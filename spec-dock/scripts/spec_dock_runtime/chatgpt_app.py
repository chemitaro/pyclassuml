from __future__ import annotations

import sys

from spec_dock_runtime.app import _find_specdock_dir
from spec_dock_runtime.cli.bootstrap import build_runtime
from spec_dock_runtime.cli.chatgpt_parser import build_parser
from spec_dock_runtime.cli.chatgpt_registry import build_registry
from spec_dock_runtime.cli.dispatch import dispatch


def main(argv: list[str] | None = None) -> int:
    parsed_argv = sys.argv[1:] if argv is None else argv
    try:
        registry = build_registry()
        parser = build_parser(registry)
        try:
            namespace = parser.parse_args(parsed_argv)
        except SystemExit as error:
            code = getattr(error, "code", 1)
            return int(code) if isinstance(code, int) else 1
        specdock_dir = _find_specdock_dir()
        runtime = build_runtime(specdock_dir, repo_root=specdock_dir.parent)
        return dispatch(namespace, registry, runtime.use_cases)
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
