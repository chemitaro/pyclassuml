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
MemberKind: TypeAlias = str
MemberVisibility: TypeAlias = str

_SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")
_TARGET_PYTHON = re.compile(r"^3\.[0-9]+$")
_MEMBER_KINDS = frozenset({"field", "method"})
_MEMBER_VISIBILITIES = frozenset({"public", "protected", "private"})
_RELATION_TYPES = frozenset(
    {"inherits", "realizes", "composition", "aggregation", "association", "uses", "dependency"}
)
_ANNOTATION_SHAPES = frozenset({"direct", "optional", "union", "collection", "mapping_value"})
_DIFF_BASE_RESOLUTION_KINDS = frozenset(
    {"explicit_base", "default_branch_head", "default_branch_merge_base", "initial_commit_fallback"}
)


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


def _ensure_optional_string(value: object, field_name: str) -> None:
    if value is not None and not isinstance(value, str):
        raise ValueError(f"{field_name} must be str or None")


def _ensure_optional_non_empty_string(value: object, field_name: str) -> None:
    if value is not None:
        _ensure_non_empty_string(value, field_name)


def _ensure_non_empty_strings(values: tuple[object, ...], field_name: str) -> None:
    for value in values:
        _ensure_non_empty_string(value, field_name)


def _ensure_diff_base_resolution_kind(value: object) -> None:
    if value not in _DIFF_BASE_RESOLUTION_KINDS:
        raise ValueError(
            "resolution_kind must be one of: explicit_base, default_branch_head, default_branch_merge_base, "
            "initial_commit_fallback"
        )


def _ensure_member_kind(value: object) -> None:
    if value not in _MEMBER_KINDS:
        raise ValueError("kind must be one of: field, method")


def _ensure_member_visibility(value: object) -> None:
    if value not in _MEMBER_VISIBILITIES:
        raise ValueError("visibility must be one of: public, protected, private")


def _ensure_relation_type(value: object) -> None:
    if value not in _RELATION_TYPES:
        raise ValueError(
            "relation_type must be one of: inherits, realizes, composition, aggregation, association, uses, dependency"
        )


def _ensure_annotation_shape(value: object) -> None:
    if value is not None and value not in _ANNOTATION_SHAPES:
        raise ValueError("annotation_shape must be one of: direct, optional, union, collection, mapping_value, None")


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
    base_ref: str | None
    current_state: DiffCurrentState
    include_untracked: bool
    current_state_cli_provided: bool = True
    include_untracked_cli_provided: bool = True

    def __post_init__(self) -> None:
        _ensure_optional_non_empty_string(self.base_ref, "base_ref")
        _ensure_enum(self.current_state, DiffCurrentState, "current_state")
        if not isinstance(self.include_untracked, bool):
            raise ValueError("include_untracked must be bool")
        if not isinstance(self.current_state_cli_provided, bool):
            raise ValueError("current_state_cli_provided must be bool")
        if not isinstance(self.include_untracked_cli_provided, bool):
            raise ValueError("include_untracked_cli_provided must be bool")


@dataclass(frozen=True)
class DiffBaseResolution:
    requested_base_ref: str | None
    resolved_base_ref: str
    resolution_kind: str
    candidate_ref: str | None = None

    def __post_init__(self) -> None:
        _ensure_optional_non_empty_string(self.requested_base_ref, "requested_base_ref")
        _ensure_non_empty_string(self.resolved_base_ref, "resolved_base_ref")
        _ensure_diff_base_resolution_kind(self.resolution_kind)
        _ensure_optional_non_empty_string(self.candidate_ref, "candidate_ref")


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
    vcs_root: Path | None = None
    import_roots: tuple[Path, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("execution_cwd", "project_root", "package_root", "scope_root"):
            if not isinstance(getattr(self, field_name), Path):
                raise ValueError(f"{field_name} must be Path")
        vcs_root = self.project_root if self.vcs_root is None else self.vcs_root
        if not isinstance(vcs_root, Path):
            raise ValueError("vcs_root must be Path")
        import_roots = tuple(self.import_roots) or (self.project_root,)
        for import_root in import_roots:
            if not isinstance(import_root, Path):
                raise ValueError("import_roots must contain Path values")
        object.__setattr__(self, "vcs_root", vcs_root)
        object.__setattr__(self, "import_roots", import_roots)


@dataclass(frozen=True)
class AnalysisConfig:
    ignore: tuple[str, ...] = ()
    output: Path | None = None
    depth: int | None = None
    mode: AnalysisMode = AnalysisMode.WARN
    target_python: str | None = None
    diff_current_state: DiffCurrentState = DiffCurrentState.WORKING_TREE
    diff_include_untracked: bool = True

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
class ClassReference:
    source_class_id: ClassId
    target_name: str
    reference_kind: EvidenceKind
    reference_owner: str
    annotation_shape: str | None = None

    def __post_init__(self) -> None:
        _ensure_non_empty_string(self.source_class_id, "source_class_id")
        _ensure_non_empty_string(self.target_name, "target_name")
        _ensure_non_empty_string(self.reference_kind, "reference_kind")
        _ensure_non_empty_string(self.reference_owner, "reference_owner")
        _ensure_annotation_shape(self.annotation_shape)


@dataclass(frozen=True)
class MemberParameter:
    name: str
    annotation_text: str | None = None

    def __post_init__(self) -> None:
        _ensure_non_empty_string(self.name, "name")
        _ensure_optional_string(self.annotation_text, "annotation_text")


@dataclass(frozen=True)
class ClassMember:
    owner_class_id: ClassId
    name: str
    kind: MemberKind
    visibility: MemberVisibility
    annotation_text: str | None = None
    parameters: tuple[MemberParameter, ...] = ()
    return_annotation_text: str | None = None
    modifiers: tuple[str, ...] = ()
    source_order: int = 0

    def __post_init__(self) -> None:
        _ensure_non_empty_string(self.owner_class_id, "owner_class_id")
        _ensure_non_empty_string(self.name, "name")
        _ensure_member_kind(self.kind)
        _ensure_member_visibility(self.visibility)
        _ensure_optional_string(self.annotation_text, "annotation_text")
        parameters = _as_tuple(self.parameters)
        for parameter in parameters:
            if not isinstance(parameter, MemberParameter):
                raise ValueError("parameters must contain MemberParameter values")
        _ensure_optional_string(self.return_annotation_text, "return_annotation_text")
        modifiers = _as_tuple(self.modifiers)
        _ensure_non_empty_strings(modifiers, "modifiers")
        _ensure_non_negative_int(self.source_order, "source_order")
        object.__setattr__(self, "parameters", parameters)
        object.__setattr__(self, "modifiers", modifiers)


@dataclass(frozen=True)
class SelectedRelation:
    source_class_id: ClassId
    target_class_id: ClassId
    relation_type: RelationType
    evidence_kind: EvidenceKind

    def __post_init__(self) -> None:
        _ensure_non_empty_string(self.source_class_id, "source_class_id")
        _ensure_non_empty_string(self.target_class_id, "target_class_id")
        _ensure_relation_type(self.relation_type)
        _ensure_non_empty_string(self.evidence_kind, "evidence_kind")


@dataclass(frozen=True)
class SelectedRelations:
    relations: tuple[SelectedRelation, ...] = ()

    def __post_init__(self) -> None:
        relations = _as_tuple(self.relations)
        for relation in relations:
            if not isinstance(relation, SelectedRelation):
                raise ValueError("relations must contain SelectedRelation values")
        object.__setattr__(self, "relations", relations)


@dataclass(frozen=True)
class ClassSpan:
    class_id: ClassId
    start_line: int
    end_line: int

    def __post_init__(self) -> None:
        _ensure_non_empty_string(self.class_id, "class_id")
        if (
            isinstance(self.start_line, bool)
            or isinstance(self.end_line, bool)
            or not isinstance(self.start_line, int)
            or not isinstance(self.end_line, int)
            or self.start_line < 1
            or self.end_line < self.start_line
        ):
            raise ValueError("class span must be a positive inclusive line range")


@dataclass(frozen=True)
class ParsedModule:
    module_path: ModulePath
    imports: tuple[str, ...] = ()
    classes: tuple[ClassId, ...] = ()
    class_references: tuple[ClassReference, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()
    members: tuple[ClassMember, ...] = ()
    class_spans: tuple[ClassSpan, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.module_path, Path):
            raise ValueError("module_path must be Path")
        imports = _as_tuple(self.imports)
        classes = _as_tuple(self.classes)
        class_references = _as_tuple(self.class_references)
        diagnostics = _as_tuple(self.diagnostics)
        members = _as_tuple(self.members)
        class_spans = _as_tuple(self.class_spans)
        _ensure_non_empty_strings(imports, "imports")
        _ensure_non_empty_strings(classes, "classes")
        for class_reference in class_references:
            if not isinstance(class_reference, ClassReference):
                raise ValueError("class_references must contain ClassReference values")
        _ensure_diagnostics(diagnostics, "diagnostics")
        for member in members:
            if not isinstance(member, ClassMember):
                raise ValueError("members must contain ClassMember values")
        for class_span in class_spans:
            if not isinstance(class_span, ClassSpan):
                raise ValueError("class_spans must contain ClassSpan values")
        object.__setattr__(self, "imports", imports)
        object.__setattr__(self, "classes", classes)
        object.__setattr__(self, "class_references", class_references)
        object.__setattr__(self, "diagnostics", diagnostics)
        object.__setattr__(self, "members", members)
        object.__setattr__(self, "class_spans", class_spans)


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
    members: tuple[ClassMember, ...] = ()
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
        for member in members:
            if not isinstance(member, ClassMember):
                raise ValueError("members must contain ClassMember values")
        _ensure_non_empty_strings(grouping_keys, "grouping_keys")
        for relation in _as_tuple(self.relations):
            relation_tuple = _as_fixed_tuple(relation, 3, "relations", "triples")
            _ensure_non_empty_strings(relation_tuple, "relations")
            _ensure_relation_type(relation_tuple[2])
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
            _ensure_relation_type(relation_tuple[2])
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
class RenderFailureSignal:
    failure_reason: FailureReason
    diagnostics: tuple[Diagnostic, ...] = ()
    class_count: int = 0
    relation_count: int = 0
    partial_diagram_present: bool = False

    def __post_init__(self) -> None:
        _ensure_enum(self.failure_reason, FailureReason, "failure_reason")
        diagnostics = _as_tuple(self.diagnostics)
        _ensure_diagnostics(diagnostics, "diagnostics")
        _ensure_non_negative_int(self.class_count, "class_count")
        _ensure_non_negative_int(self.relation_count, "relation_count")
        if not isinstance(self.partial_diagram_present, bool):
            raise ValueError("partial_diagram_present must be bool")
        if self.partial_diagram_present != (self.class_count > 0):
            raise ValueError("partial_diagram_present must equal class_count > 0")
        object.__setattr__(self, "diagnostics", diagnostics)


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
    diff_base_resolution: DiffBaseResolution | None = None

    def __post_init__(self) -> None:
        if self.artifact_path is not None and not isinstance(self.artifact_path, Path):
            raise ValueError("artifact_path must be Path or None")
        if not isinstance(self.summary, RunSummary):
            raise ValueError("summary must be RunSummary")
        diagnostics = _as_tuple(self.diagnostics)
        _ensure_diagnostics(diagnostics, "diagnostics")
        _ensure_non_negative_int(self.exit_code, "exit_code")
        if self.diff_base_resolution is not None and not isinstance(self.diff_base_resolution, DiffBaseResolution):
            raise ValueError("diff_base_resolution must be DiffBaseResolution or None")
        object.__setattr__(self, "diagnostics", diagnostics)


__all__ = [
    "Alias",
    "AnalysisConfig",
    "AnalysisMode",
    "ChangedClassInventory",
    "ClassMember",
    "ClassReference",
    "ClassId",
    "ClassSpan",
    "CommandName",
    "CommandOptions",
    "CommandRequest",
    "CommandResult",
    "DependencyGraph",
    "Diagnostic",
    "DiagnosticCode",
    "DiagnosticSeverity",
    "DiffBaseResolution",
    "DiffCurrentState",
    "DiffOptions",
    "DiagramModel",
    "EvidenceKind",
    "ExecutionContext",
    "FailureReason",
    "GenerateOptions",
    "GroupingKey",
    "MemberKind",
    "MemberParameter",
    "MemberVisibility",
    "ModulePath",
    "OriginSeam",
    "ParsedModule",
    "PlantUmlText",
    "Recoverability",
    "RelationType",
    "RenderFailureSignal",
    "RenderReadyModel",
    "RunSummary",
    "SelectedClasses",
    "SelectedRelation",
    "SelectedRelations",
    "TargetObservations",
    "TargetSet",
]
