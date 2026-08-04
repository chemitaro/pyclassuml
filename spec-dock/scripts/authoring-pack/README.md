# ChatGPT authoring pack installed asset helpers

This directory is the provider-side source of truth for ChatGPT authoring pack helper scripts that are shipped into consumer repositories by `spec-dock init` and `spec-dock update`.

## Position

Files under `src/spec_dock/assets/spec_dock/scripts/authoring-pack/` are installed asset content. A consumer repository receives them under `spec-dock/scripts/authoring-pack/` when the scaffold is initialized or updated.

The repository-root `scripts/authoring-pack/` directory is a compatibility and dogfood developer surface for this provider repository. It is useful for local development, manual tests, and migration support, but it is not the installed asset source of truth.

## Authority Boundary

- This directory is provider-side source of truth for the shipped helper inventory.
- Helper outputs remain evidence-only until a main orchestrator adopts them into canonical SpecDock artifacts.
- ChatGPT output, ZIP files, staged artifacts, and reviewer-focus notes do not replace canonical docs, `.assurance.json`, authorized profiles, or fresh reviewer gates.
- Backend automation such as Oracle or browser control is not bundled here. It must be supplied through an explicit backend command contract in later workflow steps.

## Installed Asset Contract

The helper scripts in this directory support preparing, reviewing, staging, and validating ChatGPT authoring pack outputs. They are intentionally kept as scripts in this Issue; runtime command integration, backend invocation policy, ZIP staging promotion, candidate validation policy, and installed skill workflow updates are handled by later Issues in `epic-00295`.

Do not add generated files such as `__pycache__/` to this provider asset inventory.

## Verification

When this inventory changes, verify both provider and installed-consumer reachability:

```bash
find src/spec_dock/assets/spec_dock/scripts/authoring-pack -maxdepth 1 -type f | sort
python -m py_compile src/spec_dock/assets/spec_dock/scripts/authoring-pack/*.py
uvx --isolated --from "$(pwd)" spec-dock init /private/tmp/specdock-authoring-pack-init-smoke
test -f /private/tmp/specdock-authoring-pack-init-smoke/spec-dock/scripts/authoring-pack/README.md
```
