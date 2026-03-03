# inf-Coding

このフォルダは Katala 連携用の**固定入口**です。

## 目的
- Enigma -> inf-Coding -> Katala の順路を固定する
- inf-Coding を経由しない直接実行を防ぐ
- 現フェーズでは、実行イベントを `inf-Coding-cache` に集約する
- 人間命令は `inf-Coding-Order` で優先制御する

## ディレクトリ
- `inf-Coding-cache/` : 一時データ置き場（現フェーズのイベント記録先）
- `inf-Coding-run/` : 将来の監査ログ本番置き場（予約）
- `inf-Coding-Order/` : 人間命令の制御状態
- `inf-Coding-Assist/` : 補助ツール層

## ファイル
- `katala-root` : Katala ルートへのシンボリックリンク
- `guard.sh` : 入口ガード（inf-Coding 経由か検証）
- `order-enforce.sh` : 人間命令（katala-off/on）を強制
- `open-katala.sh` : ガード通過後に Katala ルートでシェルを開く
- `katala-exec.sh` : 通常実行ラッパー（ログは本文でなくハッシュ）
- `assist-exec.sh` : Assist層経由の実行ラッパー
- `inf-Coding-Assist/assist-cycle.sh` : KS+KCS必須の3サイクル（test/build/fix）実行
- `inf-Coding-Assist/assist-rustize.sh` : 重い処理のRust化候補抽出
- `log-to-cache.sh` : 実行イベントを cache 側へ追記
- `cache-clean.sh` : cache 側を手動クリーン
- `order-set.sh` : 命令発行（clean / katala-off / katala-on / assist-off / assist-on）
- `order-show.sh` : 命令状態確認

## 使い方（必須）
```bash
cd /mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding
chmod +x guard.sh order-enforce.sh open-katala.sh katala-exec.sh assist-exec.sh log-to-cache.sh cache-clean.sh order-set.sh order-show.sh

# 状態確認
./order-show.sh

# Katala禁止/許可
./order-set.sh katala-off
./order-set.sh katala-on

# Assist禁止/許可
./order-set.sh assist-off
./order-set.sh assist-on

# cache手動クリーン
./order-set.sh clean

# 実行（katala-exec / assist-exec は独立）
./katala-exec.sh git status
./assist-exec.sh git status
```

## ルール
- `assist-off`: `assist-exec.sh` は実行拒否
- `assist-on`: `assist-exec.sh` のみ実行許可（ON/OFFをOrderで強制）
- `assist` が `on` でない限り `assist-exec.sh` は実行不可
- `katala-exec.sh` とは独立（assist設定で katala-exec は塞がない）

※ 今は「監査は後で別場所へ移管」方針のため、イベント記録は `inf-Coding-cache` 側に寄せています。
