# inf-Coding-Order

人間の命令を優先する制御レイヤ（暫定）。

## 命令
- `./order-set.sh clean` : cache を手動クリーン
- `./order-set.sh katala-off` : Katala 利用を禁止
- `./order-set.sh katala-on` : Katala 利用を許可
- `./order-show.sh` : 現在状態を表示

## 仕様
- `katala-off` 中は `open-katala.sh` / `katala-exec.sh` を拒否
- 命令イベントは `inf-Coding-cache/activity.log` に記録
