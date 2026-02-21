# Katala Immutable Log Policy (Draft)

## 1. Concept: "The Immutable Trace"

- エージェント間の交渉プロセスは、「嘘のない事実（Ground Truth）」としてすべて記録される。
- ユーザーに提示される「演出された言葉」の裏側に、必ず「検証可能な交渉ログ」を存在させる。

## 2. Global Ledger of Intent

- エージェントが行ったすべての意思決定、ベクトル変換、合意形成をシリアライズし、永続的なログとして保持する。
- これは「人間の感情（毒素）」が抜かれた後の、純粋な「意志の軌跡」である。

## 3. Transparency & Verification

- ユーザー（所有者）は、自分のエージェントがどのような事実に基づき、相手のエージェントと何を合意したのかをいつでもログレベルで遡及できる。
- 「嘘みたいな交渉（フィクション）」を排除し、ログこそが正解（Source of Truth）となる設計。

## 4. Integration Strategy

- `SynergyEngine` の計算結果と、`MediationManager` の対話ログを統合し、構造化データ（JSON/TOML）として出力・保存する。
- プロフィール（Identity Vector）の更新履歴をこのログと紐付け、なぜそのベクトルに変化したのかの証跡を残す。
