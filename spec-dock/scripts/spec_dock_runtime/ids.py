from __future__ import annotations

from typing import Any

from spec_dock_runtime.domain import ids as _domain_ids

_DEFAULT_ID_WIDTH = _domain_ids.DEFAULT_ID_WIDTH
_ID_RE = _domain_ids.ID_RE
_NUM_RE = _domain_ids.NUM_RE
_INPUT_TITLE_RE = _domain_ids.INPUT_TITLE_RE
_INPUT_SLUG_KEBAB_RE = _domain_ids.INPUT_SLUG_KEBAB_RE


def _validate_lowercase(value: str, *, field: str) -> str:
    return _domain_ids.validate_lowercase(value, field=field)


def _validate_slug(value: str, *, field: str = "slug") -> str:
    return _domain_ids.validate_slug(value, field=field)


def _validate_input_title(value: str, *, field: str = "--title") -> str:
    return _domain_ids.validate_input_title(value, field=field)


def _validate_input_slug_kebab(value: str, *, field: str = "--slug") -> str:
    return _domain_ids.validate_input_slug_kebab(value, field=field)


def _derive_input_slug_from_title(title: str) -> str:
    return _domain_ids.derive_input_slug_from_title(title)


def _resolve_input_title_and_slug(title: str, slug: str | None) -> tuple[str, str]:
    return _domain_ids.resolve_input_title_and_slug(title, slug)


def _normalize_id_input(value: str, *, prefix: str, field: str) -> str:
    return _domain_ids.normalize_id_input(value, prefix=prefix, field=field)


def _find_existing_id_by_num(nodes: dict[str, Any], *, prefix: str, num: int, local: bool) -> str | None:
    return _domain_ids.find_existing_id_by_num(nodes, prefix=prefix, num=num, local=local)


def _resolve_id_input(value: str, *, prefix: str, field: str, nodes: dict[str, Any] | None = None) -> str:
    return _domain_ids.resolve_id_input(value, prefix=prefix, field=field, nodes=nodes)


def _slugify(title: str) -> str:
    return _domain_ids.slugify(title)


def _parse_id(value: str) -> tuple[str, bool, int]:
    return _domain_ids.parse_id(value)


def _format_id(prefix: str, num: int, *, width: int = _DEFAULT_ID_WIDTH, local: bool = False) -> str:
    return _domain_ids.format_id(prefix, num, width=width, local=local)


def _deps_node_sort_key(node_id: str) -> tuple[int, int, str]:
    return _domain_ids.deps_node_sort_key(node_id)
