# r18 Rust移行 具体I/F実装計画（実装用）

対象: `inf-Coding -> inf-Bridge -> KQ`
目的: Python制御を維持しつつ、計算ホットスポットをRustへ移植。最終的にRust主経路へ。

## 1) Rust移植対象関数（優先順）

### P1（最優先）
- mini solver family score計算（512 lanes）
- triadic complement matrix計算
- SPML 5成分 + completeness/fidelity 集約

### P2
- orchestration_detail 集約計算
- orchestration_history rolling統計計算

### P3
- ks47_compatible_output の5軸集約（axis_details含む）

---

## 2) Python ↔ Rust I/F スキーマ

## 2.1 mini solver kernel

### input
```json
{
  "text": "string",
  "complementFamilyBoost": {
    "lexical": 0.0,
    "grounding": 0.0,
    "logic": 0.0,
    "coding": 0.0,
    "creativity": 0.0,
    "safety": 0.0,
    "routing": 0.0,
    "stability": 0.0
  }
}
```

### output
```json
{
  "activationRatio": 0.0,
  "activatedCount": 0,
  "families": {},
  "scores": {},
  "activated": []
}
```

## 2.2 SPML kernel

### input
```json
{
  "semanticFidelityLoss": 0.0,
  "embodiedSignalLoss": 0.0,
  "temporalParadigmLoss": 0.0,
  "stanceContextLoss": 0.0,
  "evidenceGroundingLoss": 0.0,
  "weights": {
    "semantic_fidelity_loss": 0.24,
    "embodied_signal_loss": 0.20,
    "temporal_paradigm_loss": 0.20,
    "stance_context_loss": 0.16,
    "evidence_grounding_loss": 0.20
  }
}
```

### output
```json
{
  "score": 0.0,
  "mappingCompletenessLoss": 0.0,
  "mappingFidelityLoss": 0.0,
  "profile": "low-loss|controlled-loss|medium-loss|high-loss"
}
```

## 2.3 triadic kernel

### input
```json
{
  "spmTagCount": 0,
  "domainActivationRatio": 0.0,
  "miniActivationRatio": 0.0
}
```

### output
```json
{
  "pairScores": {
    "spm_x_28plus": 0.0,
    "spm_x_mini": 0.0,
    "28plus_x_mini": 0.0
  },
  "triadicScore": 0.0,
  "recommendedMode": "pairwise|triadic"
}
```

---

## 3) 段階切替手順（Phase1-4）

### Phase 1
- Rust crate雛形作成 (`rust_kq_kernels`)
- pyo3公開関数だけ先に定義
- Python側 adapter を追加（呼び出しのみ）

### Phase 2
- mini solver kernel を Rust実装
- triadic kernel を Rust実装
- Pythonで同等性テスト

### Phase 3
- SPML kernel を Rust実装
- orchestration計算を Rust実装
- ks47 5軸集約を Rust実装

### Phase 4
- Rust主経路へ切替
- Python旧経路を互換専用へ縮退

---

## 4) 同等性テスト項目

- mini solver:
  - count, activated_count, activation_ratio
  - family別 activated
- triadic:
  - pair_scores / triadic_score / recommended_mode
- SPML:
  - score, profile
  - completeness/fidelity
- orchestration:
  - completion/recovery/parallelism/exec_time/consistency
- ks47互換:
  - 5軸 solver_results と overall_score

許容誤差: `abs(py - rust) <= 1e-6`

---

## 5) 切替判定基準（フォールバック撤去条件）

- 連続 1000 ケースの同等性テスト pass
- 主要回帰テスト pass
- 48h burn-in でクラッシュ 0
- 性能改善:
  - p95 latency 20%以上改善
  - CPU使用率 15%以上改善
- 以上を満たしたらフォールバック撤去候補
