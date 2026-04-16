# system（ツール管理領域）

このディレクトリは `spec-dock` が **ツール都合で常設するファイル**を置く領域です。

- ここにあるファイルは **ユーザーの仕様書（Initiative/Epic/Issue）ではありません**
- `spec-dock update` により **上書きされる可能性**があります

## active-none（placeholder）

`spec-dock/active/{initiative,epic,issue}` は、アクティブ対象が無い場合でも壊れないように、
この placeholder をリンク先として利用します。

- 目的: 「アクティブが無い」ことを明示し、エージェントの入口が常に成立するようにする
- 注意: placeholder は編集対象外（best-effortで read-only）です

