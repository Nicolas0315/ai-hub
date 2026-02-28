# HTLF (Holographic Translation Loss Framework)

HTLF は、異なる記号レイヤー間（数学 / 形式言語 / 自然言語 / 音楽 / 創作）で翻訳されたときの情報損失を 3 軸で測定するフレームワークです。

- `R_struct`: 構造復元度
- `R_context`: 文脈復元度
- `R_qualia`: 体験的質感の復元度

Phase 3 では、KS29B の信頼性スコアと HTLF の翻訳忠実度を統合するインターフェースを追加しました。

---

## インストール

```bash
cd /Users/nicolas/work/katala
python3 -m venv .venv
source .venv/bin/activate
pip install -r src/htlf/requirements.txt
export PYTHONPATH=src
```

---

## 使い方

### 1) 通常 HTLF パイプライン（Phase 2）

```bash
python -m htlf.pipeline \
  --mode htlf \
  --source /path/to/source.txt \
  --target /path/to/target.txt
```

### 2) KS29B 統合モード（Phase 3）

```bash
python -m htlf.pipeline \
  --mode ks29b \
  --claim "This paper claims X reduces Y by 32% (p<0.05)." \
  --source "Original abstract text here..."
```

またはファイル入力:

```bash
python -m htlf.pipeline \
  --mode ks29b \
  --claim /path/to/claim.txt \
  --source /path/to/source.txt \
  --alpha 0.7 \
  --beta 0.3
```

### 3) 事前算出済み KS29B スコアを注入

```bash
python -m htlf.pipeline \
  --mode ks29b \
  --claim "..." \
  --ks29b-score 0.81
```

---

## 統合スコア式

```text
final = α × ks29b_score + β × translation_fidelity
```

- `translation_fidelity = 1 - total_loss`
- `α, β` は CLI で調整可能（正規化されます）

---

## アーキテクチャ（ASCII）

```text
                  +---------------------------+
source_text ----> | HTLF parser + DAG matcher | ----+
claim_text  ----> | HTLF scorer (3 axes)      |     |
                  +---------------------------+     |
                                                     v
                                              translation_fidelity
                                                     |
claim_text ------------------------------------------+-----+
                                                     |     |
                                                     v     |
                                     +------------------+  |
                                     | KS29B score      |  |
                                     | (provided/est.)  |  |
                                     +------------------+  |
                                                     |     |
                                                     +-----v
                                               final weighted score
```

---

## Phase 0-3 進捗サマリ

- **Phase 0 (理論)**
  - 5レイヤー × 3軸（構造・文脈・質感）の定義
  - 12プロファイル（2軸合成 + 単軸）

- **Phase 1 (最小実装)**
  - HTLF CLI パイプライン骨組み
  - 検証データセット整備

- **Phase 2 (計測可能化)**
  - `R_struct` 実装（DAG/edge aware）
  - `R_context` 実装（LLM + heuristic fallback）
  - `R_qualia` 実装（LLM ensemble proxy）
  - 既知課題: `R_qualia` 相関が低い（代理指標）

- **Phase 3 (今回)**
  - 行動主義的 `R_qualia` 計測プロトコル文書化
  - `HTLFScorer` (`ks29b_integration.py`) 追加
  - `pipeline.py --mode ks29b` 追加
  - KS29B × HTLF 統合式の実装

---

## 主要ファイル

- `src/htlf/pipeline.py` — CLIエントリポイント
- `src/htlf/scorer.py` — 3軸スコア計算
- `src/htlf/ks29b_integration.py` — KS29B統合インターフェース
- `docs/research/htlf-qualia-protocol.md` — Phase 3 プロトコル
