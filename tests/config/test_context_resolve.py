from pathlib import Path

import pytest

from pyclassuml.cli import bind_command_request
from pyclassuml.config import ConfigResolution, resolve_context
from pyclassuml.model import (
    AnalysisConfig,
    AnalysisMode,
    CommandName,
    CommandOptions,
    CommandRequest,
    DiagnosticSeverity,
    DiffCurrentState,
    DiffOptions,
    ExecutionContext,
    FailureReason,
    GenerateOptions,
    OriginSeam,
    Recoverability,
)


def generate_request(process_cwd: Path, **overrides: object) -> CommandRequest:
    kwargs: dict[str, object] = {
        "command": CommandName.GENERATE,
        "generate": GenerateOptions(targets=("pkg.module:Class",)),
    }
    kwargs.update(overrides)
    return CommandRequest(process_cwd=process_cwd, cli_options=CommandOptions(**kwargs))


def diff_request(process_cwd: Path, **overrides: object) -> CommandRequest:
    kwargs: dict[str, object] = {
        "command": CommandName.DIFF,
        "diff": DiffOptions(
            base_ref="main",
            current_state=DiffCurrentState.WORKING_TREE,
            include_untracked=False,
        ),
    }
    kwargs.update(overrides)
    return CommandRequest(process_cwd=process_cwd, cli_options=CommandOptions(**kwargs))


def write_config(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def assert_success(result: ConfigResolution) -> tuple[ExecutionContext, AnalysisConfig]:
    assert result.diagnostics == ()
    assert result.context is not None
    assert result.analysis_config is not None
    return result.context, result.analysis_config


def assert_failure(
    result: ConfigResolution,
    reason: FailureReason,
    *,
    code: str | None = None,
    message_contains: str | None = None,
) -> None:
    assert result.context is None
    assert result.analysis_config is None
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.origin_seam is OriginSeam.CONFIG
    assert diagnostic.recoverability is Recoverability.FATAL
    assert diagnostic.failure_reason is reason
    if code is not None:
        assert diagnostic.code == code
    if message_contains is not None:
        assert message_contains in diagnostic.message


def test_default_no_config_resolves_context_and_default_analysis_config(tmp_path: Path) -> None:
    result = resolve_context(generate_request(tmp_path))

    context, config = assert_success(result)
    assert context == ExecutionContext(
        execution_cwd=tmp_path.resolve(),
        project_root=tmp_path.resolve(),
        package_root=tmp_path.resolve(),
        scope_root=tmp_path.resolve(),
    )
    assert config == AnalysisConfig()


def test_diff_default_depth_is_one_without_cli_or_config(tmp_path: Path) -> None:
    _, config = assert_success(resolve_context(diff_request(tmp_path)))

    assert config.depth == 1


def test_generate_default_depth_is_none_without_cli_or_config(tmp_path: Path) -> None:
    _, config = assert_success(resolve_context(generate_request(tmp_path)))

    assert config.depth is None


def test_cwd_is_resolved_relative_to_process_cwd(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()

    context, _ = assert_success(resolve_context(generate_request(tmp_path, cwd=Path("work"))))

    assert context.execution_cwd == work.resolve()
    assert context.project_root == work.resolve()


def test_project_root_config_discovery_takes_priority_over_parent_search(tmp_path: Path) -> None:
    execution = tmp_path / "repo" / "pkg"
    project = tmp_path / "chosen"
    fallback_project = tmp_path / "repo"
    for path in (execution, project / "src", fallback_project / "src"):
        path.mkdir(parents=True)
    write_config(
        project / ".pyclassuml.toml",
        """
package_root = "src"
depth = 1
""",
    )
    write_config(
        fallback_project / ".pyclassuml.toml",
        """
package_root = "src"
depth = 9
""",
    )

    context, config = assert_success(resolve_context(generate_request(execution, project_root=project)))

    assert context.project_root == project.resolve()
    assert context.package_root == (project / "src").resolve()
    assert config.depth == 1


def test_project_root_discovery_falls_back_to_execution_cwd_parent_search(tmp_path: Path) -> None:
    explicit_project = tmp_path / "project"
    execution = explicit_project / "pkg"
    package = explicit_project / "src"
    for path in (execution, package):
        path.mkdir(parents=True)
    write_config(
        execution / ".pyclassuml.toml",
        """
package_root = "../src"
depth = 4
""",
    )

    context, config = assert_success(resolve_context(generate_request(execution, project_root=explicit_project)))

    assert context.project_root == explicit_project.resolve()
    assert context.package_root == package.resolve()
    assert config.depth == 4


def test_explicit_project_root_overrides_conflicting_fallback_config_project_root(tmp_path: Path) -> None:
    fallback_project = tmp_path / "repo"
    explicit_project = fallback_project / "project"
    execution = fallback_project / "work"
    conflicting_project = fallback_project / "conflicting"
    package = explicit_project / "src"
    for path in (execution, package, conflicting_project):
        path.mkdir(parents=True)
    write_config(
        fallback_project / ".pyclassuml.toml",
        """
project_root = "conflicting"
package_root = "project/src"
depth = 5
""",
    )

    context, config = assert_success(resolve_context(generate_request(execution, project_root=explicit_project)))

    assert context.project_root == explicit_project.resolve()
    assert context.package_root == package.resolve()
    assert context.scope_root == package.resolve()
    assert config.depth == 5


def test_config_file_directory_is_project_root_fallback(tmp_path: Path) -> None:
    package = tmp_path / "src"
    package.mkdir()
    write_config(tmp_path / ".pyclassuml.toml", 'package_root = "src"\n')

    context, _ = assert_success(resolve_context(generate_request(tmp_path / "src")))

    assert context.project_root == tmp_path.resolve()
    assert context.package_root == package.resolve()
    assert context.scope_root == package.resolve()


def test_relative_path_base_cwd_resolves_config_paths_from_execution_cwd(tmp_path: Path) -> None:
    config_dir = tmp_path / "config_dir"
    execution = tmp_path / "work"
    project = execution / "project"
    package = project / "pkg"
    package.mkdir(parents=True)
    config_dir.mkdir()
    write_config(
        config_dir / "settings.toml",
        """
relative_path_base = "cwd"
project_root = "project"
package_root = "project/pkg"
output = "out/diagram.puml"
""",
    )

    context, config = assert_success(
        resolve_context(generate_request(execution, config=Path("../config_dir/settings.toml")))
    )

    assert context.project_root == project.resolve()
    assert context.package_root == package.resolve()
    assert config.output == (execution / "out" / "diagram.puml").resolve()


def test_generate_command_section_overrides_all_common_values(tmp_path: Path) -> None:
    common_project = tmp_path / "common"
    command_project = tmp_path / "command"
    for project in (common_project, command_project):
        (project / "pkg" / "scope").mkdir(parents=True)
    write_config(
        tmp_path / ".pyclassuml.toml",
        """
project_root = "common"
package_root = "common/pkg"
scope_root = "common/pkg/scope"
output = "common.puml"
ignore = ["common"]
depth = 4
mode = "strict"
target_python = "3.10"

[generate]
project_root = "command"
package_root = "command/pkg"
scope_root = "command/pkg/scope"
output = "command.puml"
ignore = []
depth = 0
mode = "warn"
target_python = "3.11"
[diff]
current_state = "head"
include_untracked = false
""",
    )

    context, config = assert_success(resolve_context(generate_request(tmp_path)))

    assert context.project_root == command_project.resolve()
    assert context.package_root == (command_project / "pkg").resolve()
    assert context.scope_root == (command_project / "pkg" / "scope").resolve()
    assert config.output == (tmp_path / "command.puml").resolve()
    assert config.ignore == ()
    assert config.depth == 0
    assert config.mode is AnalysisMode.WARN
    assert config.target_python == "3.11"
    assert config.diff_current_state is DiffCurrentState.HEAD
    assert config.diff_include_untracked is False


def test_diff_command_section_overrides_common_and_diff_specific_values(
    tmp_path: Path,
) -> None:
    common_project = tmp_path / "common"
    diff_project = tmp_path / "diff"
    for project in (common_project, diff_project):
        (project / "pkg" / "scope").mkdir(parents=True)
    write_config(
        tmp_path / ".pyclassuml.toml",
        """
project_root = "common"
package_root = "common/pkg"
scope_root = "common/pkg/scope"
output = "common.puml"
ignore = ["common"]
depth = 4
mode = "strict"
target_python = "3.10"

[diff]
project_root = "diff"
package_root = "diff/pkg"
scope_root = "diff/pkg/scope"
output = "diff.puml"
ignore = ["diff"]
depth = 0
mode = "warn"
target_python = "3.11"
current_state = "head"
include_untracked = false
""",
    )

    context, config = assert_success(
        resolve_context(bind_command_request(("diff", "--base", "main"), tmp_path))
    )

    assert context.project_root == diff_project.resolve()
    assert context.package_root == (diff_project / "pkg").resolve()
    assert context.scope_root == (diff_project / "pkg" / "scope").resolve()
    assert config.output == (tmp_path / "diff.puml").resolve()
    assert config.ignore == ("diff",)
    assert config.depth == 0
    assert config.mode is AnalysisMode.WARN
    assert config.target_python == "3.11"
    assert config.diff_current_state is DiffCurrentState.HEAD
    assert config.diff_include_untracked is False


def test_diff_command_section_inherits_top_level_common_values(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    (project / "pkg" / "scope").mkdir(parents=True)
    write_config(
        tmp_path / ".pyclassuml.toml",
        """
project_root = "project"
package_root = "project/pkg"
scope_root = "project/pkg/scope"
output = "common.puml"
ignore = ["common"]
depth = 2
mode = "strict"
target_python = "3.11"
relative_path_base = "config"

[diff]
current_state = "head"
include_untracked = false
""",
    )

    context, config = assert_success(
        resolve_context(bind_command_request(("diff", "--base", "main"), tmp_path))
    )

    assert context.project_root == project.resolve()
    assert context.package_root == (project / "pkg").resolve()
    assert context.scope_root == (project / "pkg" / "scope").resolve()
    assert config.output == (tmp_path / "common.puml").resolve()
    assert config.ignore == ("common",)
    assert config.depth == 2
    assert config.mode is AnalysisMode.STRICT
    assert config.target_python == "3.11"
    assert config.diff_current_state is DiffCurrentState.HEAD
    assert config.diff_include_untracked is False


def test_cli_common_values_override_command_and_common_sections(tmp_path: Path) -> None:
    top_project = tmp_path / "top"
    command_project = tmp_path / "command"
    cli_project = tmp_path / "cli"
    for project in (top_project, command_project, cli_project):
        (project / "pkg" / "scope").mkdir(parents=True)
    write_config(
        tmp_path / ".pyclassuml.toml",
        """
project_root = "top"
package_root = "top/pkg"
scope_root = "top/pkg/scope"
output = "top.puml"
ignore = ["top"]
depth = 4
mode = "warn"
target_python = "3.10"

[generate]
project_root = "command"
package_root = "command/pkg"
scope_root = "command/pkg/scope"
output = "command.puml"
ignore = ["command"]
depth = 2
mode = "warn"
target_python = "3.11"
""",
    )

    context, config = assert_success(
        resolve_context(
            generate_request(
                tmp_path,
                project_root=Path("cli"),
                package_root=Path("cli/pkg"),
                scope_root=Path("cli/pkg/scope"),
                output=Path("cli.puml"),
                ignore=("cli",),
                depth=0,
                strict=True,
                target_python="3.12",
            )
        )
    )

    assert context.project_root == cli_project.resolve()
    assert context.package_root == (cli_project / "pkg").resolve()
    assert context.scope_root == (cli_project / "pkg" / "scope").resolve()
    assert config.output == (tmp_path / "cli.puml").resolve()
    assert config.ignore == ("cli",)
    assert config.depth == 0
    assert config.mode is AnalysisMode.STRICT
    assert config.target_python == "3.12"


def test_command_relative_path_base_applies_to_inherited_top_level_paths(
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "config"
    execution = tmp_path / "execution"
    config_dir.mkdir()
    execution.mkdir()
    project = execution / "project"
    (project / "pkg" / "scope").mkdir(parents=True)
    write_config(
        config_dir / "settings.toml",
        """
project_root = "project"
package_root = "project/pkg"
scope_root = "project/pkg/scope"
output = "diagram.puml"

[diff]
relative_path_base = "cwd"
""",
    )

    context, config = assert_success(
        resolve_context(
            diff_request(
                execution,
                config=Path("../config/settings.toml"),
                diff=DiffOptions(
                    base_ref="main",
                    current_state=DiffCurrentState.WORKING_TREE,
                    include_untracked=True,
                    current_state_cli_provided=False,
                    include_untracked_cli_provided=False,
                ),
            )
        )
    )

    assert context.project_root == project.resolve()
    assert context.package_root == (project / "pkg").resolve()
    assert context.scope_root == (project / "pkg" / "scope").resolve()
    assert config.output == (execution / "diagram.puml").resolve()


def test_diff_command_relative_path_base_overrides_top_level_base(
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "config"
    execution = tmp_path / "execution"
    config_dir.mkdir()
    execution.mkdir()
    for root in (config_dir / "project", execution / "project"):
        (root / "pkg" / "scope").mkdir(parents=True)
    write_config(
        config_dir / "settings.toml",
        """
project_root = "project"
package_root = "project/pkg"
scope_root = "project/pkg/scope"
output = "diagram.puml"
relative_path_base = "config"

[diff]
relative_path_base = "cwd"
""",
    )

    context, config = assert_success(
        resolve_context(
            diff_request(
                execution,
                config=Path("../config/settings.toml"),
            )
        )
    )

    project = execution / "project"
    assert context.project_root == project.resolve()
    assert context.package_root == (project / "pkg").resolve()
    assert context.scope_root == (project / "pkg" / "scope").resolve()
    assert config.output == (execution / "diagram.puml").resolve()


def test_generate_command_relative_path_base_applies_to_command_and_inherited_paths(
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "config"
    execution = tmp_path / "execution"
    config_dir.mkdir()
    execution.mkdir()
    project = execution / "project"
    (project / "pkg" / "scope").mkdir(parents=True)
    write_config(
        config_dir / "settings.toml",
        """
project_root = "shadowed"
package_root = "project/pkg"
scope_root = "project/pkg/scope"
output = "diagram.puml"

[generate]
relative_path_base = "cwd"
project_root = "project"
""",
    )

    context, config = assert_success(
        resolve_context(
            generate_request(
                execution,
                config=Path("../config/settings.toml"),
            )
        )
    )

    assert context.project_root == project.resolve()
    assert context.package_root == (project / "pkg").resolve()
    assert context.scope_root == (project / "pkg" / "scope").resolve()
    assert config.output == (execution / "diagram.puml").resolve()


def test_cli_paths_use_execution_cwd_even_when_config_base_is_config(
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "config"
    execution = tmp_path / "execution"
    config_dir.mkdir()
    execution.mkdir()
    (execution / "cli" / "pkg" / "scope").mkdir(parents=True)
    write_config(
        config_dir / "settings.toml",
        """
project_root = "shadowed"
package_root = "shadowed/pkg"
scope_root = "shadowed/pkg/scope"
relative_path_base = "config"
""",
    )

    context, config = assert_success(
        resolve_context(
            diff_request(
                execution,
                config=Path("../config/settings.toml"),
                project_root=Path("cli"),
                package_root=Path("cli/pkg"),
                scope_root=Path("cli/pkg/scope"),
                output=Path("cli.puml"),
            )
        )
    )

    assert context.project_root == (execution / "cli").resolve()
    assert context.package_root == (execution / "cli" / "pkg").resolve()
    assert context.scope_root == (execution / "cli" / "pkg" / "scope").resolve()
    assert config.output == (execution / "cli.puml").resolve()


def test_default_project_root_remains_config_parent_when_active_base_is_cwd(
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "config"
    execution = tmp_path / "execution"
    config_dir.mkdir()
    execution.mkdir()
    write_config(
        config_dir / "settings.toml",
        """
[diff]
relative_path_base = "cwd"
""",
    )

    context, _ = assert_success(
        resolve_context(diff_request(execution, config=Path("../config/settings.toml")))
    )

    assert context.project_root == config_dir.resolve()
    assert context.package_root == config_dir.resolve()
    assert context.scope_root == config_dir.resolve()


def test_inactive_command_path_is_schema_checked_without_filesystem_validation(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    (project / "pkg").mkdir(parents=True)
    write_config(
        tmp_path / ".pyclassuml.toml",
        """
project_root = "project"
package_root = "project/pkg"

[diff]
project_root = "missing"
package_root = "missing/pkg"
scope_root = "missing/pkg/scope"
output = "inactive.puml"
""",
    )

    context, config = assert_success(resolve_context(generate_request(tmp_path)))

    assert context.project_root == project.resolve()
    assert context.package_root == (project / "pkg").resolve()
    assert config.output is None


def test_inactive_generate_section_type_is_validated_for_diff_command(
    tmp_path: Path,
) -> None:
    write_config(
        tmp_path / ".pyclassuml.toml",
        """
[generate]
project_root = 1
""",
    )

    assert_failure(
        resolve_context(diff_request(tmp_path)),
        FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
        code="invalid_config",
        message_contains="generate.project_root must be a string",
    )


def test_command_project_root_diagnostic_qualifies_active_section_field(
    tmp_path: Path,
) -> None:
    write_config(
        tmp_path / ".pyclassuml.toml",
        """
[diff]
project_root = "missing"
""",
    )

    assert_failure(
        resolve_context(diff_request(tmp_path)),
        FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
        code="invalid_root_path",
        message_contains="diff.project_root does not exist or is not a directory",
    )


def test_command_output_resolution_diagnostic_qualifies_active_section_field(
    tmp_path: Path,
) -> None:
    loop = tmp_path / "loop"
    loop.symlink_to(loop)
    write_config(
        tmp_path / ".pyclassuml.toml",
        """
[generate]
output = "loop/diagram.puml"
""",
    )

    assert_failure(
        resolve_context(generate_request(tmp_path)),
        FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
        code="invalid_path_resolution",
        message_contains="generate.output could not be resolved",
    )


def test_merge_fields_and_dotted_diff_schema(tmp_path: Path) -> None:
    project = tmp_path / "project"
    package = project / "pkg"
    scope = package / "feature"
    scope.mkdir(parents=True)
    write_config(
        project / ".pyclassuml.toml",
        """
package_root = "pkg"
scope_root = "pkg/feature"
output = "config-output.puml"
ignore = ["config_ignore"]
depth = 2
mode = "strict"
target_python = "3.10"
diff.current_state = "head"
diff.include_untracked = true
""",
    )

    context, config = assert_success(resolve_context(generate_request(package, output=Path("cli-output.puml"))))

    assert context.project_root == project.resolve()
    assert context.package_root == package.resolve()
    assert context.scope_root == scope.resolve()
    assert config.output == (package / "cli-output.puml").resolve()
    assert config.ignore == ("config_ignore",)
    assert config.depth == 2
    assert config.mode is AnalysisMode.STRICT
    assert config.target_python == "3.10"
    assert config.diff_current_state is DiffCurrentState.HEAD
    assert config.diff_include_untracked is True


def test_cli_values_override_config_values_and_cli_diff_only_applies_to_diff_command(tmp_path: Path) -> None:
    project = tmp_path / "project"
    cli_package = project / "cli_pkg"
    config_package = project / "config_pkg"
    cli_scope = cli_package / "scope"
    for path in (cli_scope, config_package):
        path.mkdir(parents=True)
    write_config(
        project / ".pyclassuml.toml",
        """
package_root = "config_pkg"
scope_root = "config_pkg"
ignore = ["config_ignore"]
depth = 2
target_python = "3.10"
[diff]
current_state = "head"
include_untracked = false
""",
    )

    context, config = assert_success(
        resolve_context(
            diff_request(
                project,
                package_root=Path("cli_pkg"),
                scope_root=Path("cli_pkg/scope"),
                ignore=("cli_ignore",),
                depth=0,
                target_python="3.12",
                diff=DiffOptions(
                    base_ref="main",
                    current_state=DiffCurrentState.WORKING_TREE,
                    include_untracked=True,
                ),
            )
        )
    )

    assert context.package_root == cli_package.resolve()
    assert context.scope_root == cli_scope.resolve()
    assert config.ignore == ("cli_ignore",)
    assert config.depth == 0
    assert config.target_python == "3.12"
    assert config.diff_current_state is DiffCurrentState.WORKING_TREE
    assert config.diff_include_untracked is True


def test_cli_and_config_depth_precedence_preserves_zero(tmp_path: Path) -> None:
    write_config(tmp_path / ".pyclassuml.toml", "depth = 3\n")

    _, config_from_config = assert_success(resolve_context(diff_request(tmp_path)))
    _, config_from_zero = assert_success(
        resolve_context(diff_request(tmp_path, depth=0))
    )
    _, config_from_two = assert_success(
        resolve_context(diff_request(tmp_path, depth=2))
    )

    assert config_from_config.depth == 3
    assert config_from_zero.depth == 0
    assert config_from_two.depth == 2


def test_package_root_is_preferred_import_root_for_monorepo_context(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    backend = repo / "backend"
    backend.mkdir(parents=True)

    context, _ = assert_success(
        resolve_context(
            diff_request(
                repo,
                project_root=repo,
                package_root=Path("backend"),
                scope_root=Path("backend"),
            )
        )
    )

    assert context.project_root == repo.resolve()
    assert context.package_root == backend.resolve()
    assert context.vcs_root == repo.resolve()
    assert context.import_roots == (backend.resolve(), repo.resolve())


def test_cli_diff_unset_include_untracked_uses_config_before_default(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    write_config(
        project / ".pyclassuml.toml",
        """
[diff]
include_untracked = false
""",
    )

    _, config = assert_success(resolve_context(bind_command_request(("diff", "--base", "main"), project)))

    assert config.diff_include_untracked is False


def test_cli_diff_unset_current_state_uses_config_before_default(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    write_config(
        project / ".pyclassuml.toml",
        """
[diff]
current_state = "head"
""",
    )

    _, config = assert_success(resolve_context(bind_command_request(("diff", "--base", "main"), project)))

    assert config.diff_current_state is DiffCurrentState.HEAD


def test_cli_diff_unset_current_state_defaults_working_tree_without_config(tmp_path: Path) -> None:
    _, config = assert_success(resolve_context(bind_command_request(("diff", "--base", "main"), tmp_path)))

    assert config.diff_current_state is DiffCurrentState.WORKING_TREE


def test_cli_current_state_overrides_config_head(tmp_path: Path) -> None:
    write_config(
        tmp_path / ".pyclassuml.toml",
        """
[diff]
current_state = "head"
""",
    )

    _, config = assert_success(
        resolve_context(bind_command_request(("diff", "--base", "main", "--current-state", "working-tree"), tmp_path))
    )

    assert config.diff_current_state is DiffCurrentState.WORKING_TREE


def test_cli_diff_unset_include_untracked_defaults_true_without_config(tmp_path: Path) -> None:
    _, config = assert_success(resolve_context(bind_command_request(("diff", "--base", "main"), tmp_path)))

    assert config.diff_include_untracked is True


def test_cli_no_include_untracked_overrides_config_true(tmp_path: Path) -> None:
    write_config(
        tmp_path / ".pyclassuml.toml",
        """
[diff]
include_untracked = true
""",
    )

    _, config = assert_success(
        resolve_context(bind_command_request(("diff", "--base", "main", "--no-include-untracked"), tmp_path))
    )

    assert config.diff_include_untracked is False


def test_strict_false_does_not_override_config_mode_but_strict_true_does(tmp_path: Path) -> None:
    write_config(tmp_path / ".pyclassuml.toml", 'mode = "strict"\n')

    _, config_false = assert_success(resolve_context(generate_request(tmp_path, strict=False)))
    _, config_true = assert_success(resolve_context(generate_request(tmp_path, strict=True)))

    assert config_false.mode is AnalysisMode.STRICT
    assert config_true.mode is AnalysisMode.STRICT


def test_strict_true_overrides_warn_config_mode(tmp_path: Path) -> None:
    write_config(tmp_path / ".pyclassuml.toml", 'mode = "warn"\n')

    _, config = assert_success(resolve_context(generate_request(tmp_path, strict=True)))

    assert config.mode is AnalysisMode.STRICT


def test_explicit_config_path_is_used(tmp_path: Path) -> None:
    project = tmp_path / "project"
    package = project / "pkg"
    package.mkdir(parents=True)
    explicit = tmp_path / "explicit.toml"
    write_config(explicit, f'project_root = "{project}"\npackage_root = "project/pkg"\ndepth = 7\n')

    context, config = assert_success(resolve_context(generate_request(tmp_path, config=explicit)))

    assert context.project_root == project.resolve()
    assert context.package_root == package.resolve()
    assert config.depth == 7


def test_missing_explicit_config_is_failure(tmp_path: Path) -> None:
    result = resolve_context(generate_request(tmp_path, config=Path("missing.toml")))

    assert_failure(
        result,
        FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
        code="invalid_config_path",
        message_contains="config file does not exist or is not a file",
    )


def test_invalid_toml_is_failure(tmp_path: Path) -> None:
    write_config(tmp_path / ".pyclassuml.toml", "project_root = [")

    assert_failure(
        resolve_context(generate_request(tmp_path)),
        FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
        code="invalid_config_toml",
        message_contains="config file is not valid TOML",
    )


def test_unknown_top_level_key_is_failure(tmp_path: Path) -> None:
    write_config(tmp_path / ".pyclassuml.toml", 'unexpected = "value"\n')

    assert_failure(
        resolve_context(generate_request(tmp_path)),
        FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
        code="invalid_config",
        message_contains="unknown config key: unexpected",
    )


def test_unknown_diff_key_is_failure(tmp_path: Path) -> None:
    write_config(tmp_path / ".pyclassuml.toml", "[diff]\nunknown = true\n")

    assert_failure(
        resolve_context(generate_request(tmp_path)),
        FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
        code="invalid_config",
        message_contains="unknown diff key: unknown",
    )


def test_non_table_diff_is_failure(tmp_path: Path) -> None:
    write_config(tmp_path / ".pyclassuml.toml", 'diff = "head"\n')

    assert_failure(
        resolve_context(generate_request(tmp_path)),
        FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
        code="invalid_config",
        message_contains="diff must be a table",
    )


def test_non_table_generate_is_failure(tmp_path: Path) -> None:
    write_config(tmp_path / ".pyclassuml.toml", "generate = true\n")

    assert_failure(
        resolve_context(generate_request(tmp_path)),
        FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
        code="invalid_config",
        message_contains="generate must be a table",
    )


def test_unknown_generate_key_is_failure(tmp_path: Path) -> None:
    write_config(tmp_path / ".pyclassuml.toml", "[generate]\nunknown = true\n")

    assert_failure(
        resolve_context(generate_request(tmp_path)),
        FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
        code="invalid_config",
        message_contains="unknown generate key: unknown",
    )


def test_generate_targets_config_key_is_failure(tmp_path: Path) -> None:
    write_config(tmp_path / ".pyclassuml.toml", "[generate]\ntargets = []\n")

    assert_failure(
        resolve_context(generate_request(tmp_path)),
        FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
        code="invalid_config",
        message_contains="unknown generate key: targets",
    )


@pytest.mark.parametrize(
    ("toml", "message_contains"),
    [
        ('current_state = "head"\n', "unknown config key: current_state"),
        ('[generate]\ncurrent_state = "head"\n', "unknown generate key: current_state"),
        ('[diff]\nbase = "main"\n', "unknown diff key: base"),
        ("[generate]\nproject_root = 1\n", "generate.project_root must be a string"),
        ("[diff]\ndepth = -1\n", "diff.depth must be a non-negative integer"),
        (
            '[diff]\nrelative_path_base = "project"\n',
            "diff.relative_path_base must be config or cwd",
        ),
    ],
)
def test_command_specific_schema_rejects_misplaced_or_invalid_values(
    tmp_path: Path,
    toml: str,
    message_contains: str,
) -> None:
    write_config(tmp_path / ".pyclassuml.toml", toml)

    assert_failure(
        resolve_context(generate_request(tmp_path)),
        FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
        code="invalid_config",
        message_contains=message_contains,
    )


@pytest.mark.parametrize(
    ("toml", "message_contains"),
    [
        ('mode = "fatal"\n', "mode must be warn or strict"),
        ('target_python = "2.7"\n', "target_python must match 3.<minor>"),
        ("target_python = 3.10\n", "target_python must match 3.<minor>"),
        ("target_python = true\n", "target_python must match 3.<minor>"),
        ('relative_path_base = "project"\n', "relative_path_base must be config or cwd"),
        ('[diff]\ncurrent_state = "index"\n', "diff.current_state must be working-tree or head"),
        ('[diff]\ninclude_untracked = "yes"\n', "diff.include_untracked must be a bool"),
        ("project_root = 1\n", "project_root must be a string"),
        ('ignore = "pkg"\n', "ignore must be a list of non-empty strings"),
        ('ignore = ["pkg", 1]\n', "ignore must be a list of non-empty strings"),
        ("depth = true\n", "depth must be a non-negative integer"),
        ("depth = -1\n", "depth must be a non-negative integer"),
    ],
)
def test_invalid_config_file_schema_values_are_failures(
    tmp_path: Path,
    toml: str,
    message_contains: str,
) -> None:
    write_config(tmp_path / ".pyclassuml.toml", toml)

    assert_failure(
        resolve_context(generate_request(tmp_path)),
        FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
        code="invalid_config",
        message_contains=message_contains,
    )


def test_unresolved_root_from_config_is_failure(tmp_path: Path) -> None:
    write_config(tmp_path / ".pyclassuml.toml", 'package_root = "missing"\n')

    assert_failure(
        resolve_context(generate_request(tmp_path)),
        FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
        code="invalid_root_path",
        message_contains="package_root does not exist or is not a directory",
    )


def test_unresolved_root_from_cli_is_failure(tmp_path: Path) -> None:
    result = resolve_context(generate_request(tmp_path, package_root=Path("missing")))

    assert_failure(
        result,
        FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
        code="invalid_root_path",
        message_contains="package_root does not exist or is not a directory",
    )


def test_invalid_cwd_is_failure(tmp_path: Path) -> None:
    result = resolve_context(generate_request(tmp_path, cwd=Path("missing")))

    assert_failure(
        result,
        FailureReason.INVALID_PATH_OR_CONTAINMENT,
        code="invalid_cwd",
        message_contains="cwd does not exist or is not a directory",
    )


def test_cwd_resolution_error_is_failure_diagnostic(tmp_path: Path) -> None:
    loop = tmp_path / "loop"
    loop.symlink_to(loop)

    result = resolve_context(generate_request(tmp_path, cwd=Path("loop")))

    assert_failure(
        result,
        FailureReason.INVALID_PATH_OR_CONTAINMENT,
        code="invalid_path_resolution",
        message_contains="cwd could not be resolved",
    )


def test_explicit_config_resolution_error_is_failure_diagnostic(tmp_path: Path) -> None:
    loop = tmp_path / "loop.toml"
    loop.symlink_to(loop)

    result = resolve_context(generate_request(tmp_path, config=Path("loop.toml")))

    assert_failure(
        result,
        FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
        code="invalid_path_resolution",
        message_contains="config could not be resolved",
    )


@pytest.mark.parametrize(
    ("override_name", "override_value", "message_contains"),
    [
        ("project_root", Path("loop"), "project_root could not be resolved"),
        ("output", Path("loop"), "output could not be resolved"),
    ],
)
def test_explicit_cli_path_resolution_errors_are_config_failures(
    tmp_path: Path,
    override_name: str,
    override_value: Path,
    message_contains: str,
) -> None:
    loop = tmp_path / "loop"
    loop.symlink_to(loop)

    result = resolve_context(generate_request(tmp_path, **{override_name: override_value}))

    assert_failure(
        result,
        FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
        code="invalid_path_resolution",
        message_contains=message_contains,
    )


def test_containment_violation_is_failure(tmp_path: Path) -> None:
    project = tmp_path / "project"
    outside = tmp_path / "outside"
    project.mkdir()
    outside.mkdir()

    result = resolve_context(generate_request(tmp_path, project_root=project, package_root=outside))

    assert_failure(
        result,
        FailureReason.INVALID_PATH_OR_CONTAINMENT,
        code="invalid_containment",
        message_contains="package_root must be under or equal to project_root",
    )


def test_scope_root_outside_package_root_containment_violation_is_failure(tmp_path: Path) -> None:
    project = tmp_path / "project"
    package = project / "package"
    outside_scope = project / "outside_scope"
    package.mkdir(parents=True)
    outside_scope.mkdir()

    result = resolve_context(
        generate_request(
            tmp_path,
            project_root=project,
            package_root=package,
            scope_root=outside_scope,
        )
    )

    assert_failure(
        result,
        FailureReason.INVALID_PATH_OR_CONTAINMENT,
        code="invalid_containment",
        message_contains="scope_root must be under or equal to package_root",
    )
