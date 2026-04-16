# pyclassuml AGENTS Guide

このファイルは、このリポジトリにおける repo / product / domain / onboarding の正本です。

責務の分離:
- `spec-dock/active/*` は current task contract
- repo root `AGENTS.md` は repo / product / domain / onboarding の正本
- `.codex/config.toml` はセッションとオーケストレーション設定
- `.codex/AGENTS.md` は root `AGENTS.md` が無い場合の SpecDock bootstrap 補助

## Project Overview

`pyclassuml` は Python プロダクトを対象にした外部 CLI ツールです。

- AST ベースの静的解析で内部依存をたどる
- 指定した起点から到達可能なクラス群を抽出する
- PlantUML `.puml` の UML クラス図を生成する
- 主コマンドは `generate` と `diff`

このツールは解析対象プロジェクトへ依存として組み込まず、外部ツールとして実行します。

## Read First

作業開始時は、まず current active context を確認し、次をこの順で読みます。

1. `spec-dock/active/issue/{requirement,design,plan}.md`
2. `spec-dock/active/epic/{requirement,design,plan}.md`
3. `spec-dock/active/initiative/{requirement,design,plan}.md`
4. `spec-dock/initiatives/init-00001-pyclassuml-prototype/discussions/20260416t080346z-research-pyclassuml-requirements-baseline-v2.md`
5. 必要に応じて `spec-dock/docs/guide.md` と関連 workflow docs

active が未設定でも `spec-dock/active/*` は fallback を返すため、最初に確認します。

## Source Of Truth

正本の扱い:
- チャットログは正本にしない
- 長い外部入力やユーザー提供仕様は `discussions/research` に置く
- 論点整理や比較は `discussions/disc` に置く
- 長期に残す判断は `adr` に置く
- `requirement.md` / `design.md` / `plan.md` は全文転載ではなく、必要な契約に再編して書く

この repository では、prototype の基礎仕様として上記 research baseline を参照元に使います。

## Working Model

SpecDock 運用の基本:
- SpecDock のコマンド操作は原則 `spec-manager` を使う
- `./spec-dock/scripts/spec-dock active show` をセッション開始時に確認する
- 実装前に issue の `requirement.md` / `design.md` / `plan.md` を整合させる
- 構造変更後と handoff 前に `./spec-dock/scripts/spec-dock validate` を実行する
- `./spec-dock/scripts/spec-dock sync` は CLI-managed state の再生成に限定し、一般的な修復手段として使わない

進行原則:
- Initiative は投資単位、Epic は設計の背骨、Issue は実装の最小単位として扱う
- 実装は active issue を基準に進める
- report には判断、検証結果、未解決事項、blocker を残す

## Product And Domain Rules

このプロダクトで守るべき強い骨格:
- 外部 CLI として動作する
- 解析対象プロジェクトの `pyproject.toml` に依存を追加しない
- 対象ソースコードを書き換えない
- 読み取り専用で動作する
- 対象コードを import 実行しない
- AST ベース静的解析のみで扱う

境界と責務:
- `execution_cwd` / `project_root` / `package_root` / `scope_root` を明確に分離する
- `generate` と `diff` では scope の扱いを混同しない
- MVP と将来拡張を混同しない
- 決定性を重視し、同一入力では同一内容を出力する

## Coding And Repo Conventions

基本ルール:
- ユーザーチャットは日本語
- STT typo を前提にし、識別子や path は検索で確認してから扱う
- 新規 path は原則 lowercase を使う
- 例外として repo root `AGENTS.md` は onboarding 用の正規ファイル名として許可する
- commit message は日本語 multi-line Conventional Commits を使う

実装時の重視点:
- 非侵襲性を壊さない
- 決定性を壊さない
- 読み取り専用の前提を壊さない
- 要件で MVP に含めないものを先回り実装しない

## Do / Do Not

Do:
- まず active docs と related research を読む
- SpecDock 管理対象は command-first で扱う
- requirement / design / plan の整合を確認してから実装へ進む
- 重要な判断や比較は docs に残す

Do not:
- `spec-dock/active/*` のリンクや `.path` を手で編集しない
- CLI-managed generated state を手で修復しない
- metadata を直編集して運用を進めない
- 仕様未整合のまま実装を始めない
- task 固有の一時判断を root `AGENTS.md` に積み上げない

## Escalate When

次の場合は立ち止まって確認または docs 化を優先します。

- active docs 同士が衝突する
- active docs と root `AGENTS.md` の前提が衝突する
- MVP 範囲か将来拡張かの線引きが曖昧
- SpecDock 管理対象か手編集可能かが不明
- `validate` failure の原因が不明
- 仕様変更が project / package / scope boundary を壊しうる
