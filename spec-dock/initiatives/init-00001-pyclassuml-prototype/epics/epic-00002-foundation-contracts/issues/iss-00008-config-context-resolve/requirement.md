---
種別: 要件定義書（Issue）
ID: "iss-00008"
タイトル: "Config Context Resolve"
関連GitHub: ["#8"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
親: ["epic-00002", "init-00001"]
---

# iss-00008 Config Context Resolve — 要件定義（WHAT / WHY）

## 目的
- `process_cwd` と CLI / config 入力から、`execution_cwd`, `project_root`, `package_root`, `scope_root` を authoritative に確定する。
- config discovery / merge / validation を `config` seam に閉じ、後続 `targets`, `vcs`, `parse`, `report` が同じ意味論を共有できるようにする。

## スコープ
- MUST:
  - `process_cwd` 基準で `--cwd` を解決する。
  - `CLI > config > default` の優先順位で `AnalysisConfig` を確定する。
  - `depth` を `AnalysisConfig.depth = null | int >= 0` に正規化して carry する。
  - `AnalysisConfig.mode` は `warn | strict` に固定し、`cli_options.strict=true` なら `strict`、それ以外は `warn` に写像する。
  - `target_python` を semantic validation し、`AnalysisConfig.target_python = null | 3.<minor>` として carry する。
  - `project_root` を `CLI > config > config-file-dir > execution_cwd` の順で確定する。
  - `package_root` 未指定時は `project_root`、`scope_root` 未指定時は `package_root` を使う。
  - `--config` 指定時はその path を使う。
  - `--config` 未指定かつ `--project-root` 指定時は `<project_root>/.pyclassuml.toml` を先に探し、見つからなければ `execution_cwd` から親方向へ探索する。
  - `--config` 未指定かつ `--project-root` 未指定時は `execution_cwd` から親方向へ探索する。
  - `relative_path_base=config|cwd` を解釈し、config 内相対 path の基準を切り替える。
  - config file が読み込まれ、CLI と config のどちらでも `project_root` が明示されない場合は config file directory を `project_root` fallback とする。
  - config read failure、invalid config value、unresolved config path、containment violation を hard failure とする。
- MUST NOT:
  - explicit / diff target selection を行わない。
  - Git diff 読み取りや parse / analyze を行わない。
- OUT OF SCOPE:
  - summary counter の生成。
  - output write や exit code policy の最終決定。

## 受け入れ条件
- AC-001:
  - Actor:
    - CLI 利用者
  - Given:
    - `process_cwd` と `--cwd` がある。
  - When:
    - context resolve を行う。
  - Then:
    - `execution_cwd` は `process_cwd` 基準で解決され、`ExecutionContext` に格納される。
  - 観測点:
    - `process_cwd -> execution_cwd` handoff review。
- AC-002:
  - Actor:
    - CLI 利用者
  - Given:
    - CLI option、config file、default の値が混在する。
  - When:
    - config merge を行う。
  - Then:
    - `CLI > config > default` で `AnalysisConfig` が確定する。
  - 観測点:
    - config merge scenario review。
- AC-003:
  - Actor:
    - CLI 利用者
  - Given:
    - `--config` 未指定の invocation がある。
  - When:
    - config discovery を行う。
  - Then:
    - `--project-root` 有無に応じて canonical order で `.pyclassuml.toml` を探索する。
  - 観測点:
    - discovery order scenario。
- AC-004:
  - Actor:
    - CLI 利用者
  - Given:
    - invalid config read / value / path / containment のいずれかがある。
  - When:
    - context resolve を行う。
  - Then:
    - hard failure として non-zero 相当の failure handoff を返す。config read / invalid value / unresolved path は `invalid_config_or_config_path`、containment violation は `invalid_path_or_containment` を使う。
  - 観測点:
    - failure taxonomy review。

## 例外・エッジケース
- EC-001:
  - 条件:
    - config file は見つかったが、`project_root` が CLI と config にない。
  - 期待:
    - config file directory を `project_root` fallback に使う。
  - 観測点:
    - fallback scenario review。
- EC-002:
  - 条件:
    - config 内相対 path と `relative_path_base=cwd` が指定される。
  - 期待:
    - config 内相対 path は `execution_cwd` 基準で解決する。
  - 観測点:
    - relative path base scenario。
- EC-003:
  - 条件:
    - `--project-root` 指定時に `<project_root>/.pyclassuml.toml` がない。
  - 期待:
    - `execution_cwd` 親探索へフォールバックする。
  - 観測点:
    - discovery order scenario。

## 制約
- 4 roots の resolve owner は `config` とし、他 seam が再解釈しない。
- `project_root`, `package_root`, `scope_root` の containment validation はこの issue で閉じる。
- 4 roots の default derivation order もこの issue で閉じ、後段 seam が独自 fallback を持たない。
- config file 不在は failure ではなく default 継続だが、読み込めた config の invalidity は failure とする。
- `target_python` の semantic validation / carry owner は `config` とし、後段 seam が独自解釈しない。
- `CommandRequest` に入った CLI 起点の `target_python` も config 起点の値も、`config` が一元的に検証し、不正値は `invalid_config_or_config_path` として扱う。
- `target_python` は downstream `parse` / `analyze` が version-sensitive な syntax / typing interpretation に使う authoritative hint とする。
- `depth` の正規化 / carry owner も `config` とし、後段 seam は raw CLI option を参照しない。
- config read failure、invalid config value、unresolved config path の `failure_reason` は `invalid_config_or_config_path` に固定する。
- containment violation の `failure_reason` は `invalid_path_or_containment` に固定する。

## 未確定事項
- なし:
  - discovery order と failure taxonomy は initiative canonical docs で確定済みである。
