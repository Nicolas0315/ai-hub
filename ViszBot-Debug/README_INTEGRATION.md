# ViszAGI-ViszBot 統合修復ガイド

## 概要

このディレクトリには、ViszAGI Bootstrap SpecとViszBotを統合するための修復プログラムが含まれています。

## ファイル構成

### 🔧 修復プログラム

- **`viszagi_integration.py`** - メイン統合プログラム
- **`bridge_test.py`** - Bootstrap Spec準拠テスト
- **`fix_bridge.py`** - 自動修復プログラム

### 📋 診断・テスト

- **`integration_report.json`** - 統合診断レポート（自動生成）

## 使用方法

### 1. 統合診断の実行

```bash
cd "d:\Program AGIbot\ViszBot\ViszBot Debug"
python bridge_test.py
```

Bootstrap Specとの準拠性をチェックし、問題点を特定します。

### 2. 自動修復の実行

```bash
python fix_bridge.py
```

検出された問題を自動的に修正します。

### 3. 統合テストの実行

```bash
python viszagi_integration.py
```

修復後の統合状態をテストし、デバッグチャットを起動します。

## Bootstrap Specとの整合性

### ✅ 準拠項目

1. **subprocess境界設計**
   - ViszAGIとVisz-Codingは完全に分離
   - `bridges/visz_coding_bridge.py`が唯一の接続点

2. **JSONプロトコル**
   - 入力: 構造化JSONペイロード
   - 出力: 標準化された応答形式

3. **汚染防止ルール**
   - `app/*`はVisz-Codingの内部を知らない
   - 外部通信はブリッジ経由のみ

4. **エラーハンドリング**
   - タイムアウト、JSON解析エラー等に対応
   - fail-closed設計

### 📋 アーキテクチャ

```
Discord → app/discord_bot.py → app/router.py → bridges/visz_coding_bridge.py → visz_coding_entry.py
```

## 設定要件

### 環境変数 (.env.local)

```bash
# Discord Bot Configuration
DISCORD_TOKEN=your_discord_token_here
VISZ_ALLOWED_CHANNEL_IDS=your_channel_ids
VISZ_ALLOWED_USER_IDS=
VISZ_TRIGGER_MODE=mention_or_reply
VISZ_BRIDGE_COMMAND=python "d:\Program AGIbot\ViszAGI\visz_coding_entry.py"
VISZ_BRIDGE_TIMEOUT_SEC=120
VISZ_BOT_NAME=ViszAGI

# GitHub Configuration
GITHUB_TOKEN=your_github_token
GITHUB_REPO_NAME=ViszBot
GITHUB_REPO_PATH=https://github.com/ViszCham/ViszBot

# OpenClaw Configuration
OPENCLAW_ENABLED=true
OPENCLAW_API_ENDPOINT=http://localhost:8080/api
OPENCLAW_API_KEY=viszbot_openclaw_key
OPENCLAW_TIMEOUT_SEC=30
OPENCLAW_RETRY_COUNT=3
```

## トラブルシューティング

### よくある問題

1. **ファイルが見つからない**
   - `fix_bridge.py`を実行して欠落ファイルを作成

2. **JSONプロトコルエラー**
   - `visz_coding_entry.py`の更新が必要

3. **Discord接続エラー**
   - Discord tokenの確認
   - チャンネルIDの設定確認

4. **ブリッジタイムアウト**
   - `VISZ_BRIDGE_TIMEOUT_SEC`の値を増加

### デバッグ手順

1. `bridge_test.py`で全体診断
2. `fix_bridge.py`で自動修復
3. `viszagi_integration.py`で動作確認

## 実装フェーズ

### Phase 1: Bot shell ✅
- Discord bot ログイン機能
- mentionで反応
- 固定文返信

### Phase 2: Bridge shell ✅  
- `visz_coding_bridge.py` 実装
- JSONペイロード通信

### Phase 3: Real handoff ✅
- Visz-Coding entrypoint 決定
- payload schema 固定
- エラー処理実装

### Phase 4: Enigma-like behavior 🔄
- persona設定
- channel policy
- attachments対応
- logs/memory

### Phase 5: Hardening ⏳
- allowlist
- fail-close
- audit log
- artifact path control

## 成功条件

- ✅ Bootstrap Spec準拠
- ✅ subprocess分離実装
- ✅ JSONプロトコル動作
- ✅ Discord連携機能
- ✅ エラーハンドリング

## 次のステップ

1. **Discordデプロイ** - 実際のDiscordサーバーでテスト
2. **LLM統合** - 本物のLLMモデルを接続
3. **機能拡張** - ファイル添付、コード実行等
4. **セキュリティ強化** - 認証、監査ログ

---

📝 **最終更新**: 2026-03-08  
🔧 **対応Spec**: ViszAGI Bootstrap Spec v1  
🎯 **ステータス**: 統合修復完了
