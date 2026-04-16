from __future__ import annotations

import json

from ..application.contracts import SyncStateResult
from ..domain.ids import deps_node_sort_key
from .contracts import DashboardArtifact
from .json_state import render_index_artifact
from .puml import _deps_disabled_error_text, _issue_ready_board_state

_DASHBOARD_TOP_LIMIT = 10
_TREE_BOARD_BLOCKERS_LABEL_LIMIT = 3


def _active_entry_id(entry: object) -> str | None:
    if not isinstance(entry, dict):
        return None
    value = entry.get("id")
    if isinstance(value, str) and value:
        return value
    return None


def _render_dashboard_md(
    index_nodes: dict[str, object],
    *,
    active: dict[str, object] | None,
    top_limit: int = _DASHBOARD_TOP_LIMIT,
) -> str:
    active_issue_id = _active_entry_id(active.get("issue")) if isinstance(active, dict) else None

    entries: list[dict[str, object]] = []
    for node_id in sorted(index_nodes.keys(), key=deps_node_sort_key):
        item = index_nodes.get(node_id)
        if not isinstance(item, dict):
            continue
        if item.get("type") != "issue":
            continue
        status = str(item.get("status") or "unknown").lower()
        if status == "done":
            continue

        state, blockers_top = _issue_ready_board_state(
            node_id,
            item,
            active_issue_id=active_issue_id,
        )
        entries.append(
            {
                "id": node_id,
                "title": str(item.get("title") or ""),
                "state": state,
                "blockers_top": blockers_top,
            }
        )

    by_state: dict[str, list[dict[str, object]]] = {
        "DOING": [],
        "READY": [],
        "BLOCKED": [],
        "UNKNOWN": [],
    }
    for entry in entries:
        state = entry.get("state")
        if isinstance(state, str) and state in by_state:
            by_state[state].append(entry)

    lines: list[str] = []
    lines.append("# Dashboard (generated)")
    lines.append("")
    lines.append("## Observability")
    lines.append("- index: `spec-dock/.agent/index.json`")
    lines.append("- ready board: `spec-dock/tree.puml`")
    lines.append("- deps graph: `spec-dock/deps-issues.puml`")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- todo_total: {len(entries)}")
    lines.append(f"- doing: {len(by_state['DOING'])}")
    lines.append(f"- ready: {len(by_state['READY'])}")
    lines.append(f"- blocked: {len(by_state['BLOCKED'])}")
    lines.append(f"- unknown: {len(by_state['UNKNOWN'])}")
    lines.append("")

    def append_state_section(state: str, title: str) -> None:
        lines.append(f"## {title}")
        section_items = by_state[state][:top_limit]
        if not section_items:
            lines.append("- (none)")
            lines.append("")
            return
        for entry in section_items:
            issue_id = entry["id"]
            issue_title = entry["title"]
            blockers_top = entry.get("blockers_top")
            if state == "BLOCKED" and isinstance(blockers_top, list) and blockers_top:
                blockers = ", ".join(str(dep_id) for dep_id in blockers_top[:_TREE_BOARD_BLOCKERS_LABEL_LIMIT])
                lines.append(f"- `{issue_id}` {issue_title} (blockers: {blockers})")
            else:
                lines.append(f"- `{issue_id}` {issue_title}")
        lines.append("")

    append_state_section("DOING", "Doing")
    append_state_section("READY", "Ready")
    append_state_section("BLOCKED", "Blocked")
    append_state_section("UNKNOWN", "Unknown")
    return "\n".join(lines)


def _render_deps_disabled_dashboard_md(*, error: str | None) -> str:
    err = _deps_disabled_error_text(error)
    lines: list[str] = []
    lines.append("# Dashboard (generated)")
    lines.append("")
    lines.append("## DEPS_DISABLED")
    lines.append("- deps_preflight_failed")
    lines.append("- deps.valid=false")
    lines.append("- mode: `sync --force`")
    lines.append(f"- error: `{err}`")
    lines.append("- ready/blocked 集計は無効です")
    lines.append("")
    lines.append("## Observability")
    lines.append("- index: `spec-dock/.agent/index.json`")
    lines.append("- ready board: `spec-dock/tree.puml`")
    lines.append("- deps graph: `spec-dock/deps-issues.puml`")
    lines.append("")
    return "\n".join(lines)


def render_dashboard(result: SyncStateResult, *, top_limit: int = 10) -> DashboardArtifact:
    if result.deps_preflight_error is not None:
        text = _render_deps_disabled_dashboard_md(error=result.deps_preflight_error)
        return DashboardArtifact(markdown_text=text if text.endswith("\n") else text + "\n")

    index_artifact = render_index_artifact(result)
    index_payload = json.loads(index_artifact.all_json_text)
    nodes = index_payload.get("nodes") if isinstance(index_payload, dict) else {}
    active = index_payload.get("active") if isinstance(index_payload, dict) else None
    if not isinstance(nodes, dict):
        nodes = {}
    text = _render_dashboard_md(nodes, active=active if isinstance(active, dict) else None, top_limit=top_limit)
    return DashboardArtifact(markdown_text=text if text.endswith("\n") else text + "\n")
