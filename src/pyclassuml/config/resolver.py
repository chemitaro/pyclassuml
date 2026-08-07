"""Resolve execution context and analysis config from command requests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import tomllib
from typing import Any

from pyclassuml.model import (
    AnalysisConfig,
    AnalysisMode,
    CommandName,
    CommandRequest,
    Diagnostic,
    DiagnosticSeverity,
    DiffCurrentState,
    ExecutionContext,
    FailureReason,
    OriginSeam,
    Recoverability,
)

CONFIG_FILE_NAME = ".pyclassuml.toml"
_TARGET_PYTHON = re.compile(r"^3\.[0-9]+$")
_COMMON_CONFIG_KEYS = {
    "project_root",
    "package_root",
    "scope_root",
    "output",
    "ignore",
    "depth",
    "mode",
    "target_python",
    "relative_path_base",
}
_DIFF_ONLY_CONFIG_KEYS = {"current_state", "include_untracked"}
_COMMAND_TABLE_KEYS = {"generate", "diff"}
_TOP_LEVEL_KEYS = _COMMON_CONFIG_KEYS | _COMMAND_TABLE_KEYS
_GENERATE_KEYS = _COMMON_CONFIG_KEYS
_DIFF_KEYS = _COMMON_CONFIG_KEYS | _DIFF_ONLY_CONFIG_KEYS
if _COMMON_CONFIG_KEYS & _DIFF_ONLY_CONFIG_KEYS:
    raise AssertionError("common and diff-only config keys must be disjoint")


@dataclass(frozen=True)
class ConfigResolution:
    """Seam-local result for config context resolution."""

    context: ExecutionContext | None
    analysis_config: AnalysisConfig | None
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True)
class _ConfigLayers:
    common: dict[str, Any]
    active: dict[str, Any]
    active_name: str
    diff: dict[str, Any]
    config_base: Path


@dataclass(frozen=True)
class _SelectedValue:
    value: object
    origin: str


class ConfigError(Exception):
    def __init__(self, code: str, message: str, failure_reason: FailureReason) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.failure_reason = failure_reason


def resolve_context(request: CommandRequest) -> ConfigResolution:
    """Resolve paths and analysis configuration without downstream side effects."""

    try:
        execution_cwd = _resolve_execution_cwd(request)
        config_path = _discover_config_path(request, execution_cwd)
        config = _load_config(config_path) if config_path is not None else {}
        layers = _build_config_layers(
            request.cli_options.command, execution_cwd, config_path, config
        )

        context = _build_execution_context(request, execution_cwd, config_path, layers)
        analysis_config = _build_analysis_config(request, execution_cwd, layers)
        return ConfigResolution(
            context=context, analysis_config=analysis_config, diagnostics=()
        )
    except ConfigError as exc:
        return ConfigResolution(
            context=None,
            analysis_config=None,
            diagnostics=(
                Diagnostic(
                    severity=DiagnosticSeverity.ERROR,
                    code=exc.code,
                    message=exc.message,
                    origin_seam=OriginSeam.CONFIG,
                    recoverability=Recoverability.FATAL,
                    failure_reason=exc.failure_reason,
                ),
            ),
        )


def _resolve_execution_cwd(request: CommandRequest) -> Path:
    process_cwd = _resolve_path(
        request.process_cwd,
        None,
        code="invalid_path_resolution",
        failure_reason=FailureReason.INVALID_PATH_OR_CONTAINMENT,
        field_name="process_cwd",
    )
    raw_cwd = request.cli_options.cwd
    execution_cwd = (
        process_cwd
        if raw_cwd is None
        else _resolve_path(
            raw_cwd,
            process_cwd,
            code="invalid_path_resolution",
            failure_reason=FailureReason.INVALID_PATH_OR_CONTAINMENT,
            field_name="cwd",
        )
    )
    if not execution_cwd.is_dir():
        raise ConfigError(
            "invalid_cwd",
            f"cwd does not exist or is not a directory: {execution_cwd}",
            FailureReason.INVALID_PATH_OR_CONTAINMENT,
        )
    return execution_cwd


def _discover_config_path(request: CommandRequest, execution_cwd: Path) -> Path | None:
    options = request.cli_options
    if options.config is not None:
        config_path = _resolve_path(
            options.config,
            execution_cwd,
            code="invalid_path_resolution",
            failure_reason=FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
            field_name="config",
        )
        if not config_path.is_file():
            raise ConfigError(
                "invalid_config_path",
                f"config file does not exist or is not a file: {config_path}",
                FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
            )
        return config_path

    if options.project_root is not None:
        project_root = _resolve_path(
            options.project_root,
            execution_cwd,
            code="invalid_path_resolution",
            failure_reason=FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
            field_name="project_root",
        )
        project_config = project_root / CONFIG_FILE_NAME
        if project_config.is_file():
            return project_config

    return _find_parent_config(execution_cwd)


def _find_parent_config(start: Path) -> Path | None:
    for directory in (start, *start.parents):
        config_path = directory / CONFIG_FILE_NAME
        if config_path.is_file():
            return config_path
    return None


def _load_config(config_path: Path) -> dict[str, Any]:
    try:
        with config_path.open("rb") as file:
            loaded = tomllib.load(file)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(
            "invalid_config_toml",
            f"config file is not valid TOML: {config_path}: {exc}",
            FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
        ) from exc
    except OSError as exc:
        raise ConfigError(
            "invalid_config_path",
            f"config file could not be read: {config_path}: {exc}",
            FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
        ) from exc

    _validate_config_schema(loaded)
    return loaded


def _validate_config_schema(config: dict[str, Any]) -> None:
    unknown = set(config) - _TOP_LEVEL_KEYS
    if unknown:
        _invalid_config(f"unknown config key: {sorted(unknown)[0]}")

    _validate_common_section(config, section_name="")
    for section_name, allowed_keys in (
        ("generate", _GENERATE_KEYS),
        ("diff", _DIFF_KEYS),
    ):
        if section_name not in config:
            continue
        section = config[section_name]
        if not isinstance(section, dict):
            _invalid_config(f"{section_name} must be a table")
        unknown_section = set(section) - allowed_keys
        if unknown_section:
            _invalid_config(f"unknown {section_name} key: {sorted(unknown_section)[0]}")
        _validate_common_section(section, section_name=section_name)
        if section_name == "diff":
            _validate_diff_only_section(section)


def _validate_common_section(
    values: dict[str, Any],
    *,
    section_name: str,
) -> None:
    for key in ("project_root", "package_root", "scope_root", "output"):
        if key in values and not isinstance(values[key], str):
            _invalid_config(
                f"{_qualified_field_name(section_name, key)} must be a string"
            )

    if "ignore" in values:
        ignore = values["ignore"]
        if not isinstance(ignore, list) or not all(
            isinstance(item, str) and item for item in ignore
        ):
            _invalid_config(
                f"{_qualified_field_name(section_name, 'ignore')} must be a list of non-empty strings"
            )

    if "depth" in values and (
        isinstance(values["depth"], bool)
        or not isinstance(values["depth"], int)
        or values["depth"] < 0
    ):
        _invalid_config(
            f"{_qualified_field_name(section_name, 'depth')} must be a non-negative integer"
        )

    if "mode" in values and values["mode"] not in {mode.value for mode in AnalysisMode}:
        _invalid_config(
            f"{_qualified_field_name(section_name, 'mode')} must be warn or strict"
        )

    if "target_python" in values and not _is_target_python(values["target_python"]):
        _invalid_config(
            f"{_qualified_field_name(section_name, 'target_python')} must match 3.<minor>"
        )

    if "relative_path_base" in values and values["relative_path_base"] not in {
        "config",
        "cwd",
    }:
        _invalid_config(
            f"{_qualified_field_name(section_name, 'relative_path_base')} must be config or cwd"
        )


def _validate_diff_only_section(values: dict[str, Any]) -> None:
    if "current_state" in values and values["current_state"] not in {
        state.value for state in DiffCurrentState
    }:
        _invalid_config("diff.current_state must be working-tree or head")
    if "include_untracked" in values and not isinstance(
        values["include_untracked"], bool
    ):
        _invalid_config("diff.include_untracked must be a bool")


def _qualified_field_name(section_name: str, field_name: str) -> str:
    return f"{section_name}.{field_name}" if section_name else field_name


def _build_execution_context(
    request: CommandRequest,
    execution_cwd: Path,
    config_path: Path | None,
    layers: _ConfigLayers,
) -> ExecutionContext:
    options = request.cli_options
    project_root = _resolve_root(
        _select_value(
            cli_value=options.project_root,
            cli_provided=options.project_root is not None,
            command_section=layers.active,
            common_section=layers.common,
            key="project_root",
            default=(config_path.parent if config_path is not None else execution_cwd),
        ),
        execution_cwd=execution_cwd,
        config_base=layers.config_base,
        field_name="project_root",
        section_name=layers.active_name,
    )
    package_root = _resolve_root(
        _select_value(
            cli_value=options.package_root,
            cli_provided=options.package_root is not None,
            command_section=layers.active,
            common_section=layers.common,
            key="package_root",
            default=project_root,
        ),
        execution_cwd=execution_cwd,
        config_base=layers.config_base,
        field_name="package_root",
        section_name=layers.active_name,
    )
    scope_root = _resolve_root(
        _select_value(
            cli_value=options.scope_root,
            cli_provided=options.scope_root is not None,
            command_section=layers.active,
            common_section=layers.common,
            key="scope_root",
            default=package_root,
        ),
        execution_cwd=execution_cwd,
        config_base=layers.config_base,
        field_name="scope_root",
        section_name=layers.active_name,
    )

    if not _is_relative_to(package_root, project_root):
        raise ConfigError(
            "invalid_containment",
            f"package_root must be under or equal to project_root: {package_root}",
            FailureReason.INVALID_PATH_OR_CONTAINMENT,
        )
    if not _is_relative_to(scope_root, package_root):
        raise ConfigError(
            "invalid_containment",
            f"scope_root must be under or equal to package_root: {scope_root}",
            FailureReason.INVALID_PATH_OR_CONTAINMENT,
        )

    import_roots = _default_import_roots(project_root, package_root)
    return ExecutionContext(
        execution_cwd=execution_cwd,
        project_root=project_root,
        package_root=package_root,
        scope_root=scope_root,
        vcs_root=project_root,
        import_roots=import_roots,
    )


def _default_import_roots(project_root: Path, package_root: Path) -> tuple[Path, ...]:
    if package_root == project_root:
        return (project_root,)
    return (package_root, project_root)


def _build_analysis_config(
    request: CommandRequest,
    execution_cwd: Path,
    layers: _ConfigLayers,
) -> AnalysisConfig:
    options = request.cli_options
    output_value = _select_value(
        cli_value=options.output,
        cli_provided=options.output is not None,
        command_section=layers.active,
        common_section=layers.common,
        key="output",
        default=None,
    )
    output = (
        None
        if output_value.value is None
        else _resolve_selected_path(
            output_value,
            execution_cwd=execution_cwd,
            config_base=layers.config_base,
            field_name="output",
            section_name=layers.active_name,
        )
    )

    ignore = _select_value(
        cli_value=options.ignore,
        cli_provided=bool(options.ignore),
        command_section=layers.active,
        common_section=layers.common,
        key="ignore",
        default=(),
    ).value
    depth = _select_value(
        cli_value=options.depth,
        cli_provided=options.depth is not None,
        command_section=layers.active,
        common_section=layers.common,
        key="depth",
        default=_default_depth(options.command),
    ).value
    mode = AnalysisMode(
        _select_value(
            cli_value=AnalysisMode.STRICT,
            cli_provided=options.strict,
            command_section=layers.active,
            common_section=layers.common,
            key="mode",
            default=AnalysisMode.WARN,
        ).value
    )
    target_python = _select_value(
        cli_value=options.target_python,
        cli_provided=options.target_python is not None,
        command_section=layers.active,
        common_section=layers.common,
        key="target_python",
        default=None,
    ).value

    diff_options = options.diff
    diff_current_state = DiffCurrentState(
        _select_value(
            cli_value=(
                diff_options.current_state
                if diff_options is not None
                else DiffCurrentState.WORKING_TREE
            ),
            cli_provided=(
                diff_options is not None and diff_options.current_state_cli_provided
            ),
            command_section=layers.diff,
            common_section={},
            key="current_state",
            default=DiffCurrentState.WORKING_TREE,
        ).value
    )
    diff_include_untracked = bool(
        _select_value(
            cli_value=(
                diff_options.include_untracked if diff_options is not None else True
            ),
            cli_provided=(
                diff_options is not None and diff_options.include_untracked_cli_provided
            ),
            command_section=layers.diff,
            common_section={},
            key="include_untracked",
            default=True,
        ).value
    )

    return AnalysisConfig(
        ignore=ignore,
        output=output,
        depth=depth,
        mode=mode,
        target_python=target_python,
        diff_current_state=diff_current_state,
        diff_include_untracked=diff_include_untracked,
    )


def _build_config_layers(
    command: CommandName,
    execution_cwd: Path,
    config_path: Path | None,
    config: dict[str, Any],
) -> _ConfigLayers:
    active = config.get(command.value, {})
    diff = config.get("diff", {})
    relative_path_base = _select_value(
        cli_value=None,
        cli_provided=False,
        command_section=active,
        common_section=config,
        key="relative_path_base",
        default="config",
    ).value
    return _ConfigLayers(
        common=config,
        active=active,
        active_name=command.value,
        diff=diff,
        config_base=_config_base(execution_cwd, config_path, relative_path_base),
    )


def _select_value(
    *,
    cli_value: object,
    cli_provided: bool,
    command_section: dict[str, Any],
    common_section: dict[str, Any],
    key: str,
    default: object,
) -> _SelectedValue:
    if cli_provided:
        return _SelectedValue(cli_value, "cli")
    if key in command_section:
        return _SelectedValue(command_section[key], "command")
    if key in common_section:
        return _SelectedValue(common_section[key], "common")
    return _SelectedValue(default, "default")


def _resolve_root(
    selected: _SelectedValue,
    *,
    execution_cwd: Path,
    config_base: Path,
    field_name: str,
    section_name: str,
) -> Path:
    root = _resolve_selected_path(
        selected,
        execution_cwd=execution_cwd,
        config_base=config_base,
        field_name=field_name,
        section_name=section_name,
    )
    diagnostic_field_name = _selected_field_name(selected, field_name, section_name)
    if not root.is_dir():
        raise ConfigError(
            "invalid_root_path",
            f"{diagnostic_field_name} does not exist or is not a directory: {root}",
            FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
        )
    return root


def _resolve_selected_path(
    selected: _SelectedValue,
    *,
    execution_cwd: Path,
    config_base: Path,
    field_name: str,
    section_name: str,
) -> Path:
    path = Path(selected.value)
    base = (
        execution_cwd
        if selected.origin == "cli"
        else config_base
        if selected.origin in {"command", "common"}
        else None
    )
    return _resolve_path(
        path,
        base,
        code="invalid_path_resolution",
        failure_reason=FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
        field_name=_selected_field_name(selected, field_name, section_name),
    )


def _selected_field_name(
    selected: _SelectedValue,
    field_name: str,
    section_name: str,
) -> str:
    if selected.origin == "command":
        return f"{section_name}.{field_name}"
    return field_name


def _config_base(
    execution_cwd: Path, config_path: Path | None, relative_path_base: object
) -> Path:
    if config_path is None or relative_path_base == "cwd":
        return execution_cwd
    return config_path.parent


def _default_depth(command: CommandName) -> int | None:
    if command is CommandName.DIFF:
        return 1
    if command is CommandName.GENERATE:
        return None
    raise AssertionError(f"unsupported command: {command}")


def _resolve_path(
    path: Path,
    base: Path | None,
    *,
    code: str = "invalid_path_resolution",
    failure_reason: FailureReason = FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
    field_name: str = "path",
) -> Path:
    try:
        return (path if path.is_absolute() or base is None else base / path).resolve()
    except (OSError, RuntimeError) as exc:
        raise ConfigError(
            code,
            f"{field_name} could not be resolved: {path}: {exc}",
            failure_reason,
        ) from exc


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _is_target_python(value: object) -> bool:
    return isinstance(value, str) and _TARGET_PYTHON.fullmatch(value) is not None


def _invalid_config(message: str) -> None:
    raise ConfigError(
        "invalid_config", message, FailureReason.INVALID_CONFIG_OR_CONFIG_PATH
    )
