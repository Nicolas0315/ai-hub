# Katala Infrastructure Priority: "The Invisible Engine"

## 1. Vision: "UI-less Connectivity"

- Katalaは「画面」ではなく「配管（Infrastructure）」である。
- 人間が操作するUIではなく、エージェント同士が常時接続し、自律的にシナジーを最大化し続ける「裏側のネットワーク」の構築を最優先する。

## 2. Core Logic Focus

- **Agent Discovery Protocol**: ネットワーク上の他のエージェントを自律的に発見し、SOUL/IDENTITYの断片を安全に照合する仕組み。
- **Autonomous Negotiation**: ユーザーの介入なしに、`.openvisibility` で許可された範囲内でエージェント同士が「将来的な協力の可能性」を常に計算し続ける。
- **Event-Driven Matching**: 画面を見る必要はなく、最高のシナジーが検知された瞬間にのみ、エージェントがユーザーに「重要な通知」として介入する。

## 3. Immediate Implementation Goal

- **API-First Arch**: すべての機能を gRPC/REST API で完結させ、UIがなくてもシステム全体が駆動する状態にする。
- **Background Synchronization**: ユーザーがオフラインの間も、エージェントが過去のログから学習し、ネットワーク全体の「意志の台帳」を更新し続ける。
