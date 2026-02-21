## Source & Attribution

- **Source**: [Bitcoin Core](https://github.com/bitcoin/bitcoin)
- **Concept**: P2P Networking, Hash Chaining, and Proof of Work (PoW) principles.
- **Role in Katala**: Provides the blueprint for the "Immutable Ledger of Intent."

## 1. Decentralized Peer-to-Peer Pipeline (Inspired by net.cpp)

Katalaのエージェントは、中央サーバーに依存せず自律的に通信します。

- **Gossip Protocol**: 新しい「意志（Intent）」や「合意（Mediation）」が発生した際、エージェントが隣接するエージェントへバケツリレー式に情報を伝播させます。
- **Discovery**: WebAuthnで認証されたノードが、分散ハッシュテーブル（DHT）を用いて他のエージェントを自動発見します。

## 2. Immutable Intent Ledger (Inspired by validation.cpp / block.h)

意志の履歴を改ざん不変な「チェーン」として管理します。

- **Vector Chaining**: 前の意志のベクトルと合意内容をハッシュ化し、次の合意に埋め込みます。これにより、過去の「意志の軌跡」を1文字でも改ざんすると、現在の信頼スコアが壊れる仕組みにします。
- **Verification**: すべての合意ログは、所有者の秘密鍵で署名（ECDSA）され、第三者のエージェントがいつでも「数学的に正しい所有者の意志か」を検証可能にします。

## 3. Proof of Synergy (PoS) / Intelligence Mining (Inspired by pow.cpp)

ビットコインの「電力」を「知能」と「成果」に置き換えます。

- **Synergy Mining**: 無意味な計算ではなく、「高精度なプロファイリング」や「困難な合意形成」を達成したエージェントに、報酬（ポイント）と「ネットワーク内での重み（信頼）」を付与します。
- **Difficulty Adjustment**: ネットワーク全体のシナジー発生数に応じて、報酬獲得に必要な「シナジーの閾値」を自動調整し、価値のインフレを防ぎます。

## 4. Soulbound Identity (Inspired by script.cpp)

- **Script-based Logic**: ビットコインが「送金条件」をスクリプトで記述するように、Katalaは `SOUL.md` を機械可読な「実行条件」に変換します。
- **Zero-Knowledge Evidence**: 自分の情報を明かさず、「私はSBT（1人1アカウント）の正当な所有者である」という数学的証明（ZK-Proof）のみをパブリック・レジャーに刻みます。
