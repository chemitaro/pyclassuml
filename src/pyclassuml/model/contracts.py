"""Immutable DTO contracts shared across pyclassuml seams."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import re
from types import MappingProxyType
from typing import Mapping, TypeAlias


ClassId: TypeAlias = str
ModulePath: TypeAlias = Path
DiagnosticCode: TypeAlias = str
RelationType: TypeAlias = str
EvidenceKind: TypeAlias = str
GroupingKey: TypeAlias = str
Alias: TypeAlias = str

_SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")
_TARGET_PYTHON = re.compile(r"^3\.[0-9]+$")


class CommandName(str, Enum):
    GENERATE = "generate"
    DIFF = "diff"


class AnalysisMode(str, Enum):
    WARN = "warn"
    STRICT = "strict"


class DiffCurrentState(str, Enum):
    WORKING_TREE = "working-tree"
    HEAD = "head"


class DiagnosticSeverity(str, Enum):
    WARNING = "warning"
    ERROR = "error"


class Recoverability(str, Enum):
    RECOVERABLE = "recoverable"
    DEGRADED_OUTPUT = "degraded_output"
    FATAL = "fatal"


class OriginSeam(str, Enum):
    CLI = "cli"
    CONFIG = "config"
    TARGETS = "targets"
    VCS = "vcs"
    PARSE = "parse"
    ANALYZE = "analyze"
    FRAMEWORKS = "frameworks"
    RENDER = "render"
    REPORT = "report"
    APP = "app"


class FailureReason(str, Enum):
    CLI_USAGE_ERROR = "cli_usage_error"
    INVALID_CONFIG_OR_CONFIG_PATH = "invalid_config_or_config_path"
    INVALID_PATH_OR_CONTAINMENT = "invalid_path_or_containment"
    STRICT_DIFF_SCOPE_EXCLUSION = "strict_diff_scope_exclusion"
    GENERATE_SCOPE_VIOLATION = "generate_scope_violation"
    GENERATE_ZERO_TARGET_AFTER_NORMALIZE = "generate_zero_target_after_normalize"
    DIFF_ZERO_TARGET_AFTER_SCOPE_FILTER = "diff_zero_target_after_scope_filter"
    STRICT_RESOLUTION_FAILURE = "strict_resolution_failure"
    STRICT_SYNTAX_ERROR = "strict_syntax_error"
    STRICT_WILDCARD_RESOLUTION_FAILURE = "strict_wildcard_resolution_failure"
    TRAVERSAL_LIMIT_REACHED = "traversal_limit_reached"
    OUTPUT_WRITE_FAILURE = "output_write_failure"
    VCS_READ_FAILURE = "vcs_read_failure"
    DIAGRAM_UNBUILDABLE_AFTER_RECOVERY = "diagram_unbuildable_after_recovery"


def _ensure_enum(value: object, enum_type: type[Enum], field_name: str) -> None:
    if not isinstance(value, enum_type):
        raise ValueError(f"{field_name} must be {enum_type.__name__}")


def _ensure_optional_enum(value: object, enum_type: type[Enum], field_name: str) -> None:
    if value is not None:
        _ensure_enum(value, enum_type, field_name)


def _ensure_non_negative_int(value: object, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative int")


def _ensure_optional_depth(value: object) -> None:
    if value is not None:
        _ensure_non_negative_int(value, "depth")


def _ensure_optional_path(value: object, field_name: str) -> None:
    if value is not None and not isinstance(value, Path):
        raise ValueError(f"{field_name} must be Path or None")


def _ensure_target_python(value: object) -> None:
    if value is not None and (not isinstance(value, str) or not _TARGET_PYTHON.fullmatch(value)):
        raise ValueError("target_python must be None or a 3.<minor> string")


def _ensure_non_empty_string(value: object, field_name: str) -> None:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{field_name} must be a non-empty str")


def _ensure_non_empty_strings(values: tuple[object, ...], field_name: str) -> None:
    for value in values:
        _ensure_non_empty_string(value, field_name)


def _ensure_diagnostics(values: tuple[object, ...], field_name: str) -> None:
    for value in values:
        if not isinstance(value, Diagnostic):
            raise ValueError(f"{field_name} must contain Diagnostic values")


def _as_tuple(values: object) -> tuple:
    if isinstance(values, (str, bytes)):
        raise ValueError("collection fields must not be bare str or bytes")
    return tuple(values)  # type: ignore[arg-type]


def _as_fixed_tuple(values: object, length: int, field_name: str, shape_name: str) -> tuple:
    item = _as_tuple(values)
    if len(item) != length:
        raise ValueError(f"{field_name} must contain {shape_name}")
    return item


@dataclass(frozen=True)
class GenerateOptions:
    targets: tuple[Path | str, ...] = ()

    def __post_init__(self) -> None:
        targets = _as_tuple(self.targets)
        for target in targets:
            if not isinstance(target, (Path, str)):
                raise ValueError("targets must contain Path or str values")
        object.__setattr__(self, "targets", targets)


@dataclass(frozen=True)
class DiffOptions:
    base_ref: str
    current_state: DiffCurrentState
    include_untracked: bool

    def __post_init__(self) -> None:
        _ensure_non_empty_string(self.base_ref, "base_ref")
        _ensure_enum(self.current_state, DiffCurrentState, "current_state")
        if not isinstance(self.include_untracked, bool):
            raise ValueError("include_untracked must be bool")


@dataclass(frozen=True)
class CommandOptions:
    command: CommandName
    cwd: Path | None = None
    config: Path | None = None
    project_root: Path | None = None
    package_root: Path | None = None
    scope_root: Path | None = None
    output: Path | None = None
    ignore: tuple[str, ...] = ()
    depth: int | None = None
    strict: bool = False
    target_python: str | None = None
    generate: GenerateOptions | None = None
    diff: DiffOptions | None = None

    def __post_init__(self) -> None:
        _ensure_enum(self.command, CommandName, "command")
        for field_name in ("cwd", "config", "project_root", "package_root", "scope_root", "output"):
            _ensure_optional_path(getattr(self, field_name), field_name)
        ignore = _as_tuple(self.ignore)
        _ensure_non_empty_strings(ignore, "ignore")
        _ensure_optional_depth(self.depth)
        _ensure_target_python(self.target_python)
        if not isinstance(self.strict, bool):
            raise ValueError("strict must be bool")
        if self.generate is not None and not isinstance(self.generate, GenerateOptions):
            raise ValueError("generate must be GenerateOptions or None")
        if self.diff is not None and not isinstance(self.diff, DiffOptions):
            raise ValueError("diff must be DiffOptions or None")
        if self.command is CommandName.GENERATE and (self.generate is None or self.diff is not None):
            raise ValueError("generate command requires generate options and no diff options")
        if self.command is CommandName.DIFF and (self.diff is None or self.generate is not None):
            raise ValueError("diff command requires diff options and no generate options")
        object.__setattr__(self, "ignore", ignore)


@dataclass(frozen=True)
class CommandRequest:
    process_cwd: Path
    cli_options: CommandOptions

    def __post_init__(self) -> None:
        if not isinstance(self.process_cwd, Path):
            raise ValueError("process_cwd must be Path")
        if not isinstance(self.cli_options, CommandOptions):
            raise ValueError("cli_options must be CommandOptions")


@dataclass(frozen=True)
class ExecutionContext:
    execution_cwd: Path
    project_root: Path
    package_root: Path
    scope_root: Path

    def __post_init__(self) -> None:
        for field_name in ("execution_cwd", "project_root", "package_root", "scope_root"):
            if not isinstance(getattr(self, field_name), Path):
                raise ValueError(f"{field_name} must be Path")


@dataclass(frozen=True)
class AnalysisConfig:
    ignore: tuple[str, ...] = ()
    output: Path | None = None
    depth: int | None = None
    mode: AnalysisMode = AnalysisMode.WARN
    target_python: str | None = None
    diff_current_state: DiffCurrentState = DiffCurrentState.WORKING_TREE
    diff_include_untracked: bool = False

    def __post_init__(self) -> None:
        ignore = _as_tuple(self.ignore)
        _ensure_non_empty_strings(ignore, "ignore")
        if self.output is not None and not isinstance(self.output, Path):
            raise ValueError("output must be Path or None")
        _ensure_optional_depth(self.depth)
        _ensure_enum(self.mode, AnalysisMode, "mode")
        _ensure_target_python(self.target_python)
        _ensure_enum(self.diff_current_state, DiffCurrentState, "diff_current_state")
        if not isinstance(self.diff_include_untracked, bool):
            raise ValueError("diff_include_untracked must be bool")
        object.__setattr__(self, "ignore", ignore)


@dataclass(frozen=True)
class TargetObservations:
    ignored_seed_candidate_count: int = 0
    diff_scope_excluded_count: int = 0

    def __post_init__(self) -> None:
        _ensure_non_negative_int(self.ignored_seed_candidate_count, "ignored_seed_candidate_count")
        _ensure_non_negative_int(self.diff_scope_excluded_count, "diff_scope_excluded_count")


@dataclass(frozen=True)
class TargetSet:
    seed_files: tuple[Path, ...]
    observations: TargetObservations

    def __post_init__(self) -> None:
        seed_files = _as_tuple(self.seed_files)
        for seed_file in seed_files:
            if not isinstance(seed_file, Path) or seed_file.suffix != ".py":
                raise ValueError("seed_files must contain .py Path values only")
        if not isinstance(self.observations, TargetObservations):
            raise ValueError("observations must be TargetObservations")
        object.__setattr__(self, "seed_files", seed_files)


@dataclass(frozen=True)
class Diagnostic:
    severity: DiagnosticSeverity
    code: DiagnosticCode
    message: str
    origin_seam: OriginSeam
    recoverability: Recoverability
    failure_reason: FailureReason | None = None

    def __post_init__(self) -> None:
        _ensure_enum(self.severity, DiagnosticSeverity, "severity")
        if not isinstance(self.code, str) or not _SNAKE_CASE.fullmatch(self.code):
            raise ValueError("code must be a non-empty snake_case str")
        _ensure_non_empty_string(self.message, "message")
        _ensure_enum(self.origin_seam, OriginSeam, "origin_seam")
        _ensure_enum(self.recoverability, Recoverability, "recoverability")
        _ensure_optional_enum(self.failure_reason, FailureReason, "failure_reason")
        if self.severity is DiagnosticSeverity.ERROR and self.failure_reason is None:
            raise ValueError("error diagnostic requires failure_reason")
        if self.severity is DiagnosticSeverity.WARNING and self.failure_reason is not None:
            raise ValueError("warning diagnostic requires failure_reason to be None")


@dataclass(frozen=True)
class ParsedModule:
    module_path: ModulePath
    imports: tuple[str, ...] = ()
    classes: tuple[ClassId, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.module_path, Path):
            raise ValueError("module_path must be Path")
        imports = _as_tuple(self.imports)
        classes = _as_tuple(self.classes)
        diagnostics = _as_tuple(self.diagnostics)
        _ensure_non_empty_strings(imports, "imports")
        _ensure_non_empty_strings(classes, "classes")
        _ensure_diagnostics(diagnostics, "diagnostics")
        object.__setattr__(self, "imports", imports)
        object.__setattr__(self, "classes", classes)
        object.__setattr__(self, "diagnostics", diagnostics)


@dataclass(frozen=True)
class DependencyGraph:
    reachable_files: tuple[Path, ...] = ()
    edges: tuple[tuple[Path, Path], ...] = ()

    def __post_init__(self) -> None:
        reachable_files = _as_tuple(self.reachable_files)
        edges = []
        for path in reachable_files:
            if not isinstance(path, Path):
                raise ValueError("reachable_files must contain Path values")
        for edge in _as_tuple(self.edges):
            edge_tuple = _as_fixed_tuple(edge, 2, "edges", "(Path, Path) tuples")
            if not all(isinstance(path, Path) for path in edge_tuple):
                raise ValueError("edges must contain (Path, Path) tuples")
            edges.append(edge_tuple)
        object.__setattr__(self, "reachable_files", reachable_files)
        object.__setattr__(self, "edges", tuple(edges))


@dataclass(frozen=True)
class SelectedClasses:
    class_ids: tuple[ClassId, ...] = ()

    def __post_init__(self) -> None:
        class_ids = _as_tuple(self.class_ids)
        _ensure_non_empty_strings(class_ids, "class_ids")
        object.__setattr__(self, "class_ids", class_ids)


@dataclass(frozen=True)
class ChangedClassInventory:
    class_count: int
    changed_files: tuple[Path, ...] = ()

    def __post_init__(self) -> None:
        _ensure_non_negative_int(self.class_count, "class_count")
        changed_files = _as_tuple(self.changed_files)
        for path in changed_files:
            if not isinstance(path, Path):
                raise ValueError("changed_files must contain Path values")
        object.__setattr__(self, "changed_files", changed_files)


@dataclass(frozen=True)
class RenderReadyModel:
    classes: tuple[ClassId, ...] = ()
    members: tuple[str, ...] = ()
    relations: tuple[tuple[ClassId, ClassId, RelationType], ...] = ()
    class_decorations: tuple[tuple[ClassId, str], ...] = ()
    grouping_keys: tuple[GroupingKey, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        classes = _as_tuple(self.classes)
        members = _as_tuple(self.members)
        relations = []
        class_decorations = []
        grouping_keys = _as_tuple(self.grouping_keys)
        diagnostics = _as_tuple(self.diagnostics)
        _ensure_non_empty_strings(classes, "classes")
        _ensure_non_empty_strings(members, "members")
        _ensure_non_empty_strings(grouping_keys, "grouping_keys")
        for relation in _as_tuple(self.relations):
            relation_tuple = _as_fixed_tuple(relation, 3, "relations", "triples")
            _ensure_non_empty_strings(relation_tuple, "relations")
            relations.append(relation_tuple)
        for decoration in _as_tuple(self.class_decorations):
            decoration_tuple = _as_fixed_tuple(decoration, 2, "class_decorations", "pairs")
            _ensure_non_empty_strings(decoration_tuple, "class_decorations")
            class_decorations.append(decoration_tuple)
        _ensure_diagnostics(diagnostics, "diagnostics")
        object.__setattr__(self, "classes", classes)
        object.__setattr__(self, "members", members)
        object.__setattr__(self, "relations", tuple(relations))
        object.__setattr__(self, "class_decorations", tuple(class_decorations))
        object.__setattr__(self, "grouping_keys", grouping_keys)
        object.__setattr__(self, "diagnostics", diagnostics)


@dataclass(frozen=True)
class DiagramModel:
    containers: tuple[str, ...] = ()
    rendered_classes: tuple[ClassId, ...] = ()
    rendered_relations: tuple[tuple[ClassId, ClassId, RelationType], ...] = ()
    aliases: tuple[tuple[ClassId, Alias], ...] = ()

    def __post_init__(self) -> None:
        containers = _as_tuple(self.containers)
        rendered_classes = _as_tuple(self.rendered_classes)
        rendered_relations = []
        aliases = []
        _ensure_non_empty_strings(containers, "containers")
        _ensure_non_empty_strings(rendered_classes, "rendered_classes")
        for relation in _as_tuple(self.rendered_relations):
            relation_tuple = _as_fixed_tuple(relation, 3, "rendered_relations", "triples")
            _ensure_non_empty_strings(relation_tuple, "rendered_relations")
            rendered_relations.append(relation_tuple)
        for alias in _as_tuple(self.aliases):
            alias_tuple = _as_fixed_tuple(alias, 2, "aliases", "pairs")
            _ensure_non_empty_strings(alias_tuple, "aliases")
            aliases.append(alias_tuple)
        object.__setattr__(self, "containers", containers)
        object.__setattr__(self, "rendered_classes", rendered_classes)
        object.__setattr__(self, "rendered_relations", tuple(rendered_relations))
        object.__setattr__(self, "aliases", tuple(aliases))


@dataclass(frozen=True)
class PlantUmlText:
    text: str

    def __post_init__(self) -> None:
        _ensure_non_empty_string(self.text, "text")


@dataclass(frozen=True)
class RunSummary:
    counters: Mapping[str, int] = field(default_factory=dict)
    failure_reason: FailureReason | None = None

    def __post_init__(self) -> None:
        _ensure_optional_enum(self.failure_reason, FailureReason, "failure_reason")
        copied: dict[str, int] = {}
        for key, value in self.counters.items():
            _ensure_non_empty_string(key, "counters key")
            _ensure_non_negative_int(value, f"counter {key}")
            copied[key] = value
        object.__setattr__(self, "counters", MappingProxyType(copied))


@dataclass(frozen=True)
class CommandResult:
    artifact_path: Path | None
    summary: RunSummary
    diagnostics: tuple[Diagnostic, ...]
    exit_code: int

    def __post_init__(self) -> None:
        if self.artifact_path is not None and not isinstance(self.artifact_path, Path):
            raise ValueError("artifact_path must be Path or None")
        if not isinstance(self.summary, RunSummary):
            raise ValueError("summary must be RunSummary")
        diagnostics = _as_tuple(self.diagnostics)
        _ensure_diagnostics(diagnostics, "diagnostics")
        _ensure_non_negative_int(self.exit_code, "exit_code")
        object.__setattr__(self, "diagnostics", diagnostics)


__all__ = [
    "Alias",
    "AnalysisConfig",
    "AnalysisMode",
    "ChangedClassInventory",
    "ClassId",
    "CommandName",
    "CommandOptions",
    "CommandRequest",
    "CommandResult",
    "DependencyGraph",
    "Diagnostic",
    "DiagnosticCode",
    "DiagnosticSeverity",
    "DiffCurrentState",
    "DiffOptions",
    "DiagramModel",
    "EvidenceKind",
    "ExecutionContext",
    "FailureReason",
    "GenerateOptions",
    "GroupingKey",
    "ModulePath",
    "OriginSeam",
    "ParsedModule",
    "PlantUmlText",
    "Recoverability",
    "RelationType",
    "RenderReadyModel",
    "RunSummary",
    "SelectedClasses",
    "TargetObservations",
    "TargetSet",
]
