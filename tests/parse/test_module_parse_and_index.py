from pathlib import Path

import pytest

from pyclassuml.model import (
    AnalysisConfig,
    ClassMember,
    ClassReference,
    DiagnosticSeverity,
    ExecutionContext,
    FailureReason,
    MemberParameter,
    OriginSeam,
    Recoverability,
    TargetObservations,
    TargetSet,
)
from pyclassuml.parse import indexer
from pyclassuml.parse import parse_target_set


def write_file(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path.resolve()


def context(project_root: Path, *, package_root: Path | None = None, scope_root: Path | None = None) -> ExecutionContext:
    return ExecutionContext(
        execution_cwd=project_root.resolve(),
        project_root=project_root.resolve(),
        package_root=(package_root or project_root).resolve(),
        scope_root=(scope_root or project_root).resolve(),
    )


def target_set(*seed_files: Path) -> TargetSet:
    return TargetSet(seed_files=tuple(seed_files), observations=TargetObservations())


def compatibility_references(class_references: tuple[ClassReference, ...]) -> tuple[ClassReference, ...]:
    return tuple(
        sorted(
            (
                reference
                for reference in class_references
                if reference.reference_kind in {
                    "annotation_string",
                    "annotation_subscript",
                    "call_string_arg",
                    "class_base",
                }
            ),
            key=lambda reference: (
                reference.source_class_id,
                reference.target_name,
                reference.reference_kind,
                reference.reference_owner,
            ),
        )
    )


def semantic_references(class_references: tuple[ClassReference, ...]) -> tuple[ClassReference, ...]:
    return tuple(
        reference
        for reference in class_references
        if reference.reference_kind
        in {
            "class_base",
            "field_annotation",
            "init_field_annotation",
            "method_parameter_annotation",
            "method_return_annotation",
        }
    )


def test_seed_file_parse_builds_parsed_module_and_index(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "a.py",
        "\n".join(
            [
                "import pkg.b",
                "from pkg import c",
                "class A:",
                "    class Nested:",
                "        pass",
                "def factory():",
                "    class Local:",
                "        pass",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert result.diagnostics == ()
    assert result.observations.ignored_dependency_candidate_count == 0
    assert result.module_index.seed_project_relative_paths == (Path("pkg/a.py"),)
    assert [module.module_path for module in result.parsed_modules] == [Path("pkg/a.py")]
    module = result.parsed_modules[0]
    assert module.imports == ("from pkg import c", "pkg.b")
    assert module.classes == ("pkg/a.py:A", "pkg/a.py:A.Nested")
    assert result.module_index.module_by_path[Path("pkg/a.py")] is module
    assert result.module_index.project_relative_file_to_module == {Path("pkg/a.py"): Path("pkg/a.py")}
    assert result.module_index.class_to_module == {
        "pkg/a.py:A": Path("pkg/a.py"),
        "pkg/a.py:A.Nested": Path("pkg/a.py"),
    }


def test_class_members_are_extracted_in_source_order_with_method_modifiers(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "order.py",
        "\n".join(
            [
                "class Order(Base):",
                "    customer: Customer",
                "    status = 'draft'",
                "    @property",
                "    def total(self) -> Decimal:",
                "        pass",
                "    @classmethod",
                "    async def load(cls, key: Key) -> 'Order':",
                "        pass",
                "    @staticmethod",
                "    def make(value: Value) -> Result:",
                "        pass",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert result.parsed_modules[0].members == (
        ClassMember(
            owner_class_id="pkg/order.py:Order",
            name="customer",
            kind="field",
            visibility="public",
            annotation_text="Customer",
            source_order=1,
        ),
        ClassMember(
            owner_class_id="pkg/order.py:Order",
            name="status",
            kind="field",
            visibility="public",
            source_order=2,
        ),
        ClassMember(
            owner_class_id="pkg/order.py:Order",
            name="total",
            kind="method",
            visibility="public",
            return_annotation_text="Decimal",
            modifiers=("property",),
            source_order=3,
        ),
        ClassMember(
            owner_class_id="pkg/order.py:Order",
            name="load",
            kind="method",
            visibility="public",
            parameters=(MemberParameter(name="key", annotation_text="Key"),),
            return_annotation_text="'Order'",
            modifiers=("classmethod", "async"),
            source_order=4,
        ),
        ClassMember(
            owner_class_id="pkg/order.py:Order",
            name="make",
            kind="method",
            visibility="public",
            parameters=(MemberParameter(name="value", annotation_text="Value"),),
            return_annotation_text="Result",
            modifiers=("staticmethod",),
            source_order=5,
        ),
    )
    assert semantic_references(result.parsed_modules[0].class_references) == (
        ClassReference("pkg/order.py:Order", "Base", "class_base", "base"),
        ClassReference("pkg/order.py:Order", "Customer", "field_annotation", "customer"),
        ClassReference("pkg/order.py:Order", "Decimal", "method_return_annotation", "total"),
        ClassReference("pkg/order.py:Order", "Key", "method_parameter_annotation", "load.key"),
        ClassReference("pkg/order.py:Order", "Order", "method_return_annotation", "load"),
        ClassReference("pkg/order.py:Order", "Value", "method_parameter_annotation", "make.value"),
        ClassReference("pkg/order.py:Order", "Result", "method_return_annotation", "make"),
    )


def test_parsed_module_members_preserve_module_source_order_across_classes(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "order.py",
        "\n".join(
            [
                "class Z:",
                "    zed: Zed",
                "class A:",
                "    alpha: Alpha",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert result.parsed_modules[0].members == (
        ClassMember(
            owner_class_id="pkg/order.py:Z",
            name="zed",
            kind="field",
            visibility="public",
            annotation_text="Zed",
            source_order=1,
        ),
        ClassMember(
            owner_class_id="pkg/order.py:A",
            name="alpha",
            kind="field",
            visibility="public",
            annotation_text="Alpha",
            source_order=1,
        ),
    )


def test_parsed_module_members_preserve_source_order_across_nested_class_members(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "order.py",
        "\n".join(
            [
                "class A:",
                "    before: Before",
                "    class Nested:",
                "        nested: NestedType",
                "    def later(self) -> Later:",
                "        pass",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert result.parsed_modules[0].members == (
        ClassMember(
            owner_class_id="pkg/order.py:A",
            name="before",
            kind="field",
            visibility="public",
            annotation_text="Before",
            source_order=1,
        ),
        ClassMember(
            owner_class_id="pkg/order.py:A.Nested",
            name="nested",
            kind="field",
            visibility="public",
            annotation_text="NestedType",
            source_order=1,
        ),
        ClassMember(
            owner_class_id="pkg/order.py:A",
            name="later",
            kind="method",
            visibility="public",
            return_annotation_text="Later",
            source_order=2,
        ),
    )


def test_method_parameters_preserve_signature_order_with_varargs_and_kwargs(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "order.py",
        "class Order:\n    def f(self, x: X, *args: A, y: Y, **kw: K):\n        pass\n",
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert result.parsed_modules[0].members == (
        ClassMember(
            owner_class_id="pkg/order.py:Order",
            name="f",
            kind="method",
            visibility="public",
            parameters=(
                MemberParameter(name="x", annotation_text="X"),
                MemberParameter(name="args", annotation_text="A"),
                MemberParameter(name="y", annotation_text="Y"),
                MemberParameter(name="kw", annotation_text="K"),
            ),
            source_order=1,
        ),
    )


def test_init_direct_self_assignments_create_instance_fields_and_semantic_refs(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "order.py",
        "\n".join(
            [
                "class Order:",
                "    def __init__(self, customer: 'Customer', items: list['Item'], raw):",
                "        self.customer = customer",
                "        if raw:",
                "            self.items = items",
                "            def nested():",
                "                self.bad = customer",
                "            class Local:",
                "                self.bad = customer",
                "        for item in items:",
                "            self.raw = raw",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert result.parsed_modules[0].members == (
        ClassMember(
            owner_class_id="pkg/order.py:Order",
            name="__init__",
            kind="method",
            visibility="public",
            parameters=(
                MemberParameter(name="customer", annotation_text="'Customer'"),
                MemberParameter(name="items", annotation_text="list['Item']"),
                MemberParameter(name="raw"),
            ),
            source_order=1,
        ),
        ClassMember(
            owner_class_id="pkg/order.py:Order",
            name="customer",
            kind="field",
            visibility="public",
            annotation_text="'Customer'",
            source_order=2,
        ),
        ClassMember(
            owner_class_id="pkg/order.py:Order",
            name="items",
            kind="field",
            visibility="public",
            annotation_text="list['Item']",
            source_order=3,
        ),
        ClassMember(
            owner_class_id="pkg/order.py:Order",
            name="raw",
            kind="field",
            visibility="public",
            source_order=4,
        ),
    )
    assert semantic_references(result.parsed_modules[0].class_references) == (
        ClassReference("pkg/order.py:Order", "Customer", "method_parameter_annotation", "__init__.customer"),
        ClassReference("pkg/order.py:Order", "Item", "method_parameter_annotation", "__init__.items"),
        ClassReference("pkg/order.py:Order", "Customer", "init_field_annotation", "customer"),
        ClassReference("pkg/order.py:Order", "Item", "init_field_annotation", "items"),
    )
    assert "bad" not in {member.name for member in result.parsed_modules[0].members}
    assert not any(
        reference.reference_kind == "init_field_annotation" and reference.reference_owner == "bad"
        for reference in result.parsed_modules[0].class_references
    )


def test_init_vararg_and_kwarg_annotations_feed_instance_fields_and_refs(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "order.py",
        "\n".join(
            [
                "class Order:",
                "    def __init__(self, *items: Item, **metadata: Metadata):",
                "        self.items = items",
                "        self.metadata = metadata",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert result.parsed_modules[0].members == (
        ClassMember(
            owner_class_id="pkg/order.py:Order",
            name="__init__",
            kind="method",
            visibility="public",
            parameters=(
                MemberParameter(name="items", annotation_text="Item"),
                MemberParameter(name="metadata", annotation_text="Metadata"),
            ),
            source_order=1,
        ),
        ClassMember(
            owner_class_id="pkg/order.py:Order",
            name="items",
            kind="field",
            visibility="public",
            annotation_text="Item",
            source_order=2,
        ),
        ClassMember(
            owner_class_id="pkg/order.py:Order",
            name="metadata",
            kind="field",
            visibility="public",
            annotation_text="Metadata",
            source_order=3,
        ),
    )
    assert semantic_references(result.parsed_modules[0].class_references) == (
        ClassReference("pkg/order.py:Order", "Item", "method_parameter_annotation", "__init__.items"),
        ClassReference("pkg/order.py:Order", "Metadata", "method_parameter_annotation", "__init__.metadata"),
        ClassReference("pkg/order.py:Order", "Item", "init_field_annotation", "items"),
        ClassReference("pkg/order.py:Order", "Metadata", "init_field_annotation", "metadata"),
    )


def test_init_direct_self_assignments_create_fields_for_non_name_rhs_without_param_annotations(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "order.py",
        "\n".join(
            [
                "class Order:",
                "    def __init__(self, id: Id):",
                "        self.id = uuid4()",
                "        self.enabled = True",
                "        self.param_id = id",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert result.parsed_modules[0].members == (
        ClassMember(
            owner_class_id="pkg/order.py:Order",
            name="__init__",
            kind="method",
            visibility="public",
            parameters=(MemberParameter(name="id", annotation_text="Id"),),
            source_order=1,
        ),
        ClassMember(
            owner_class_id="pkg/order.py:Order",
            name="id",
            kind="field",
            visibility="public",
            source_order=2,
        ),
        ClassMember(
            owner_class_id="pkg/order.py:Order",
            name="enabled",
            kind="field",
            visibility="public",
            source_order=3,
        ),
        ClassMember(
            owner_class_id="pkg/order.py:Order",
            name="param_id",
            kind="field",
            visibility="public",
            annotation_text="Id",
            source_order=4,
        ),
    )
    assert semantic_references(result.parsed_modules[0].class_references) == (
        ClassReference("pkg/order.py:Order", "Id", "method_parameter_annotation", "__init__.id"),
        ClassReference("pkg/order.py:Order", "Id", "init_field_annotation", "param_id"),
    )


def test_init_direct_self_assignments_under_while_and_try_create_instance_fields_and_refs(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "order.py",
        "\n".join(
            [
                "class Order:",
                "    def __init__(",
                "        self, ready: bool, retry: RetryPolicy, primary: PrimaryItem, fallback: FallbackItem",
                "    ):",
                "        while ready:",
                "            self.retry = retry",
                "            break",
                "        try:",
                "            self.primary = primary",
                "        except ValueError:",
                "            self.fallback = fallback",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert result.parsed_modules[0].members == (
        ClassMember(
            owner_class_id="pkg/order.py:Order",
            name="__init__",
            kind="method",
            visibility="public",
            parameters=(
                MemberParameter(name="ready", annotation_text="bool"),
                MemberParameter(name="retry", annotation_text="RetryPolicy"),
                MemberParameter(name="primary", annotation_text="PrimaryItem"),
                MemberParameter(name="fallback", annotation_text="FallbackItem"),
            ),
            source_order=1,
        ),
        ClassMember(
            owner_class_id="pkg/order.py:Order",
            name="retry",
            kind="field",
            visibility="public",
            annotation_text="RetryPolicy",
            source_order=2,
        ),
        ClassMember(
            owner_class_id="pkg/order.py:Order",
            name="primary",
            kind="field",
            visibility="public",
            annotation_text="PrimaryItem",
            source_order=3,
        ),
        ClassMember(
            owner_class_id="pkg/order.py:Order",
            name="fallback",
            kind="field",
            visibility="public",
            annotation_text="FallbackItem",
            source_order=4,
        ),
    )
    assert tuple(
        reference
        for reference in result.parsed_modules[0].class_references
        if reference.reference_kind == "init_field_annotation"
    ) == (
        ClassReference("pkg/order.py:Order", "RetryPolicy", "init_field_annotation", "retry"),
        ClassReference("pkg/order.py:Order", "PrimaryItem", "init_field_annotation", "primary"),
        ClassReference("pkg/order.py:Order", "FallbackItem", "init_field_annotation", "fallback"),
    )


def test_non_init_self_assignment_does_not_create_instance_field_or_init_field_ref(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "order.py",
        "\n".join(
            [
                "class Order:",
                "    def set_customer(self, customer: Customer):",
                "        self.customer = customer",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert result.parsed_modules[0].members == (
        ClassMember(
            owner_class_id="pkg/order.py:Order",
            name="set_customer",
            kind="method",
            visibility="public",
            parameters=(MemberParameter(name="customer", annotation_text="Customer"),),
            source_order=1,
        ),
    )
    assert semantic_references(result.parsed_modules[0].class_references) == (
        ClassReference("pkg/order.py:Order", "Customer", "method_parameter_annotation", "set_customer.customer"),
    )


def test_annotation_text_degrades_to_warning_when_stable_text_conversion_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    seed = write_file(project / "pkg" / "a.py", "class A:\n    field: Broken\n")
    original_unparse = indexer.ast.unparse

    def raising_unparse(node):
        if isinstance(node, indexer.ast.Name) and node.id == "Broken":
            raise ValueError("unstable")
        return original_unparse(node)

    monkeypatch.setattr(indexer.ast, "unparse", raising_unparse)

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert result.parsed_modules[0].members == (
        ClassMember(
            owner_class_id="pkg/a.py:A",
            name="field",
            kind="field",
            visibility="public",
            annotation_text=None,
            source_order=1,
        ),
    )
    assert len(result.parsed_modules[0].diagnostics) == 1
    diagnostic = result.parsed_modules[0].diagnostics[0]
    assert diagnostic.code == "annotation_text_unavailable"
    assert diagnostic.severity is DiagnosticSeverity.WARNING
    assert diagnostic.origin_seam is OriginSeam.PARSE
    assert diagnostic.recoverability is Recoverability.DEGRADED_OUTPUT
    assert diagnostic.failure_reason is None
    assert semantic_references(result.parsed_modules[0].class_references) == ()


def test_method_annotation_text_degrade_emits_one_warning_per_parameter_or_return(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    seed = write_file(project / "pkg" / "a.py", "class A:\n    def f(self, x: Broken) -> Broken:\n        pass\n")
    original_unparse = indexer.ast.unparse

    def raising_unparse(node):
        if isinstance(node, indexer.ast.Name) and node.id == "Broken":
            raise ValueError("unstable")
        return original_unparse(node)

    monkeypatch.setattr(indexer.ast, "unparse", raising_unparse)

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert result.parsed_modules[0].members == (
        ClassMember(
            owner_class_id="pkg/a.py:A",
            name="f",
            kind="method",
            visibility="public",
            parameters=(MemberParameter(name="x", annotation_text=None),),
            return_annotation_text=None,
            source_order=1,
        ),
    )
    assert [diagnostic.code for diagnostic in result.parsed_modules[0].diagnostics] == [
        "annotation_text_unavailable",
        "annotation_text_unavailable",
    ]
    assert semantic_references(result.parsed_modules[0].class_references) == ()


def test_init_parameter_annotation_degrade_reuse_emits_one_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    seed = write_file(project / "pkg" / "a.py", "class A:\n    def __init__(self, x: Broken):\n        self.x = x\n")
    original_unparse = indexer.ast.unparse

    def raising_unparse(node):
        if isinstance(node, indexer.ast.Name) and node.id == "Broken":
            raise ValueError("unstable")
        return original_unparse(node)

    monkeypatch.setattr(indexer.ast, "unparse", raising_unparse)

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert result.parsed_modules[0].members == (
        ClassMember(
            owner_class_id="pkg/a.py:A",
            name="__init__",
            kind="method",
            visibility="public",
            parameters=(MemberParameter(name="x", annotation_text=None),),
            source_order=1,
        ),
        ClassMember(
            owner_class_id="pkg/a.py:A",
            name="x",
            kind="field",
            visibility="public",
            annotation_text=None,
            source_order=2,
        ),
    )
    assert [diagnostic.code for diagnostic in result.parsed_modules[0].diagnostics] == [
        "annotation_text_unavailable",
    ]
    assert semantic_references(result.parsed_modules[0].class_references) == ()


def test_class_body_references_are_generic_and_deterministic(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "a.py",
        "\n".join(
            [
                "class A:",
                "    one: Owner[B]",
                "    many: Owner[list[C]]",
                "    link = link_to(\"D\")",
                "    def factory(self):",
                "        local: Owner[Local]",
                "        other = link_to(\"Local\")",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert compatibility_references(result.parsed_modules[0].class_references) == (
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="B",
            reference_kind="annotation_subscript",
            reference_owner="Owner",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="C",
            reference_kind="annotation_subscript",
            reference_owner="Owner",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="D",
            reference_kind="call_string_arg",
            reference_owner="link_to",
        ),
    )


def test_raw_class_references_are_ordered_by_source_position_before_lexical_fields(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "a.py",
        "\n".join(
            [
                "class A:",
                "    zed: Zed",
                "    alpha = link_to(\"Alpha\")",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert result.parsed_modules[0].class_references == (
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="Zed",
            reference_kind="field_annotation",
            reference_owner="zed",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="Alpha",
            reference_kind="call_string_arg",
            reference_owner="link_to",
        ),
    )


def test_class_base_references_are_generic_and_deterministic(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "a.py",
        "\n".join(
            [
                "class A(BaseModel):",
                "    pass",
                "class B(pydantic.BaseModel):",
                "    pass",
                "class C(CustomBase):",
                "    pass",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert compatibility_references(result.parsed_modules[0].class_references) == (
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="BaseModel",
            reference_kind="class_base",
            reference_owner="base",
        ),
        ClassReference(
            source_class_id="pkg/a.py:B",
            target_name="pydantic.BaseModel",
            reference_kind="class_base",
            reference_owner="base",
        ),
        ClassReference(
            source_class_id="pkg/a.py:C",
            target_name="CustomBase",
            reference_kind="class_base",
            reference_owner="base",
        ),
    )


def test_generic_class_base_references_use_direct_base_name(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "a.py",
        "\n".join(
            [
                "class A(CustomBase[T]):",
                "    pass",
                "class B(BaseModel[T]):",
                "    pass",
                "class C(pydantic.BaseModel[T]):",
                "    pass",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert compatibility_references(result.parsed_modules[0].class_references) == (
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="CustomBase",
            reference_kind="class_base",
            reference_owner="base",
        ),
        ClassReference(
            source_class_id="pkg/a.py:B",
            target_name="BaseModel",
            reference_kind="class_base",
            reference_owner="base",
        ),
        ClassReference(
            source_class_id="pkg/a.py:C",
            target_name="pydantic.BaseModel",
            reference_kind="class_base",
            reference_owner="base",
        ),
    )


def test_quoted_annotation_references_are_generic_and_owner_scoped(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "a.py",
        "\n".join(
            [
                "class A:",
                "    direct: \"B\"",
                "    many: list[\"C\"]",
                "    optional: Optional[\"D\"]",
                "    union: Union[\"E\", \"F\"]",
                "    literal: Literal[\"Ignored\"]",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert compatibility_references(result.parsed_modules[0].class_references) == (
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="B",
            reference_kind="annotation_string",
            reference_owner="annotation",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="C",
            reference_kind="annotation_string",
            reference_owner="list",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="C",
            reference_kind="annotation_subscript",
            reference_owner="list",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="D",
            reference_kind="annotation_string",
            reference_owner="Optional",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="D",
            reference_kind="annotation_subscript",
            reference_owner="Optional",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="E",
            reference_kind="annotation_string",
            reference_owner="Union",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="E",
            reference_kind="annotation_subscript",
            reference_owner="Union",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="F",
            reference_kind="annotation_string",
            reference_owner="Union",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="F",
            reference_kind="annotation_subscript",
            reference_owner="Union",
        ),
    )


def test_whole_string_quoted_container_annotations_emit_member_targets(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "a.py",
        "\n".join(
            [
                "class A:",
                "    many: \"list['Item']\"",
                "    maybe: \"Optional[Item]\"",
                "    literal: \"Literal['Ignored']\"",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert compatibility_references(result.parsed_modules[0].class_references) == (
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="Item",
            reference_kind="annotation_string",
            reference_owner="Optional",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="Item",
            reference_kind="annotation_string",
            reference_owner="list",
        ),
    )
    assert semantic_references(result.parsed_modules[0].class_references) == (
        ClassReference("pkg/a.py:A", "Item", "field_annotation", "many"),
        ClassReference("pkg/a.py:A", "Item", "field_annotation", "maybe"),
    )


def test_semantic_pydantic_container_field_references_include_eligible_base_forms(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "models.py",
        "\n".join(
            [
                "from typing import Literal, Optional, Union",
                "from pydantic import BaseModel",
                "import pydantic",
                "class Direct(BaseModel):",
                "    items: list[\"Item\"]",
                "    maybe: Optional[\"Item\"]",
                "    literal: Literal[\"Ignored\"]",
                "class Qualified(pydantic.BaseModel):",
                "    union: Union[\"A\", \"B\"]",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert semantic_references(result.parsed_modules[0].class_references) == (
        ClassReference("pkg/models.py:Direct", "BaseModel", "class_base", "base"),
        ClassReference("pkg/models.py:Direct", "Item", "field_annotation", "items"),
        ClassReference("pkg/models.py:Direct", "Item", "field_annotation", "maybe"),
        ClassReference("pkg/models.py:Qualified", "pydantic.BaseModel", "class_base", "base"),
        ClassReference("pkg/models.py:Qualified", "A", "field_annotation", "union"),
        ClassReference("pkg/models.py:Qualified", "B", "field_annotation", "union"),
    )


def test_annotated_metadata_strings_are_not_annotation_string_references(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "a.py",
        "\n".join(
            [
                "class A:",
                "    direct: Annotated[\"B\", \"label\"]",
                "    builtin: Annotated[int, \"label\"]",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    annotation_string_references = tuple(
        reference
        for reference in result.parsed_modules[0].class_references
        if reference.reference_kind == "annotation_string"
    )

    assert annotation_string_references == (
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="B",
            reference_kind="annotation_string",
            reference_owner="Annotated",
        ),
    )


def test_quoted_annotation_references_skip_nested_bodies(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "a.py",
        "\n".join(
            [
                "class A:",
                "    if True:",
                "        direct: \"B\"",
                "        def factory(self):",
                "            local: \"NestedFunction\"",
                "        async def async_factory(self):",
                "            local: \"NestedAsyncFunction\"",
                "        class Nested:",
                "            local: \"NestedClass\"",
                "        factory = lambda: list[\"LambdaBody\"]",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert compatibility_references(result.parsed_modules[0].class_references) == (
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="B",
            reference_kind="annotation_string",
            reference_owner="annotation",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A.Nested",
            target_name="NestedClass",
            reference_kind="annotation_string",
            reference_owner="annotation",
        ),
    )


def test_nested_class_references_use_nested_source_class_id(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "a.py",
        "\n".join(
            [
                "class A:",
                "    class Nested:",
                "        relation: Owner[B]",
                "        child: \"B\"",
                "        link = link_to(\"C\")",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert compatibility_references(result.parsed_modules[0].class_references) == (
        ClassReference(
            source_class_id="pkg/a.py:A.Nested",
            target_name="B",
            reference_kind="annotation_string",
            reference_owner="annotation",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A.Nested",
            target_name="B",
            reference_kind="annotation_subscript",
            reference_owner="Owner",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A.Nested",
            target_name="C",
            reference_kind="call_string_arg",
            reference_owner="link_to",
        ),
    )


def test_class_body_references_skip_nested_function_bodies_under_statements(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "a.py",
        "\n".join(
            [
                "class A:",
                "    if True:",
                "        def factory(self):",
                "            local = link_to(\"Local\")",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert result.parsed_modules[0].class_references == ()


def test_class_body_references_skip_lambda_bodies(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "a.py",
        "\n".join(
            [
                "class A:",
                "    factory = lambda: link_to(\"B\")",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert result.parsed_modules[0].class_references == ()


def test_class_body_references_include_annotation_under_control_statement(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "a.py",
        "\n".join(
            [
                "class A:",
                "    if True:",
                "        b: Owner[B]",
                "        def factory(self):",
                "            local: Owner[Local]",
                "        class Nested:",
                "            pass",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert compatibility_references(result.parsed_modules[0].class_references) == (
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="B",
            reference_kind="annotation_subscript",
            reference_owner="Owner",
        ),
    )


def test_mapped_annotation_references_ignore_typing_wrappers(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "a.py",
        "\n".join(
            [
                "class A:",
                "    optional: Mapped[Optional[B]]",
                "    union: Mapped[Union[B, C]]",
                "    annotated: Mapped[Annotated[B, \"primary\"]]",
                "    class_var: Mapped[ClassVar[C]]",
                "    final: Mapped[Final[B]]",
                "    literal: Mapped[Literal[\"B\"]]",
                "    required: Mapped[Required[B]]",
                "    not_required: Mapped[NotRequired[C]]",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert compatibility_references(result.parsed_modules[0].class_references) == (
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="B",
            reference_kind="annotation_subscript",
            reference_owner="Mapped",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="C",
            reference_kind="annotation_subscript",
            reference_owner="Mapped",
        ),
    )


def test_import_candidates_are_parsed_recursively_and_indexed_deterministically(tmp_path: Path) -> None:
    project = tmp_path / "project"
    package = project / "pkg"
    seed = write_file(package / "a.py", "from . import b\nclass A: pass\n")
    dependency_b = write_file(package / "b.py", "from pkg.sub import c\nclass B: pass\n")
    dependency_c = write_file(package / "sub" / "c.py", "class C: pass\n")

    result = parse_target_set(target_set(seed), context(project, package_root=package), AnalysisConfig())

    assert result.diagnostics == ()
    assert [module.module_path for module in result.parsed_modules] == [
        Path("pkg/a.py"),
        Path("pkg/b.py"),
        Path("pkg/sub/c.py"),
    ]
    assert result.module_index.import_candidate_paths == {
        "from . import b": (Path("pkg/b.py"),),
        "from pkg.sub import c": (Path("pkg/sub/c.py"),),
    }
    assert result.module_index.module_by_path[Path("pkg/b.py")].classes == ("pkg/b.py:B",)
    assert result.module_index.module_by_path[Path("pkg/sub/c.py")].classes == ("pkg/sub/c.py:C",)
    assert result.module_index.project_relative_file_to_module == {
        dependency_b.relative_to(project): Path("pkg/b.py"),
        dependency_c.relative_to(project): Path("pkg/sub/c.py"),
        seed.relative_to(project): Path("pkg/a.py"),
    }


def test_syntax_error_dependency_is_excluded_from_parsed_modules_and_indexes(tmp_path: Path) -> None:
    project = tmp_path / "project"
    package = project / "pkg"
    seed = write_file(package / "a.py", "from . import broken\nclass A: pass\n")
    write_file(package / "broken.py", "class Broken(:\n")

    result = parse_target_set(target_set(seed), context(project, package_root=package), AnalysisConfig())

    assert [module.module_path for module in result.parsed_modules] == [Path("pkg/a.py")]
    assert Path("pkg/broken.py") not in result.module_index.module_by_path
    assert Path("pkg/broken.py") not in result.module_index.project_relative_file_to_module
    assert result.module_index.class_to_module == {"pkg/a.py:A": Path("pkg/a.py")}
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "bad_syntax"
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.origin_seam is OriginSeam.PARSE
    assert diagnostic.recoverability is Recoverability.DEGRADED_OUTPUT
    assert diagnostic.failure_reason is FailureReason.STRICT_SYNTAX_ERROR
    assert "pkg/broken.py" in diagnostic.message


def test_ignored_dependency_candidate_is_not_parsed_and_is_counted(tmp_path: Path) -> None:
    project = tmp_path / "project"
    package = project / "pkg"
    seed = write_file(package / "a.py", "from pkg.generated import skip\nclass A: pass\n")
    write_file(package / "generated" / "skip.py", "class Skip: pass\n")

    result = parse_target_set(
        target_set(seed),
        context(project, package_root=package),
        AnalysisConfig(ignore=("pkg/generated/**",)),
    )

    assert [module.module_path for module in result.parsed_modules] == [Path("pkg/a.py")]
    assert result.module_index.import_candidate_paths == {}
    assert result.observations.ignored_dependency_candidate_count == 1
    assert Path("pkg/generated/skip.py") not in result.module_index.module_by_path


def test_default_ignored_dependency_candidate_is_not_parsed_and_is_counted(tmp_path: Path) -> None:
    project = tmp_path / "project"
    package = project / "pkg"
    seed = write_file(package / "a.py", "import venv.vendor\nclass A: pass\n")
    write_file(project / "venv" / "vendor.py", "class Vendor: pass\n")

    result = parse_target_set(
        target_set(seed),
        context(project, package_root=project),
        AnalysisConfig(),
    )

    assert [module.module_path for module in result.parsed_modules] == [Path("pkg/a.py")]
    assert result.module_index.import_candidate_paths == {}
    assert result.observations.ignored_dependency_candidate_count == 1
    assert Path("venv/vendor.py") not in result.module_index.module_by_path


def test_boundary_candidates_are_lookup_material_without_package_external_parse(tmp_path: Path) -> None:
    project = tmp_path / "project"
    package = project / "pkg"
    scope = package / "app"
    seed = write_file(scope / "a.py", "from pkg import shared\nimport tools.helper\nclass A: pass\n")
    write_file(package / "shared.py", "class Shared: pass\n")
    write_file(project / "tools" / "helper.py", "class Helper: pass\n")

    result = parse_target_set(
        target_set(seed),
        context(project, package_root=package, scope_root=scope),
        AnalysisConfig(),
    )

    assert result.module_index.import_candidate_paths == {
        "from pkg import shared": (Path("pkg/shared.py"),),
        "tools.helper": (Path("tools/helper.py"),),
    }
    assert [module.module_path for module in result.parsed_modules] == [
        Path("pkg/app/a.py"),
        Path("pkg/shared.py"),
    ]
    assert Path("tools/helper.py") not in result.module_index.module_by_path
