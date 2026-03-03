# inf-Coding

このフォルダは Katala 連携用の**固定入口**です。

## 目的
- Enigma -> inf-Coding -> Katala の順路を固定する
- inf-Coding を経由しない直接実行を防ぐ
- 実行ログ/キャッシュは原則残さない（stateless運用）
- 人間命令は `inf-Coding-Order` で優先制御する

## ディレクトリ
- `inf-Coding-cache/` : 互換維持用（現在は未使用）
- `inf-Coding-run/` : 将来拡張用（現在は未使用）
- `inf-Coding-Order/` : 人間命令の制御状態
- `inf-Coding-Assist/` : 補助ツール層

## ファイル
- `katala-root` : Katala ルートへのシンボリックリンク
- `guard.sh` : 入口ガード（inf-Coding 経由か検証）
- `order-enforce.sh` : 人間命令（katala-off/on）を強制
- `open-katala.sh` : ガード通過後に Katala ルートでシェルを開く
- `katala-exec.sh` : 通常実行ラッパー（ログ/ハッシュ保存なし）
- `assist-exec.sh` : Assist層経由の実行ラッパー（ログ/ハッシュ保存なし）
- `inf-Coding-Assist/assist-cycle.sh` : KS+KCS必須の3サイクル（test/build/fix）実行
- `inf-Coding-Assist/assist-rustize.sh` : 重い処理のRust化候補抽出
- `order-set.sh` : 命令発行（clean / katala-off / katala-on / assist-off / assist-on）
- `order-show.sh` : 命令状態確認

## 使い方（必須）
```bash
cd /mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding
chmod +x guard.sh order-enforce.sh open-katala.sh katala-exec.sh assist-exec.sh order-set.sh order-show.sh

# 状態確認
./order-show.sh

# Katala禁止/許可
./order-set.sh katala-off
./order-set.sh katala-on

# Assist禁止/許可
./order-set.sh assist-off
./order-set.sh assist-on

# clean（互換のため残置。現在は no-op）
./order-set.sh clean

# 実行（katala-exec / assist-exec は独立）
./katala-exec.sh git status
./assist-exec.sh git status
```

## ルール（Order強制）
- `assist-off` ⇒ `katala-off`（自動正規化）
- `katala-on` ⇒ `assist-on`（自動正規化）
- `assist-on` 時のみ `assist-exec.sh` 実行可
- `katala-off` 時は Katala 系実行を拒否

## チャット運用（負荷対策）
- 基本は **1メッセージ完結**
- 分割返信は **人間の明示依頼時のみ**
- 内部処理は構造化（条件/禁止/例外）を維持する

※ 現在は stateless 優先のため、実行イベントは保存しません。
