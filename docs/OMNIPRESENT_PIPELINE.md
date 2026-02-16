# Katala Infrastructure Design: "The Omnipresent Pipeline"

## 1. Concept: Platform-Agnostic Interface
- Katalaは特定のアプリに閉じない。Discord, Telegram, WhatsApp, Email, あるいは専用ハードウェアなど、ユーザーが「普段使っている場所」にエージェントが常駐する。
- UIは各プラットフォームのネイティブUI（チャット、音声、通知）を再利用する。

## 2. Global Pipeline Architecture
- **Input Adapter**: あらゆるプラットフォームからのメッセージ、音声、活動ログを標準化された「意志データ」に変換。
- **Core Mediation Engine**: プラットフォームの垣根を越え、エージェント同士がP2Pまたは分散型台帳（Ledger）を介して交渉。
- **Output Renderer**: 合意事項を、受信側のユーザーが使っているプラットフォームのトーン（IDENTITY.md）に合わせて配信。

## 3. Use Case: "Cross-Tool Synergy"
- ニコラスさんが Discord で発言した「意志」をエージェントが汲み取り、Telegram を使っている投資家のエージェントと裏で交渉し、翌朝ニコラスさんの Slack に「合意しました」と届く。
- これこそが「UIを捨てた、パイプラインとしてのKatala」の完成形。
