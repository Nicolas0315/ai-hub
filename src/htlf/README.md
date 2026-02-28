# HTLF (Holographic Translation Loss Framework)

HTLF は、異なる記号レイヤー間（数学 / 形式言語 / 自然言語 / 音楽 / 創作）で翻訳されたときの情報損失を 3 軸で測定するフレームワークです。

- `R_struct`: 構造復元度
- `R_context`: 文脈復元度
- `R_qualia`: 体験的質感の復元度

Phase 3 では、KS39b の信頼性スコアと HTLF の翻訳忠実度を統合するインターフェースを追加しました。

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

### 2) KS39b 統合モード（Phase 3）

```bash
python -m htlf.pipeline \
  --mode ks \
  --claim "This paper claims X reduces Y by 32% (p<0.05)." \
  --source "Original abstract text here..."
```

またはファイル入力:

```bash
python -m htlf.pipeline \
  --mode ks \
  --claim /path/to/claim.txt \
  --source /path/to/source.txt \
  --alpha 0.7 \
  --beta 0.3
```

### 3) 事前算出済み KS39b スコアを注入

```bash
python -m htlf.pipeline \
  --mode ks \
  --claim "..." \
  --ks39b-confidence 0.81
```

---

## 統合スコア式

```text
final = α × ks39b_confidence + β × translation_fidelity × measurement_reliability
```

- `translation_fidelity = 1 - total_loss`
- `measurement_reliability = f(provenance_distribution)`
- `α, β` は CLI で調整可能（正規化されます）

### provenance tracking（Self-Other Boundary連携）

HTLF 側は各計測軸に provenance tag を付与します。

- `R_struct`: parser が mock なら `SELF`、LLM抽出なら `EXTERNAL`
- `R_context`: ヒューリスティックなら `SELF`、LLM-as-readerなら `EXTERNAL`
- `R_qualia`: 行動実験/heuristicなら `SELF`、LLM ensembleなら `EXTERNAL`
- `matcher`: sentence-transformers（ローカル）なら `SELF`、API呼び出しなら `EXTERNAL`

`SELF` 比率が高いほど `measurement_reliability` は上がり、`EXTERNAL` 比率が高いほど HTLF 側の寄与は自動的に減衰します。

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
                                     | KS39b score      |  |
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
  - `HTLFScorer` (`ks_integration.py`) 追加
  - `pipeline.py --mode ks` 追加
  - KS39b × HTLF 統合式の実装

---

## 主要ファイル

- `src/htlf/pipeline.py` — CLIエントリポイント
- `src/htlf/scorer.py` — 3軸スコア計算
- `src/htlf/ks_integration.py` — KS39b統合インターフェース
- `docs/research/htlf-qualia-protocol.md` — Phase 3 プロトコル
