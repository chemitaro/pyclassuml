from pathlib import Path

import pytest

from pyclassuml.analyze.selection import SelectedRelation, SelectedRelations
from pyclassuml.frameworks.sqlalchemy import extract_sqlalchemy_enrichment_hints
from pyclassuml.model import (
    AnalysisConfig,
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


def parsed_module(*references: ClassReference) -> ParsedModule:
    return ParsedModule(
        module_path=Path("pkg/models.py"),
        classes=("pkg/models.py:A", "pkg/models.py:B"),
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


def reference(
    *,
    target_name: str,
    reference_kind: str = "annotation_subscript",
    reference_owner: str = "Mapped",
) -> ClassReference:
    return ClassReference(
        source_class_id="pkg/models.py:A",
        target_name=target_name,
        reference_kind=reference_kind,
        reference_owner=reference_owner,
    )


def relationship_reference(*, target_name: str) -> ClassReference:
    return reference(
        target_name=target_name,
        reference_kind="call_string_arg",
        reference_owner="relationship",
    )


def test_parse_to_sqlalchemy_handoff_adds_mapped_and_relationship_string_hints(tmp_path: Path) -> None:
    project = tmp_path / "project"
    package = project / "pkg"
    seed = write_file(
        package / "models.py",
        "\n".join(
            [
                "from sqlalchemy.orm import Mapped, relationship",
                "class A:",
                "    b: Mapped[B]",
                "    c = relationship(\"C\")",
                "class B:",
                "    pass",
                "class C:",
                "    pass",
            ]
        ),
    )
    parse_result = parse_target_set(target_set(seed), context(project, package_root=package), AnalysisConfig())

    hints = extract_sqlalchemy_enrichment_hints(
        parsed_modules=parse_result.parsed_modules,
        module_index=parse_result.module_index,
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
            evidence_kind="sqlalchemy_mapped",
        ),
        SelectedRelation(
            source_class_id="pkg/models.py:A",
            target_class_id="pkg/models.py:C",
            relation_type="uses",
            evidence_kind="sqlalchemy_relationship_string",
        ),
    )
    assert hints.warning_diagnostics == ()


def test_mapped_reference_adds_selected_relation_hint() -> None:
    hints = extract_sqlalchemy_enrichment_hints(
        parsed_modules=(parsed_module(reference(target_name="B")),),
        module_index=module_index("pkg/models.py:A", "pkg/models.py:B"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/models.py:B")),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == (
        SelectedRelation(
            source_class_id="pkg/models.py:A",
            target_class_id="pkg/models.py:B",
            relation_type="uses",
            evidence_kind="sqlalchemy_mapped",
        ),
    )
    assert hints.warning_diagnostics == ()


def test_relationship_string_reference_adds_selected_relation_hint() -> None:
    hints = extract_sqlalchemy_enrichment_hints(
        parsed_modules=(
            parsed_module(
                reference(
                    target_name="B",
                    reference_kind="call_string_arg",
                    reference_owner="relationship",
                )
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
            evidence_kind="sqlalchemy_relationship_string",
        ),
    )
    assert hints.warning_diagnostics == ()


def test_relationship_string_can_resolve_fully_qualified_suffix() -> None:
    hints = extract_sqlalchemy_enrichment_hints(
        parsed_modules=(
            parsed_module(
                reference(
                    target_name="Outer.B",
                    reference_kind="call_string_arg",
                    reference_owner="relationship",
                )
            ),
        ),
        module_index=module_index("pkg/models.py:A", "pkg/models.py:Outer.B"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/models.py:Outer.B")),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == (
        SelectedRelation(
            source_class_id="pkg/models.py:A",
            target_class_id="pkg/models.py:Outer.B",
            relation_type="uses",
            evidence_kind="sqlalchemy_relationship_string",
        ),
    )


def test_relationship_string_can_resolve_module_qualified_target() -> None:
    hints = extract_sqlalchemy_enrichment_hints(
        parsed_modules=(
            parsed_module(
                reference(
                    target_name="pkg.models.B",
                    reference_kind="call_string_arg",
                    reference_owner="relationship",
                )
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
            evidence_kind="sqlalchemy_relationship_string",
        ),
    )
    assert hints.warning_diagnostics == ()


def test_relationship_string_can_resolve_module_qualified_suffix_target() -> None:
    hints = extract_sqlalchemy_enrichment_hints(
        parsed_modules=(
            parsed_module(
                reference(
                    target_name="models.B",
                    reference_kind="call_string_arg",
                    reference_owner="relationship",
                )
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
            evidence_kind="sqlalchemy_relationship_string",
        ),
    )
    assert hints.warning_diagnostics == ()


def test_unselected_source_reference_is_ignored_without_warning() -> None:
    hints = extract_sqlalchemy_enrichment_hints(
        parsed_modules=(
            ParsedModule(
                module_path=Path("pkg/models.py"),
                classes=("pkg/models.py:A", "pkg/models.py:B"),
                class_references=(
                    ClassReference(
                        source_class_id="pkg/models.py:A",
                        target_name="B",
                        reference_kind="annotation_subscript",
                        reference_owner="Mapped",
                    ),
                ),
            ),
        ),
        module_index=module_index("pkg/models.py:A", "pkg/models.py:B"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:B",)),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == ()
    assert hints.warning_diagnostics == ()


@pytest.mark.parametrize(
    "reference_evidence",
    (
        reference(target_name="Missing"),
        relationship_reference(target_name="Missing"),
    ),
    ids=("mapped", "relationship"),
)
def test_unresolved_reference_warns_without_relation(reference_evidence: ClassReference) -> None:
    hints = extract_sqlalchemy_enrichment_hints(
        parsed_modules=(parsed_module(reference_evidence),),
        module_index=module_index("pkg/models.py:A", "pkg/models.py:B"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/models.py:B")),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == ()
    assert [diagnostic.code for diagnostic in hints.warning_diagnostics] == ["sqlalchemy_relation_unresolved"]
    assert_framework_warning_shape(hints.warning_diagnostics[0])


@pytest.mark.parametrize(
    "reference_evidence",
    (
        reference(target_name="B"),
        relationship_reference(target_name="B"),
    ),
    ids=("mapped", "relationship"),
)
def test_ambiguous_reference_warns_without_relation(reference_evidence: ClassReference) -> None:
    hints = extract_sqlalchemy_enrichment_hints(
        parsed_modules=(parsed_module(reference_evidence),),
        module_index=module_index("pkg/models.py:A", "pkg/one.py:B", "pkg/two.py:B"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/one.py:B", "pkg/two.py:B")),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == ()
    assert [diagnostic.code for diagnostic in hints.warning_diagnostics] == ["sqlalchemy_relation_ambiguous"]
    assert_framework_warning_shape(hints.warning_diagnostics[0])


@pytest.mark.parametrize(
    "reference_evidence",
    (
        reference(target_name="B"),
        relationship_reference(target_name="B"),
    ),
    ids=("mapped", "relationship"),
)
def test_selection_outside_reference_warns_without_relation(reference_evidence: ClassReference) -> None:
    hints = extract_sqlalchemy_enrichment_hints(
        parsed_modules=(parsed_module(reference_evidence),),
        module_index=module_index("pkg/models.py:A", "pkg/models.py:B"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A",)),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == ()
    assert [diagnostic.code for diagnostic in hints.warning_diagnostics] == [
        "sqlalchemy_relation_selection_outside"
    ]
    assert_framework_warning_shape(hints.warning_diagnostics[0])


@pytest.mark.parametrize(
    "reference_evidence",
    (
        reference(target_name="B"),
        relationship_reference(target_name="B"),
    ),
    ids=("mapped", "relationship"),
)
def test_mixed_selected_and_non_selected_collision_is_ambiguous(reference_evidence: ClassReference) -> None:
    hints = extract_sqlalchemy_enrichment_hints(
        parsed_modules=(parsed_module(reference_evidence),),
        module_index=module_index("pkg/models.py:A", "pkg/selected.py:B", "pkg/not_selected.py:B"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/selected.py:B")),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == ()
    assert [diagnostic.code for diagnostic in hints.warning_diagnostics] == ["sqlalchemy_relation_ambiguous"]
    assert_framework_warning_shape(hints.warning_diagnostics[0])


def test_relation_hints_are_deduped_and_sorted() -> None:
    hints = extract_sqlalchemy_enrichment_hints(
        parsed_modules=(
            parsed_module(
                reference(
                    target_name="C",
                    reference_kind="call_string_arg",
                    reference_owner="relationship",
                ),
                reference(target_name="B"),
                reference(target_name="B"),
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
            evidence_kind="sqlalchemy_mapped",
        ),
        SelectedRelation(
            source_class_id="pkg/models.py:A",
            target_class_id="pkg/models.py:C",
            relation_type="uses",
            evidence_kind="sqlalchemy_relationship_string",
        ),
    )


def test_relation_hints_dedupe_mapped_and_relationship_same_relation_triple() -> None:
    hints = extract_sqlalchemy_enrichment_hints(
        parsed_modules=(
            parsed_module(
                reference(target_name="B"),
                reference(
                    target_name="B",
                    reference_kind="call_string_arg",
                    reference_owner="relationship",
                ),
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
            evidence_kind="sqlalchemy_mapped",
        ),
    )
    assert hints.warning_diagnostics == ()


def test_existing_relation_inventory_dedupes_by_relation_triple() -> None:
    existing_relation = SelectedRelation(
        source_class_id="pkg/models.py:A",
        target_class_id="pkg/models.py:B",
        relation_type="uses",
        evidence_kind="module_import",
    )

    hints = extract_sqlalchemy_enrichment_hints(
        parsed_modules=(
            parsed_module(
                reference(target_name="B"),
                reference(
                    target_name="B",
                    reference_kind="call_string_arg",
                    reference_owner="relationship",
                ),
            ),
        ),
        module_index=module_index("pkg/models.py:A", "pkg/models.py:B"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/models.py:B")),
        selected_relations=SelectedRelations((existing_relation,)),
    )

    assert hints.added_relations == ()
    assert hints.warning_diagnostics == ()


def test_non_sqlalchemy_reference_is_ignored() -> None:
    hints = extract_sqlalchemy_enrichment_hints(
        parsed_modules=(parsed_module(reference(target_name="B", reference_owner="Owner")),),
        module_index=module_index("pkg/models.py:A", "pkg/models.py:B"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/models.py:B")),
        selected_relations=SelectedRelations(),
    )

    assert hints.added_relations == ()
    assert hints.warning_diagnostics == ()


def assert_framework_warning_shape(diagnostic) -> None:
    assert diagnostic.severity is DiagnosticSeverity.WARNING
    assert diagnostic.origin_seam is OriginSeam.FRAMEWORKS
    assert diagnostic.recoverability is Recoverability.DEGRADED_OUTPUT
    assert diagnostic.failure_reason is None
