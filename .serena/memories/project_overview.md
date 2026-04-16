# pyclassuml
- Purpose: external CLI tool for Python projects that performs AST-only static analysis, follows internal dependencies, extracts reachable classes from given seeds, and generates PlantUML `.puml` UML class diagrams.
- Main commands: `generate`, `diff`.
- Product constraints: read-only, no runtime imports/exec of target code, no dependency injection into analyzed projects, deterministic output expected for same input/config/git base.
- High-level architecture direction from current design docs: pipeline-oriented modular monolith with seams `context/config/path`, `targeting/diff`, `resolution/traversal`, `extraction/framework support`, `diagram/output/diagnostics`.
- Primary source-of-truth docs: repo-root `AGENTS.md`, `spec-dock/active/*`, initiative design and research docs under `spec-dock/initiatives/init-00001-pyclassuml-prototype/`.