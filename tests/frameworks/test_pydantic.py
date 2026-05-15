from pathlib import Path

from pyclassuml.analyze.selection import SelectedRelation, SelectedRelations
from pyclassuml.frameworks.pydantic import extract_pydantic_enrichment_hints
from pyclassuml.model import (
    AnalysisConfig,
    ClassMember,
    ClassReference,
    DiagnosticSeverity,
    ExecutionContext,
    OriginSeam,
    ParsedModule,
    Recoverability,
    SelectedClasses,
    TargetObservations,
    TargetSet,
)
from pyclassuml.parse import ModuleIndex, parse_target_set


def parsed_module(*references: ClassReference, classes: tuple[str, ...] | None = None) -> ParsedModule:
    return ParsedModule(
        module_path=Path("pkg/models.py"),
        classes=classes or ("pkg/models.py:A", "pkg/models.py:B", "pkg/models.py:C"),
        class_references=references,
    )


def module_index(*class_ids: str) -> ModuleIndex:
    return ModuleIndex(
        module_by_path={},
        project_relative_file_to_module={},
        class_to_module={class_id: Path(class_id.split(":", 1)[0]) for class_id in class_ids},
        seed_project_relative_paths=(),
        import_candidate_paths={},
    )


def write_file(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path.resolve()


def context(project_root: Path, *, package_root: Path) -> ExecutionContext:
    return ExecutionContext(
        execution_cwd=project_root.resolve(),
        project_root=project_root.resolve(),
        package_root=package_root.resolve(),
        scope_root=project_root.resolve(),
    )


def target_set(*seed_files: Path) -> TargetSet:
    return TargetSet(seed_files=tuple(seed_files), observations=TargetObservations())


def base_reference(*, source_class_id: str = "pkg/models.py:A", target_name: str = "BaseModel") -> ClassReference:
    return ClassReference(
        source_class_id=source_class_id,
        target_name=target_name,
        reference_kind="class_base",
        reference_owner="base",
    )


def annotation_reference(
    *,
    target_name: str,
    source_class_id: str = "pkg/models.py:A",
    reference_owner: str = "annotation",
) -> ClassReference:
    return ClassReference(
        source_class_id=source_class_id,
        target_name=target_name,
        reference_kind="annotation_string",
        reference_owner=reference_owner,
    )


def test_parse_to_pydantic_handoff_adds_direct_forward_ref_hint(tmp_path: Path) -> None:
    project = tmp_path / "project"
    package = project / "pkg"
    seed = write_file(
        package / "models.py",
        "\n".join(
            [
                "from pydantic import BaseModel",
                "class A(BaseModel):",
                "    child: \"B\"",
                "class B:",
                "    pass",
            ]
        ),
    )
    parse_result = parse_target_set(target_set(seed), context(project, package_root=package), AnalysisConfig())

    assert parse_result.parsed_modules[0].members == (
        ClassMember(
            owner_class_id="pkg/models.py:A",
            name="child",
            kind="field",
            visibility="public",
            annotation_text="'B'",
            source_order=1,
        ),
    )
    hints = extract_pydantic_enrichment_hints(
        parsed_modules=parse_result.parsed_modules,
        module_index=parse_result.module_index,
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/models.py:B")),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == (
        SelectedRelation(
            source_class_id="pkg/models.py:A",
            target_class_id="pkg/models.py:B",
            relation_type="uses",
            evidence_kind="pydantic_forward_ref",
        ),
    )
    assert hints.warning_diagnostics == ()


def test_parse_to_pydantic_handoff_accepts_generic_basemodel_base(tmp_path: Path) -> None:
    project = tmp_path / "project"
    package = project / "pkg"
    seed = write_file(
        package / "models.py",
        "\n".join(
            [
                "from pydantic import BaseModel",
                "class A(BaseModel[T]):",
                "    child: \"B\"",
                "class B:",
                "    pass",
            ]
        ),
    )
    parse_result = parse_target_set(target_set(seed), context(project, package_root=package), AnalysisConfig())

    hints = extract_pydantic_enrichment_hints(
        parsed_modules=parse_result.parsed_modules,
        module_index=parse_result.module_index,
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/models.py:B")),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == (
        SelectedRelation(
            source_class_id="pkg/models.py:A",
            target_class_id="pkg/models.py:B",
            relation_type="uses",
            evidence_kind="pydantic_forward_ref",
        ),
    )
    assert hints.warning_diagnostics == ()


def test_parse_to_pydantic_handoff_accepts_generic_pydantic_basemodel_base(tmp_path: Path) -> None:
    project = tmp_path / "project"
    package = project / "pkg"
    seed = write_file(
        package / "models.py",
        "\n".join(
            [
                "import pydantic",
                "class A(pydantic.BaseModel[T]):",
                "    child: \"B\"",
                "class B:",
                "    pass",
            ]
        ),
    )
    parse_result = parse_target_set(target_set(seed), context(project, package_root=package), AnalysisConfig())

    hints = extract_pydantic_enrichment_hints(
        parsed_modules=parse_result.parsed_modules,
        module_index=parse_result.module_index,
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/models.py:B")),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == (
        SelectedRelation(
            source_class_id="pkg/models.py:A",
            target_class_id="pkg/models.py:B",
            relation_type="uses",
            evidence_kind="pydantic_forward_ref",
        ),
    )
    assert hints.warning_diagnostics == ()


def test_parse_to_pydantic_handoff_adds_subscript_forward_ref_hints(tmp_path: Path) -> None:
    project = tmp_path / "project"
    package = project / "pkg"
    seed = write_file(
        package / "models.py",
        "\n".join(
            [
                "from typing import Optional, Union",
                "from pydantic import BaseModel",
                "class A(BaseModel):",
                "    items: list[\"B\"]",
                "    maybe: Optional[\"C\"]",
                "    union: Union[\"B\", \"C\"]",
                "class B:",
                "    pass",
                "class C:",
                "    pass",
            ]
        ),
    )
    parse_result = parse_target_set(target_set(seed), context(project, package_root=package), AnalysisConfig())

    hints = extract_pydantic_enrichment_hints(
        parsed_modules=parse_result.parsed_modules,
        module_index=parse_result.module_index,
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/models.py:B", "pkg/models.py:C")),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == (
        SelectedRelation(
            source_class_id="pkg/models.py:A",
            target_class_id="pkg/models.py:B",
            relation_type="uses",
            evidence_kind="pydantic_forward_ref",
        ),
        SelectedRelation(
            source_class_id="pkg/models.py:A",
            target_class_id="pkg/models.py:C",
            relation_type="uses",
            evidence_kind="pydantic_forward_ref",
        ),
    )
    assert hints.warning_diagnostics == ()


def test_parse_to_pydantic_handoff_resolves_whole_string_container_forward_refs(tmp_path: Path) -> None:
    project = tmp_path / "project"
    package = project / "pkg"
    seed = write_file(
        package / "models.py",
        "\n".join(
            [
                "from pydantic import BaseModel",
                "class A(BaseModel):",
                "    items: \"list['Item']\"",
                "    maybe: \"Optional[Item]\"",
                "    label: \"Literal['ignored']\"",
                "class Item:",
                "    pass",
            ]
        ),
    )
    parse_result = parse_target_set(target_set(seed), context(project, package_root=package), AnalysisConfig())

    hints = extract_pydantic_enrichment_hints(
        parsed_modules=parse_result.parsed_modules,
        module_index=parse_result.module_index,
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/models.py:Item")),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == (
        SelectedRelation(
            source_class_id="pkg/models.py:A",
            target_class_id="pkg/models.py:Item",
            relation_type="uses",
            evidence_kind="pydantic_forward_ref",
        ),
    )
    assert hints.warning_diagnostics == ()


def test_parse_to_pydantic_handoff_resolves_whole_string_union_forward_refs(tmp_path: Path) -> None:
    project = tmp_path / "project"
    package = project / "pkg"
    seed = write_file(
        package / "models.py",
        "\n".join(
            [
                "from pydantic import BaseModel",
                "class Model(BaseModel):",
                "    choice: \"Union[A, B]\"",
                "class A:",
                "    pass",
                "class B:",
                "    pass",
            ]
        ),
    )
    parse_result = parse_target_set(target_set(seed), context(project, package_root=package), AnalysisConfig())

    hints = extract_pydantic_enrichment_hints(
        parsed_modules=parse_result.parsed_modules,
        module_index=parse_result.module_index,
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:Model", "pkg/models.py:A", "pkg/models.py:B")),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == (
        SelectedRelation(
            source_class_id="pkg/models.py:Model",
            target_class_id="pkg/models.py:A",
            relation_type="uses",
            evidence_kind="pydantic_forward_ref",
        ),
        SelectedRelation(
            source_class_id="pkg/models.py:Model",
            target_class_id="pkg/models.py:B",
            relation_type="uses",
            evidence_kind="pydantic_forward_ref",
        ),
    )
    assert hints.warning_diagnostics == ()


def test_parse_to_pydantic_handoff_adds_nested_model_forward_ref_hint(tmp_path: Path) -> None:
    project = tmp_path / "project"
    package = project / "pkg"
    seed = write_file(
        package / "models.py",
        "\n".join(
            [
                "from pydantic import BaseModel",
                "class A:",
                "    class Nested(BaseModel):",
                "        child: \"B\"",
                "class B:",
                "    pass",
            ]
        ),
    )
    parse_result = parse_target_set(target_set(seed), context(project, package_root=package), AnalysisConfig())

    hints = extract_pydantic_enrichment_hints(
        parsed_modules=parse_result.parsed_modules,
        module_index=parse_result.module_index,
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A.Nested", "pkg/models.py:B")),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == (
        SelectedRelation(
            source_class_id="pkg/models.py:A.Nested",
            target_class_id="pkg/models.py:B",
            relation_type="uses",
            evidence_kind="pydantic_forward_ref",
        ),
    )
    assert hints.warning_diagnostics == ()


def test_pydantic_annotated_metadata_string_does_not_warn(tmp_path: Path) -> None:
    project = tmp_path / "project"
    package = project / "pkg"
    seed = write_file(
        package / "models.py",
        "\n".join(
            [
                "from typing import Annotated",
                "from pydantic import BaseModel",
                "class A(BaseModel):",
                "    value: Annotated[int, \"label\"]",
                "class B:",
                "    pass",
            ]
        ),
    )
    parse_result = parse_target_set(target_set(seed), context(project, package_root=package), AnalysisConfig())

    hints = extract_pydantic_enrichment_hints(
        parsed_modules=parse_result.parsed_modules,
        module_index=parse_result.module_index,
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/models.py:B")),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == ()
    assert hints.warning_diagnostics == ()


def test_parse_to_pydantic_handoff_ignores_classvar_forward_ref_without_warning(tmp_path: Path) -> None:
    project = tmp_path / "project"
    package = project / "pkg"
    seed = write_file(
        package / "models.py",
        "\n".join(
            [
                "from typing import ClassVar",
                "from pydantic import BaseModel",
                "class A(BaseModel):",
                "    cache: ClassVar[\"B\"]",
                "class B:",
                "    pass",
            ]
        ),
    )
    parse_result = parse_target_set(target_set(seed), context(project, package_root=package), AnalysisConfig())

    hints = extract_pydantic_enrichment_hints(
        parsed_modules=parse_result.parsed_modules,
        module_index=parse_result.module_index,
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/models.py:B")),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == ()
    assert hints.warning_diagnostics == ()


def test_classvar_forward_ref_is_ignored_without_warning() -> None:
    hints = extract_pydantic_enrichment_hints(
        parsed_modules=(
            parsed_module(
                base_reference(),
                annotation_reference(target_name="B", reference_owner="ClassVar"),
            ),
        ),
        module_index=module_index("pkg/models.py:A", "pkg/models.py:B"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/models.py:B")),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == ()
    assert hints.warning_diagnostics == ()


def test_direct_quoted_forward_ref_adds_selected_relation_hint() -> None:
    hints = extract_pydantic_enrichment_hints(
        parsed_modules=(parsed_module(base_reference(), annotation_reference(target_name="B")),),
        module_index=module_index("pkg/models.py:A", "pkg/models.py:B"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/models.py:B")),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == (
        SelectedRelation(
            source_class_id="pkg/models.py:A",
            target_class_id="pkg/models.py:B",
            relation_type="uses",
            evidence_kind="pydantic_forward_ref",
        ),
    )
    assert hints.warning_diagnostics == ()


def test_analyze_association_suppresses_duplicate_pydantic_forward_ref_use() -> None:
    hints = extract_pydantic_enrichment_hints(
        parsed_modules=(
            parsed_module(
                base_reference(),
                ClassReference(
                    source_class_id="pkg/models.py:A",
                    target_name="B",
                    reference_kind="field_annotation",
                    reference_owner="child",
                ),
                annotation_reference(target_name="B"),
            ),
        ),
        module_index=module_index("pkg/models.py:A", "pkg/models.py:B"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/models.py:B")),
        selected_relations=SelectedRelations(
            (
                SelectedRelation(
                    source_class_id="pkg/models.py:A",
                    target_class_id="pkg/models.py:B",
                    relation_type="association",
                    evidence_kind="field_annotation",
                ),
            )
        ),
    )

    assert hints.added_relations == ()
    assert hints.warning_diagnostics == ()


def test_selected_inherits_endpoint_suppresses_duplicate_pydantic_forward_ref_use() -> None:
    hints = extract_pydantic_enrichment_hints(
        parsed_modules=(
            parsed_module(
                base_reference(),
                ClassReference(
                    source_class_id="pkg/models.py:A",
                    target_name="B",
                    reference_kind="field_annotation",
                    reference_owner="child",
                ),
                annotation_reference(target_name="B"),
            ),
        ),
        module_index=module_index("pkg/models.py:A", "pkg/models.py:B"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/models.py:B")),
        selected_relations=SelectedRelations(
            (
                SelectedRelation(
                    source_class_id="pkg/models.py:A",
                    target_class_id="pkg/models.py:B",
                    relation_type="inherits",
                    evidence_kind="class_base",
                ),
            )
        ),
    )

    assert hints.added_relations == ()
    assert hints.warning_diagnostics == ()


def test_semantic_field_evidence_suppresses_duplicate_pydantic_warning() -> None:
    hints = extract_pydantic_enrichment_hints(
        parsed_modules=(
            parsed_module(
                base_reference(),
                ClassReference(
                    source_class_id="pkg/models.py:A",
                    target_name="Missing",
                    reference_kind="field_annotation",
                    reference_owner="child",
                ),
                annotation_reference(target_name="Missing"),
            ),
        ),
        module_index=module_index("pkg/models.py:A"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A",)),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == ()
    assert hints.warning_diagnostics == ()


def test_pydantic_module_base_eligibility_adds_selected_relation_hint() -> None:
    hints = extract_pydantic_enrichment_hints(
        parsed_modules=(
            parsed_module(
                base_reference(target_name="pydantic.BaseModel"),
                annotation_reference(target_name="B"),
            ),
        ),
        module_index=module_index("pkg/models.py:A", "pkg/models.py:B"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/models.py:B")),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == (
        SelectedRelation(
            source_class_id="pkg/models.py:A",
            target_class_id="pkg/models.py:B",
            relation_type="uses",
            evidence_kind="pydantic_forward_ref",
        ),
    )
    assert hints.warning_diagnostics == ()


def test_quoted_subscript_forward_refs_add_one_hint_per_union_member() -> None:
    hints = extract_pydantic_enrichment_hints(
        parsed_modules=(
            parsed_module(
                base_reference(),
                annotation_reference(target_name="B", reference_owner="list"),
                annotation_reference(target_name="B", reference_owner="Optional"),
                annotation_reference(target_name="B", reference_owner="Union"),
                annotation_reference(target_name="C", reference_owner="Union"),
            ),
        ),
        module_index=module_index("pkg/models.py:A", "pkg/models.py:B", "pkg/models.py:C"),
        selected_classes=SelectedClasses(
            class_ids=("pkg/models.py:A", "pkg/models.py:B", "pkg/models.py:C")
        ),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == (
        SelectedRelation(
            source_class_id="pkg/models.py:A",
            target_class_id="pkg/models.py:B",
            relation_type="uses",
            evidence_kind="pydantic_forward_ref",
        ),
        SelectedRelation(
            source_class_id="pkg/models.py:A",
            target_class_id="pkg/models.py:C",
            relation_type="uses",
            evidence_kind="pydantic_forward_ref",
        ),
    )
    assert hints.warning_diagnostics == ()


def test_non_pydantic_quoted_annotation_is_ignored_without_warning() -> None:
    hints = extract_pydantic_enrichment_hints(
        parsed_modules=(parsed_module(annotation_reference(target_name="B")),),
        module_index=module_index("pkg/models.py:A", "pkg/models.py:B"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/models.py:B")),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == ()
    assert hints.warning_diagnostics == ()


def test_custom_base_quoted_annotation_is_ignored_without_warning() -> None:
    hints = extract_pydantic_enrichment_hints(
        parsed_modules=(
            parsed_module(
                base_reference(target_name="CustomBase"),
                annotation_reference(target_name="B"),
            ),
        ),
        module_index=module_index("pkg/models.py:A", "pkg/models.py:B"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/models.py:B")),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == ()
    assert hints.warning_diagnostics == ()


def test_unselected_source_reference_is_ignored_without_warning() -> None:
    hints = extract_pydantic_enrichment_hints(
        parsed_modules=(parsed_module(base_reference(), annotation_reference(target_name="B")),),
        module_index=module_index("pkg/models.py:A", "pkg/models.py:B"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:B",)),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == ()
    assert hints.warning_diagnostics == ()


def test_unresolved_forward_ref_warns_without_relation() -> None:
    hints = extract_pydantic_enrichment_hints(
        parsed_modules=(parsed_module(base_reference(), annotation_reference(target_name="Missing")),),
        module_index=module_index("pkg/models.py:A", "pkg/models.py:B"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/models.py:B")),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == ()
    assert [diagnostic.code for diagnostic in hints.warning_diagnostics] == [
        "pydantic_forward_ref_unresolved"
    ]
    assert_framework_warning_shape(hints.warning_diagnostics[0])


def test_ambiguous_forward_ref_warns_without_relation() -> None:
    hints = extract_pydantic_enrichment_hints(
        parsed_modules=(parsed_module(base_reference(), annotation_reference(target_name="B")),),
        module_index=module_index("pkg/models.py:A", "pkg/one.py:B", "pkg/two.py:B"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/one.py:B", "pkg/two.py:B")),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == ()
    assert [diagnostic.code for diagnostic in hints.warning_diagnostics] == [
        "pydantic_forward_ref_ambiguous"
    ]
    assert_framework_warning_shape(hints.warning_diagnostics[0])


def test_selection_outside_forward_ref_warns_without_relation() -> None:
    hints = extract_pydantic_enrichment_hints(
        parsed_modules=(parsed_module(base_reference(), annotation_reference(target_name="B")),),
        module_index=module_index("pkg/models.py:A", "pkg/models.py:B"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A",)),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == ()
    assert [diagnostic.code for diagnostic in hints.warning_diagnostics] == [
        "pydantic_forward_ref_selection_outside"
    ]
    assert_framework_warning_shape(hints.warning_diagnostics[0])


def test_mixed_selected_and_non_selected_collision_is_ambiguous() -> None:
    hints = extract_pydantic_enrichment_hints(
        parsed_modules=(parsed_module(base_reference(), annotation_reference(target_name="B")),),
        module_index=module_index("pkg/models.py:A", "pkg/selected.py:B", "pkg/not_selected.py:B"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/selected.py:B")),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == ()
    assert [diagnostic.code for diagnostic in hints.warning_diagnostics] == [
        "pydantic_forward_ref_ambiguous"
    ]
    assert_framework_warning_shape(hints.warning_diagnostics[0])


def test_module_qualified_target_adds_selected_relation_hint() -> None:
    hints = extract_pydantic_enrichment_hints(
        parsed_modules=(
            parsed_module(
                base_reference(),
                annotation_reference(target_name="pkg.models.B"),
            ),
        ),
        module_index=module_index("pkg/models.py:A", "pkg/models.py:B"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/models.py:B")),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == (
        SelectedRelation(
            source_class_id="pkg/models.py:A",
            target_class_id="pkg/models.py:B",
            relation_type="uses",
            evidence_kind="pydantic_forward_ref",
        ),
    )
    assert hints.warning_diagnostics == ()


def test_relation_hints_dedupe_existing_inventory_and_same_extraction_triples() -> None:
    existing_relation = SelectedRelation(
        source_class_id="pkg/models.py:A",
        target_class_id="pkg/models.py:B",
        relation_type="uses",
        evidence_kind="module_import",
    )

    existing_hints = extract_pydantic_enrichment_hints(
        parsed_modules=(parsed_module(base_reference(), annotation_reference(target_name="B")),),
        module_index=module_index("pkg/models.py:A", "pkg/models.py:B"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/models.py:B")),
        selected_relations=SelectedRelations((existing_relation,)),
    )
    same_extraction_hints = extract_pydantic_enrichment_hints(
        parsed_modules=(
            parsed_module(
                base_reference(),
                annotation_reference(target_name="B"),
                annotation_reference(target_name="B", reference_owner="list"),
            ),
        ),
        module_index=module_index("pkg/models.py:A", "pkg/models.py:B"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/models.py:B")),
        selected_relations=SelectedRelations(),
    )

    assert existing_hints.added_relations == ()
    assert existing_hints.warning_diagnostics == ()
    assert same_extraction_hints.added_relations == (
        SelectedRelation(
            source_class_id="pkg/models.py:A",
            target_class_id="pkg/models.py:B",
            relation_type="uses",
            evidence_kind="pydantic_forward_ref",
        ),
    )
    assert same_extraction_hints.warning_diagnostics == ()


def assert_framework_warning_shape(diagnostic) -> None:
    assert diagnostic.severity is DiagnosticSeverity.WARNING
    assert diagnostic.origin_seam is OriginSeam.FRAMEWORKS
    assert diagnostic.recoverability is Recoverability.DEGRADED_OUTPUT
    assert diagnostic.failure_reason is None
