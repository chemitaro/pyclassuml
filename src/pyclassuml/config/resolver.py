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
_TOP_LEVEL_KEYS = {
    "project_root",
    "package_root",
    "scope_root",
    "output",
    "ignore",
    "depth",
    "mode",
    "target_python",
    "relative_path_base",
    "diff",
}
_DIFF_KEYS = {"current_state", "include_untracked"}


@dataclass(frozen=True)
class ConfigResolution:
    """Seam-local result for config context resolution."""

    context: ExecutionContext | None
    analysis_config: AnalysisConfig | None
    diagnostics: tuple[Diagnostic, ...] = ()


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

        context = _build_execution_context(request, execution_cwd, config_path, config)
        analysis_config = _build_analysis_config(request, execution_cwd, config_path, config)
        return ConfigResolution(context=context, analysis_config=analysis_config, diagnostics=())
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

    for key in ("project_root", "package_root", "scope_root", "output"):
        if key in config and not isinstance(config[key], str):
            _invalid_config(f"{key} must be a string")

    if "ignore" in config:
        ignore = config["ignore"]
        if not isinstance(ignore, list) or not all(isinstance(item, str) and item for item in ignore):
            _invalid_config("ignore must be a list of non-empty strings")

    if "depth" in config and (
        isinstance(config["depth"], bool) or not isinstance(config["depth"], int) or config["depth"] < 0
    ):
        _invalid_config("depth must be a non-negative integer")

    if "mode" in config and config["mode"] not in {mode.value for mode in AnalysisMode}:
        _invalid_config("mode must be warn or strict")

    if "target_python" in config and not _is_target_python(config["target_python"]):
        _invalid_config("target_python must match 3.<minor>")

    if "relative_path_base" in config and config["relative_path_base"] not in {"config", "cwd"}:
        _invalid_config("relative_path_base must be config or cwd")

    if "diff" in config:
        diff = config["diff"]
        if not isinstance(diff, dict):
            _invalid_config("diff must be a table")
        unknown_diff = set(diff) - _DIFF_KEYS
        if unknown_diff:
            _invalid_config(f"unknown diff key: {sorted(unknown_diff)[0]}")
        if "current_state" in diff and diff["current_state"] not in {state.value for state in DiffCurrentState}:
            _invalid_config("diff.current_state must be working-tree or head")
        if "include_untracked" in diff and not isinstance(diff["include_untracked"], bool):
            _invalid_config("diff.include_untracked must be a bool")


def _build_execution_context(
    request: CommandRequest,
    execution_cwd: Path,
    config_path: Path | None,
    config: dict[str, Any],
) -> ExecutionContext:
    options = request.cli_options
    config_base = _config_base(execution_cwd, config_path, config)

    project_root = _merged_root(
        cli_value=options.project_root,
        config_value=config.get("project_root"),
        cli_base=execution_cwd,
        config_base=config_base,
        default=(config_path.parent if config_path is not None else execution_cwd),
        field_name="project_root",
    )
    package_root = _merged_root(
        cli_value=options.package_root,
        config_value=config.get("package_root"),
        cli_base=execution_cwd,
        config_base=config_base,
        default=project_root,
        field_name="package_root",
    )
    scope_root = _merged_root(
        cli_value=options.scope_root,
        config_value=config.get("scope_root"),
        cli_base=execution_cwd,
        config_base=config_base,
        default=package_root,
        field_name="scope_root",
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
    config_path: Path | None,
    config: dict[str, Any],
) -> AnalysisConfig:
    options = request.cli_options
    config_base = _config_base(execution_cwd, config_path, config)
    diff_config = config.get("diff", {})

    target_python = options.target_python if options.target_python is not None else config.get("target_python")
    if target_python is not None and not _is_target_python(target_python):
        _invalid_config("target_python must match 3.<minor>")

    output = (
        _resolve_path(
            options.output,
            execution_cwd,
            code="invalid_path_resolution",
            failure_reason=FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
            field_name="output",
        )
        if options.output is not None
        else _resolve_path(
            Path(config["output"]),
            config_base,
            code="invalid_path_resolution",
            failure_reason=FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
            field_name="output",
        )
        if "output" in config
        else None
    )

    mode = (
        AnalysisMode.STRICT
        if options.strict
        else AnalysisMode(config["mode"])
        if "mode" in config
        else AnalysisMode.WARN
    )

    if options.command is CommandName.DIFF and options.diff is not None:
        if options.diff.current_state_cli_provided:
            diff_current_state = options.diff.current_state
        else:
            diff_current_state = DiffCurrentState(diff_config.get("current_state", DiffCurrentState.WORKING_TREE.value))
        if options.diff.include_untracked_cli_provided:
            diff_include_untracked = options.diff.include_untracked
        else:
            diff_include_untracked = diff_config.get("include_untracked", True)
    else:
        diff_current_state = DiffCurrentState(diff_config.get("current_state", DiffCurrentState.WORKING_TREE.value))
        diff_include_untracked = diff_config.get("include_untracked", True)

    return AnalysisConfig(
        ignore=options.ignore if options.ignore else tuple(config.get("ignore", ())),
        output=output,
        depth=_merged_depth(options.depth, config.get("depth")),
        mode=mode,
        target_python=target_python,
        diff_current_state=diff_current_state,
        diff_include_untracked=diff_include_untracked,
    )


def _merged_root(
    *,
    cli_value: Path | None,
    config_value: object,
    cli_base: Path,
    config_base: Path,
    default: Path,
    field_name: str,
) -> Path:
    if cli_value is not None:
        root = _resolve_path(
            cli_value,
            cli_base,
            code="invalid_path_resolution",
            failure_reason=FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
            field_name=field_name,
        )
    elif config_value is not None:
        root = _resolve_path(
            Path(config_value),
            config_base,
            code="invalid_path_resolution",
            failure_reason=FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
            field_name=field_name,
        )
    else:
        root = _resolve_path(
            default,
            None,
            code="invalid_path_resolution",
            failure_reason=FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
            field_name=field_name,
        )

    if not root.is_dir():
        raise ConfigError(
            "invalid_root_path",
            f"{field_name} does not exist or is not a directory: {root}",
            FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
        )
    return root


def _config_base(execution_cwd: Path, config_path: Path | None, config: dict[str, Any]) -> Path:
    if config_path is None or config.get("relative_path_base", "config") == "cwd":
        return execution_cwd
    return config_path.parent


def _merged_depth(cli_value: object, config_value: object) -> int | None:
    depth = cli_value if cli_value is not None else config_value
    if depth is not None and (isinstance(depth, bool) or not isinstance(depth, int) or depth < 0):
        _invalid_config("depth must be a non-negative integer")
    return depth


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
    raise ConfigError("invalid_config", message, FailureReason.INVALID_CONFIG_OR_CONFIG_PATH)
