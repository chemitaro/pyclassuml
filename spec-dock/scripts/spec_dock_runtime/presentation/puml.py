from __future__ import annotations

import re
from typing import Any

from ..domain.ids import deps_node_sort_key

_TREE_BOARD_BLOCKERS_LABEL_LIMIT = 3


def _active_entry_id(entry: Any) -> str | None:
    if not isinstance(entry, dict):
        return None
    value = entry.get("id")
    if isinstance(value, str) and value:
        return value
    return None


def _issue_ready_board_state(
    issue_id: str,
    issue_item: dict[str, Any],
    *,
    active_issue_id: str | None,
) -> tuple[str, list[str]]:
    status = str(issue_item.get("status") or "unknown").lower()
    deps = issue_item.get("deps")
    ready = False
    blockers_top: list[str] = []
    if isinstance(deps, dict):
        raw_ready = deps.get("ready")
        if isinstance(raw_ready, bool):
            ready = raw_ready
        raw_blockers_top = deps.get("blockers_top")
        if isinstance(raw_blockers_top, list):
            blockers_top = [str(dep_id) for dep_id in raw_blockers_top if isinstance(dep_id, str)]

    if status == "done":
        return ("DONE", [])
    if issue_id == active_issue_id:
        return ("DOING", blockers_top)
    if status == "unknown":
        return ("UNKNOWN", blockers_top)
    if ready:
        return ("READY", [])
    return ("BLOCKED", blockers_top)


def _render_tree_ready_board_puml(
    tree_state: dict[str, Any],
    *,
    active: dict[str, Any] | None,
    todo_only: bool,
    blockers_label_limit: int = _TREE_BOARD_BLOCKERS_LABEL_LIMIT,
) -> str:
    raw_tree = tree_state.get("tree")
    if not isinstance(raw_tree, list):
        raise RuntimeError("Invalid tree state: tree must be a list")

    active_issue_id = _active_entry_id(active.get("issue")) if isinstance(active, dict) else None
    state_color = {
        "READY": "#D5E8D4",
        "BLOCKED": "#F8CECC",
        "DOING": "#DAE8FC",
        "DONE": "#E3E3E3",
        "UNKNOWN": "#EEEEEE",
    }

    def alias(node_id: str) -> str:
        safe = re.sub(r"[^0-9A-Za-z_]", "_", node_id)
        if not safe or safe[0].isdigit():
            safe = "_" + safe
        return f"N{safe}"

    def esc(text: Any) -> str:
        return str(text).replace("\\", "\\\\").replace('"', '\\"')

    rendered_count = 0
    lines: list[str] = []
    lines.append("@startuml")
    lines.append("left to right direction")
    lines.append("skinparam shadowing false")
    lines.append("")
    lines.append("legend right")
    lines.append("|= State |= Color |")
    for state in ("READY", "BLOCKED", "DOING", "DONE", "UNKNOWN"):
        lines.append(f"| {state} |<{state_color[state]}> |")
    lines.append("endlegend")
    lines.append("")

    for init_item in raw_tree:
        if not isinstance(init_item, dict):
            continue
        epic_blocks: list[str] = []
        raw_epics = init_item.get("epics")
        if not isinstance(raw_epics, list):
            continue
        for epic_item in raw_epics:
            if not isinstance(epic_item, dict):
                continue
            issue_blocks: list[str] = []
            raw_issues = epic_item.get("issues")
            if not isinstance(raw_issues, list):
                continue
            for issue_item in raw_issues:
                if not isinstance(issue_item, dict):
                    continue
                issue_id = issue_item.get("id")
                if not isinstance(issue_id, str) or not issue_id:
                    continue

                state, blockers = _issue_ready_board_state(issue_id, issue_item, active_issue_id=active_issue_id)
                if todo_only and state == "DONE":
                    continue

                rendered_count += 1
                block_label = ""
                if state == "BLOCKED" and blockers:
                    shown = blockers[:blockers_label_limit]
                    suffix = f"+{len(blockers) - blockers_label_limit}" if len(blockers) > blockers_label_limit else ""
                    block_label = f"\\nblockers: {','.join(shown)}{suffix}"
                issue_blocks.append(
                    f'      rectangle "{esc(issue_id)}\\n[{state}]{block_label}" as {alias(issue_id)} {state_color[state]}'
                )

            if issue_blocks:
                epic_id = epic_item.get("id")
                epic_title = epic_item.get("title")
                if isinstance(epic_id, str) and isinstance(epic_title, str):
                    block = [f'    package "{esc(epic_id)}\\n{esc(epic_title)}" as {alias(epic_id)} {{']
                    block.extend(issue_blocks)
                    block.append("    }")
                    epic_blocks.extend(block)

        if epic_blocks:
            init_id = init_item.get("id")
            init_title = init_item.get("title")
            if isinstance(init_id, str) and isinstance(init_title, str):
                lines.append(f'  package "{esc(init_id)}\\n{esc(init_title)}" as {alias(init_id)} {{')
                lines.extend(epic_blocks)
                lines.append("  }")
                lines.append("")

    if rendered_count == 0:
        lines.append('note "No todo issues to render" as Empty')

    lines.append("@enduml")
    lines.append("")
    return "\n".join(lines)


def _deps_disabled_error_text(error: str | None) -> str:
    text = (error or "deps unavailable").strip()
    return text.replace("\n", " ")


def _render_deps_disabled_tree_puml(*, todo_only: bool, error: str | None) -> str:
    mode = "todo" if todo_only else "all"
    err = _deps_disabled_error_text(error)
    lines: list[str] = []
    lines.append("@startuml")
    lines.append("left to right direction")
    lines.append("skinparam shadowing false")
    lines.append(f"title tree-{mode} - DEPS_DISABLED")
    lines.append(f'note "deps_preflight_failed\\ndeps.valid=false\\nmode=sync --force\\nerror: {err}" as Disabled')
    lines.append("@enduml")
    lines.append("")
    return "\n".join(lines)


def _render_deps_disabled_deps_issues_puml(*, error: str | None) -> str:
    err = _deps_disabled_error_text(error)
    lines: list[str] = []
    lines.append("@startuml")
    lines.append("left to right direction")
    lines.append("skinparam shadowing false")
    lines.append("skinparam linetype ortho")
    lines.append("title deps-issues - DEPS_DISABLED")
    lines.append(f'note "deps_preflight_failed\\ndeps.valid=false\\nmode=sync --force\\nerror: {err}" as Disabled')
    lines.append("@enduml")
    lines.append("")
    return "\n".join(lines)


def _render_deps_issues_puml(deps_issues_state: dict[str, Any]) -> str:
    nodes = deps_issues_state.get("nodes")
    if not isinstance(nodes, dict):
        raise RuntimeError("Invalid deps-issues.json: nodes must be an object")
    raw_edges = deps_issues_state.get("edges")
    if not isinstance(raw_edges, list):
        raise RuntimeError("Invalid deps-issues.json: edges must be a list")

    state_color = {
        "doing": "#DAE8FC",
        "ready": "#D5E8D4",
        "blocked": "#F8CECC",
        "unknown": "#EEEEEE",
    }

    def alias(node_id: str) -> str:
        safe = re.sub(r"[^0-9A-Za-z_]", "_", node_id)
        if not safe or safe[0].isdigit():
            safe = "_" + safe
        return f"N{safe}"

    include_ids = sorted([node_id for node_id in nodes.keys() if isinstance(node_id, str)], key=deps_node_sort_key)
    include_set = set(include_ids)

    lines: list[str] = []
    lines.append("@startuml")
    lines.append("left to right direction")
    lines.append("skinparam shadowing false")
    lines.append("skinparam linetype ortho")
    lines.append("")
    lines.append("legend right")
    lines.append("|= State |= Color |")
    for state, color in (
        ("doing", "#DAE8FC"),
        ("ready", "#D5E8D4"),
        ("blocked", "#F8CECC"),
        ("unknown", "#EEEEEE"),
    ):
        lines.append(f"| {state} |<{color}> |")
    lines.append("endlegend")
    lines.append("")

    for node_id in include_ids:
        item = nodes.get(node_id)
        if not isinstance(item, dict):
            continue
        state = str(item.get("state") or "unknown")
        color = state_color.get(state, state_color["unknown"])
        label = f"{node_id}\\n{state.capitalize()}"
        if item.get("ready") is False:
            label += "\\nready=false"
        lines.append(f'rectangle "{label}" as {alias(node_id)} {color}')
    lines.append("")

    block_edges: list[tuple[str, str]] = []
    for edge in raw_edges:
        if not isinstance(edge, dict):
            continue
        dependent = edge.get("from")
        prerequisite = edge.get("to")
        if not isinstance(dependent, str) or not isinstance(prerequisite, str):
            continue
        if dependent not in include_set or prerequisite not in include_set:
            continue
        block_edges.append((prerequisite, dependent))
    block_edges.sort(key=lambda x: (deps_node_sort_key(x[0]), deps_node_sort_key(x[1])))
    for prerequisite, dependent in block_edges:
        lines.append(f"{alias(prerequisite)} --> {alias(dependent)} : blocks")

    lines.append("@enduml")
    lines.append("")
    return "\n".join(lines)


def render_tree_ready_board_puml(
    tree_state: dict[str, Any],
    *,
    active: dict[str, Any] | None,
    todo_only: bool,
) -> str:
    return _render_tree_ready_board_puml(tree_state, active=active, todo_only=todo_only)


def render_deps_disabled_tree_puml(*, todo_only: bool, error: str | None) -> str:
    return _render_deps_disabled_tree_puml(todo_only=todo_only, error=error)


def render_deps_issues_puml(deps_issues_state: dict[str, Any]) -> str:
    return _render_deps_issues_puml(deps_issues_state)


def render_deps_disabled_deps_issues_puml(*, error: str | None) -> str:
    return _render_deps_disabled_deps_issues_puml(error=error)
