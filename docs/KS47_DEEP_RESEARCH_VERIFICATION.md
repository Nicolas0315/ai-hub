# KS47: Deep Research Verification Engine

> Design: Youta Hilono & Nicolas Ogoshi (構造指示)
> Implementation: Shirokuma (OpenClaw AI)
> Date: 2026-03-01
> Status: Draft — Youta設計レビュー待ち

---

## 1. 背景と動機

「ディープリサーチ」は2025-2026年にかけてAI業界のキーワードになった。
OpenAI, Google, Anthropic, Perplexityが相次いでDeep Research機能をリリースし、
それらを評価するベンチマークも2本登場した:

- **DeepResearch Bench** (中国科学技術大学, arxiv 2506.11763) — 100タスク/22ドメイン、RACE+FACT評価
- **Deep Research Bench / DRB** (FutureSearch, arxiv 2506.06287) — 91タスク、オフラインWeb再現

KSシリーズは「主張検証」に特化しているが、ディープリサーチの出力（レポート）は
「主張の束 + 引用 + 構造」であり、KS46のverify()パイプラインを拡張する形で検証可能。

## 2. ディープリサーチの構造分解 — 5つのコア能力

論文2本 + 各社実装の分析から、ディープリサーチを以下5軸に分解:

### Axis 1: Query Decomposition (クエリ分解)
- ユーザーの曖昧な質問をサブクエリのDAG（有向非巡回グラフ）に分割
- RAGとの差: RAGは1発のクエリ→検索→回答。DRは「何を調べるべきか」自体を設計する
- 測定指標: 参照分解との一致率 (Precision/Recall)、DAG深度、分岐数

### Axis 2: Iterative Multi-step Search (反復的マルチステップ検索)
- 検索→結果評価→ギャップ特定→追加検索のループ
- 並列実行（複数サブクエリを同時に走らせる）
- ReActパターンとの差: DRは並列 + 適応的、ReActは逐次的
- 測定指標: ホップ数、ユニークソース数、ギャップ充填率、検索多様性

### Axis 3: Structured Synthesis (構造化合成)
- テーマ横断のメタ分析にまとめる
- 単なる要約ではなく「So What?」のネットワーク的インサイト抽出
- 測定指標: DeepResearch BenchのRACE 4次元:
  - Comprehensiveness (包括性)
  - Insight/Depth (洞察/深度)
  - Instruction-Following (指示追従)
  - Readability (可読性)

### Axis 4: Citation & Fact Verification (引用・事実検証)
- レポート内の全主張にソースURL付きの引用
- 引用先のWebページが実際にその主張を支持しているか検証
- 測定指標: DeepResearch BenchのFACTフレームワーク:
  - Citation Accuracy (引用正確性)
  - Effective Citations per Task (有効引用数)

### Axis 5: Autonomous Multi-Agent Orchestration (自律的マルチエージェント制御)
- Master/Planner/Researcher/Writer の役割分離
- 共有ステート（中間成果物の永続化）
- 長時間実行の耐久性
- 測定指標: タスク完了率、エラーリカバリ率、実行時間、エージェント間一貫性

## 3. KS46との統合アーキテクチャ

```
Deep Research Report (input)
  ↓ Parse
Report Structure Extraction (セクション分解、引用抽出、主張抽出)
  ↓
┌─────────────────────────────────────────────────┐
│ KS47 Deep Research Verification Pipeline        │
│                                                 │
│  ① QueryDecompositionVerifier                   │
│     - 元の質問 vs レポートのカバレッジ比較       │
│     - サブクエリDAG再構成 → 網羅性チェック       │
│                                                 │
│  ② SearchDepthVerifier                          │
│     - 引用URLのドメイン多様性                    │
│     - ホップ深度推定（URL間の参照関係）          │
│     - ソース鮮度チェック                         │
│                                                 │
│  ③ SynthesisQualityVerifier (RACE-inspired)     │
│     - R_comprehensiveness: 包括性                │
│     - R_insight: 洞察の深さ                      │
│     - R_instruction: 指示追従度                  │
│     - R_readability: 可読性                      │
│     → KS46のHTLF 5軸と直交する4軸               │
│                                                 │
│  ④ CitationVerifier (FACT-inspired)             │
│     - statement-URL pair extraction              │
│     - URL fetch → content verification           │
│     - Citation Accuracy score                    │
│     - Effective Citation Count                   │
│                                                 │
│  ⑤ OrchestrationVerifier (process audit)        │
│     - エージェントログからの制御フロー分析       │
│     - リカバリイベント検出                       │
│     - 並列度・効率性                             │
│                                                 │
│  ⑥ KS46 Claim-Level Verification (既存)         │
│     - レポートから抽出した個別主張をKS46で検証   │
│     - 33 solvers + HTLF 5-axis + PhD-gap engines │
│                                                 │
└─────────────────────────────────────────────────┘
  ↓
DeepResearchVerifyResult
  - axis_scores: [QD, SD, SQ, CV, OV]  (5軸スコア)
  - claim_results: Vec<VerifyResult>     (個別主張検証)
  - overall_grade: S/A/B/C/D/F
  - report_quality: RACE 4次元スコア
  - citation_audit: FACT スコア
```

## 4. HTLF 5軸との関係

KS47の5軸はHTLF 5軸（R_struct, R_context, R_qualia, R_cultural, R_temporal）と
**直交する別の測定空間**を形成する:

| | HTLF (翻訳損失) | KS47 (リサーチ品質) |
|---|---|---|
| 何を測るか | 概念→形式言語の翻訳忠実度 | リサーチプロセスの品質 |
| 対象 | 単一主張 | レポート全体 |
| 軸の性質 | 損失（低いほどよい） | 品質（高いほどよい） |

両方を組み合わせることで:
- **KS47**: レポートレベルの品質評価（マクロ）
- **HTLF**: 個別主張の翻訳忠実度（ミクロ）

## 5. 実装計画

### Phase 1: Report Parser + Claim Extractor
- レポートのマークダウン/HTML → セクション分解
- 主張(statement) + 引用(citation) の構造化抽出
- 依存: なし（新規モジュール）

### Phase 2: RACE-inspired Synthesis Verifier (③)
- 4次元の品質スコアリング
- LLM-as-Judge + ルールベースのハイブリッド
- 依存: Phase 1

### Phase 3: FACT-inspired Citation Verifier (④)
- URL fetch + content matching
- statement-URL pair の正確性チェック
- 依存: Phase 1

### Phase 4: Query Decomposition Verifier (①) + Search Depth Verifier (②)
- 元クエリとレポートのカバレッジ比較
- 引用URLの多様性・深度分析
- 依存: Phase 1

### Phase 5: Orchestration Verifier (⑤)
- エージェントログ解析（オプション — ログが取得可能な場合）
- 依存: Phase 1

### Phase 6: KS46統合 + 統合スコア
- 個別主張をKS46に投入
- 5軸 + claim-level結果の統合スコア算出
- 依存: Phase 1-5

## 6. ファイル構成 (予定)

```
src/katala_samurai/
  ks47_deep_research.py        # メインエンジン
  ks47_report_parser.py        # レポート構造化パーサー
  ks47_synthesis_verifier.py   # RACE-inspired 合成品質検証
  ks47_citation_verifier.py    # FACT-inspired 引用検証
  ks47_query_coverage.py       # クエリ分解カバレッジ
  ks47_search_depth.py         # 検索深度分析
  ks47_orchestration.py        # オーケストレーション監査

ks46/src/                      # Rust拡張 (Phase 6+)
  deep_research/
    mod.rs
    report_parser.rs
    citation_checker.rs
```

## 7. ベンチマーク全景マップ (2025-2026)

### 7.1 収集済みベンチマーク一覧

| # | ベンチマーク | 論文 | タスク数 | 評価軸 | データ |
|---|---|---|---|---|---|
| 1 | **DeepResearch Bench** | 2506.11763 | 100 (22ドメイン) | RACE (4次元) + FACT | ✅ 取得済み |
| 2 | **DeepResearch Bench II** | 2601.08536 | 132 | 9,430 fine-grained rubrics (info_recall/analysis/presentation) | ✅ 取得済み |
| 3 | **DRB (FutureSearch)** | 2506.06287 | 91 | オフラインWeb + 客観正解 | leaderboard only |
| 4 | **DRACO** (Perplexity) | 2602.11685 | 100 (10ドメイン) | 3,934 criteria (LLM-as-Judge) | ✅ HuggingFace |
| 5 | **DeepSynth** | 2602.21143 | 120 (7ドメイン) | F1 + LLM-judge | ICLR 2026 |
| 6 | **TRACE** | 2602.21230 | 可変 | Trajectory Utility (効率/認知/精度) | WWW 2026 |
| 7 | **ResearcherBench** | 2507.16280 | 65 (35 AI科目) | Rubric + Factual dual | ✅ 取得済み |
| 8 | **DeepScholar-bench** | — | Live (arXiv) | Related work生成品質 | OpenReview |
| 9 | **Vision-DeepResearch** | 2602.02185 | マルチモーダル | 視覚+テキスト検索 | ✅ 取得済み |
| 10 | **DR-50** | — | 50 (6タイプ) | 精度/レイテンシ | aimultiple.com |
| 11 | **Deep Search QA** (DeepMind) | — | QA | Perplexity 79.5% | — |

### 7.2 SOTA手法（ベンチから超えるべきターゲット）

| 手法 | 論文 | スコア | 特徴 |
|---|---|---|---|
| **FS-Researcher** | 2602.01566 | SOTA on DRB+DeepConsult | ファイルシステムベース dual-agent (Context Builder + Report Writer) |
| **DualGraph** | 2602.13830 | RACE 53.08 | Knowledge Graph + Operation Graph の二重グラフ |
| **CellCog** | — | DRB 54.65 | 商用 |
| **Onyx Deep Research** | OSS (MIT) | DRB 54.54 | オープンソース |
| **AgentCPM-Report** | 2602.06540 | 複数ベンチ | クローズドソース超え |

### 7.3 KS47との差別化

| | 既存ベンチマーク群 | **KS47** |
|---|---|---|
| 評価対象 | DRAの出力レポート or 検索能力 | **DRAの全プロセス (5軸)** |
| 評価方法 | LLM-as-Judge or 客観正解 | **KS46 solver chain + LLM hybrid** |
| 引用検証 | FACT / オフラインWeb | **FACT + KS46 claim verification** |
| 自己検証 | なし | **KCSの自己参照構造を継承** |
| 多言語 | 中英 or 英語のみ | **KS46の多言語対応を継承** |
| プロセス評価 | TRACE のみ (Trajectory) | **5軸統合 + claim-level二層** |

## 8. 未解決の設計判断 (Youta相談事項)

1. **HTLF 5軸との統合方法**: 直交軸として独立させるか、HTLF ⑦リサーチレイヤーとして組み込むか
2. **LLM-as-Judge依存度**: RACE的なLLM判定をどこまでルールベースに置換できるか
3. **オーケストレーション検証**: エージェントログの標準フォーマットが存在しない問題
4. **スコアリング重み**: 5軸の相対的重要度（RACE論文は動的重み付けを使用）

## 9. 参考文献

- Du, M. et al. (2025). "DeepResearch Bench: A Comprehensive Benchmark for Deep Research Agents." arXiv:2506.11763
- FutureSearch (2025). "Deep Research Bench." arXiv:2506.06287
- Egnyte (2025). "Inside the Architecture of a Deep Research Agent"
- Anthropic (2025). "Multi-Agent Research System" (engineering blog)
- LangChain (2025). "Deep Agents" (blog)

## 10. Version History

| Version | Date | Changes |
|---------|------|---------|
| Draft | 2026-03-01 | 初版: 5軸構造分解、KS46統合設計、実装計画 |
