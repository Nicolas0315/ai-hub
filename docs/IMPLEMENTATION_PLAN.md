# Katala Core Engine Implementation Plan

## 1. Phase 1: The Immutable Fact Pipeline (Foundation)
エージェントが「事実」を抽出し、改ざん不能な形で記録・公開する最小限の「配管」を実装する。

### [A] Profiling Engine: Auto-Siphon & Staging
- **Goal**: ユーザーの発言から「事実ベースのプロフィール」を抽出し、承認待ち状態にする。
- **Logic**: 
    - LLMを用いてログから `(Skill, Fact, Evidence_Link)` のタプルを抽出。
    - `Katala/packages/katala/core/ProfilingEngine.ts` を実装し、`.openvisibility` ルールを適用。
- **Output**: 承認用ダッシュボード（JSON/UI）。

### [B] Immutable Ledger: Hash Chaining
- **Goal**: 合意形成ログを鎖のように繋ぎ、改ざんを不可能にする。
- **Logic**: 
    - 各ログエントリに `previous_hash` を持たせる。
    - 署名（ECDSA）による本人性担保。

## 2. Phase 2: Autonomous Mediation (Inter-Agent)
UIを介さず、エージェント同士が裏側で「毒抜き」交渉を行うロジック。

### [A] Detox Filtering Layer
- **Goal**: メッセージから感情的ノイズを削ぎ落とし、意図を抽象化する。
- **Logic**: `MediationManager` に、`IdentityVector` に基づいた「意図抽出プロンプト」を統合。

### [B] Synergy Scorer (Rust Integration)
- **Goal**: 抽象化されたベクトル同士の相関（シナジー）を高速に計算する。
- **Logic**: `synergy_scorer.rs` を Wasm または FFI 経由で Node.js から呼び出し。

## 3. Phase 3: The Board (Visibility)
ネットワーク全体の動きを「板」として可視化する。

- **Logic**: 公開設定された `PUBLIC` ログを WebSocket でブロードキャスト。

---

### **🛠 Immediate Action (Sirokuma & Codex Task)**
1. **`ProfilingEngine.ts` の詳細実装**: ログスキャンから Staging 登録までの自動化。
2. **`SynergyEngine.ts` のロジック精緻化**: ベクトル積だけでなく、`SOUL.md` の制約条件を評価に加える。
3. **`LOG_POLICY.md` に基づくログ保存機能の追加**: ファイルシステムへの構造化保存。
