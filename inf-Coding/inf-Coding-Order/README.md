# inf-Coding-Order

人間の命令を優先する制御レイヤ（暫定）。

## 命令
- `./order-set.sh clean` : cache を手動クリーン
- `./order-set.sh katala-off` : Katala 利用を禁止
- `./order-set.sh katala-on` : Katala 利用を許可
- `./order-set.sh assist-off` : inf-Coding-Assist を禁止
- `./order-set.sh assist-on` : inf-Coding-Assist 利用を許可
- `./order-show.sh` : 現在状態を表示

## 仕様
- `katala-off` 中は `open-katala.sh` / `katala-exec.sh` / `assist-exec.sh` を拒否
- `assist-off` を設定すると `katala-off` に自動正規化
- `katala-on` を設定すると `assist-on` に自動正規化
- `assist-on` 中のみ `assist-exec.sh` を許可
- 命令イベントは `inf-Coding-cache/activity.log` に記録
