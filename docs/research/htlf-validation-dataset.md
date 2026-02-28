# HTLF Phase 0: 検証データセット（科学論文→ニュース記事）

> Generated: 2026-02-28
> Author: Shirokuma (subagent, Phase 0)
> Purpose: R_struct, R_context の逆算ロジック検証用。10ペア。

## アノテーション基準

- **R_struct** (0-1): 論文の論理構造・数式・因果関係がニュース記事にどこまで保存されているか
- **R_context** (0-1): 前提条件・適用範囲・制約・先行研究との関係がどこまで保存されているか
- **R_qualia**: 科学論文→ニュースでは N/A に近い（両方とも自然言語レイヤー内の翻訳）。本データセットでは「トーンの忠実度」として補助的に記録

---

## Case 1: LIGO重力波検出

- **論文**: "Observation of Gravitational Waves from a Binary Black Hole Merger" — LIGO/Virgo Collaboration (2016)
- **DOI**: [10.1103/PhysRevLett.116.061102](https://doi.org/10.1103/PhysRevLett.116.061102)
- **主要主張**: 2つのブラックホール（36M☉ + 29M☉）の合体からの重力波信号 GW150914 を検出。一般相対論の予測 h(t) とマッチドフィルタリングで SNR > 5σ を達成。放出エネルギー ≈ 3M☉c²。
- **ニュース**: "Gravitational Waves Detected, Confirming Einstein's Theory" — NY Times, 2016-02-11
- **URL**: <https://www.nytimes.com/2016/02/12/science/ligo-gravitational-waves-black-holes-einstein.html>
- **ニュース主張**: 「アインシュタインの100年前の予測が確認された」「2つのブラックホールの衝突を検出」

| 軸 | 値 | 根拠 |
|----|-----|------|
| R_struct | 0.45 | 信号検出の統計的手法（マッチドフィルタ、SNR閾値）は完全に省略。波形テンプレートとの比較という核心的方法論が消失。「検出した」という結論のみ保存 |
| R_context | 0.55 | 一般相対論の予測という文脈は保持。ただし40年以上の間接検出の歴史（Hulse-Taylor連星）、LIGO建設の30年の経緯、他の検出器との関係は大幅に圧縮 |

---

## Case 2: ヒッグス粒子発見

- **論文**: "Observation of a new boson at a mass of 125 GeV with the CMS experiment at the LHC" — CMS Collaboration (2012)
- **DOI**: [10.1016/j.physletb.2012.08.021](https://doi.org/10.1016/j.physletb.2012.08.021)
- **主要主張**: pp衝突データ (√s = 7, 8 TeV) から、γγ, ZZ, WW, ττ, bb の5崩壊チャネルで 125.3 ± 0.6 GeV に新粒子を観測。局所的有意度 5.0σ。標準模型ヒッグスと無矛盾。
- **ニュース**: "Physicists Find Elusive Particle Seen as Key to Universe" — NY Times, 2012-07-04
- **URL**: <https://www.nytimes.com/2012/07/05/science/cern-physicists-may-have-found-higgs-boson-particle.html>
- **ニュース主張**: 「宇宙の鍵となる粒子を発見」「神の粒子」

| 軸 | 値 | 根拠 |
|----|-----|------|
| R_struct | 0.30 | 5つの崩壊チャネルの個別分析、統計的有意度の計算方法、質量分解能、バックグラウンド推定はすべて消失。「5σで発見」という数値のみ一部保存 |
| R_context | 0.40 | 標準模型の文脈は言及あり。ただし自発的対称性の破れ、ヒッグス機構による質量付与のメカニズム、他の質量生成機構の可能性は省略。「神の粒子」という誤解を招くラベルが付加 |

---

## Case 3: ブラックホール初撮影（M87*）

- **論文**: "First M87 Event Horizon Telescope Results. I. The Shadow of the Supermassive Black Hole" — EHT Collaboration (2019)
- **DOI**: [10.3847/2041-8213/ab0ec7](https://doi.org/10.3847/2041-8213/ab0ec7)
- **主要主張**: 1.3mm VLBI で M87* の降着流と影（shadow）を直径 42±3 μas で撮像。一般相対論から予測される Kerr ブラックホールのシャドウ径と整合。質量 (6.5±0.7)×10⁹ M☉。
- **ニュース**: "First Ever Black Hole Image Released" — BBC, 2019-04-10
- **URL**: <https://www.bbc.com/news/science-environment-47873592>
- **ニュース主張**: 「史上初のブラックホールの写真」

| 軸 | 値 | 根拠 |
|----|-----|------|
| R_struct | 0.25 | VLBI干渉法、画像再構成アルゴリズム（CLEAN, RML等）、キャリブレーション手法はすべて省略。「写真」という表現が干渉計データからの再構成画像という本質を隠蔽 |
| R_context | 0.45 | ブラックホールの存在は文脈として保持。ただしEHTが地球サイズの仮想望遠鏡であること、4つの独立した画像再構成チームの検証プロセス、他の質量測定との整合性は大幅に簡略化 |

---

## Case 4: ペレルマンによるポアンカレ予想の証明

- **論文**: "The entropy formula for the Ricci flow and its geometric applications" — Perelman, G. (2002)
- **URL**: [arXiv:math/0211159](https://arxiv.org/abs/math/0211159)
- **主要主張**: Ricci フローにエントロピー汎関数 W(g,f,τ) を導入し、non-collapsing定理を証明。Hamilton プログラムの主要障害（特異点の分類と手術操作）を解決。
- **ニュース**: "Russian Reports He Has Solved a Celebrated Math Problem" — NY Times, 2003-04-15
- **URL**: <https://www.nytimes.com/2003/04/15/science/russian-reports-he-has-solved-a-celebrated-math-problem.html>
- **ニュース主張**: 「ロシア人数学者が100年来の難問を解いたと主張」

| 軸 | 値 | 根拠 |
|----|-----|------|
| R_struct | 0.10 | Ricci フロー、エントロピー汎関数、手術操作、Hamilton プログラムの技術的内容はほぼ完全に消失。「証明した」という結論のみ |
| R_context | 0.50 | 100年来の未解決問題、ミレニアム賞金100万ドル、トポロジーの基本問題であることは報道。ただしThurston幾何化予想との関係、Hamiltonの30年の研究との連続性は薄い |

---

## Case 5: CRISPR-Cas9 遺伝子編集

- **論文**: "A Programmable Dual-RNA–Guided DNA Endonuclease in Adaptive Bacterial Immunity" — Jinek, M., Chylinski, K., Fonfara, I., Hauer, M., Doudna, J.A., Charpentier, E. (2012)
- **DOI**: [10.1126/science.1225829](https://doi.org/10.1126/science.1225829)
- **主要主張**: Cas9はcrRNAとtracrRNAのデュアルRNA構造によりDNAを部位特異的に切断する。chimeric single-guide RNA (sgRNA) を設計すれば任意の配列を標的にできる。
- **ニュース**: "Scientists Discover Double-Helix-Snipping utilidad Called CRISPR" — Wired, 2013-02
- **URL**: <https://www.wired.com/2013/02/crispr-technique/>
- **ニュース主張**: 「DNAを自在に編集できる革命的ツール」

| 軸 | 値 | 根拠 |
|----|-----|------|
| R_struct | 0.35 | sgRNAの設計原理、PAM配列の制約、in vitroでの切断実験の詳細は消失。「プログラム可能なDNA切断」という概念は保存 |
| R_context | 0.35 | 細菌の適応免疫機構としての起源は多くの記事で省略。ZFN/TALENとの技術比較、off-target効果の制約も未言及 |

---

## Case 6: 量子超越性（Google Sycamore）

- **論文**: "Quantum supremacy using a programmable superconducting processor" — Arute, F. et al. (2019)
- **DOI**: [10.1038/s41586-019-1666-5](https://doi.org/10.1038/s41586-019-1666-5)
- **主要主張**: 53量子ビットSycamoreプロセッサでランダム量子回路サンプリングタスクを200秒で実行。古典計算機では約10,000年と推定（cross-entropy benchmarkingで検証）。
- **ニュース**: "Google Claims to Achieve Quantum Supremacy" — Financial Times, 2019-09-20
- **URL**: <https://www.ft.com/content/b9bb4e54-dbc1-11e9-8f9b-77216ebe1f17>
- **ニュース主張**: 「Googleが量子コンピュータで古典コンピュータを超えた」

| 軸 | 値 | 根拠 |
|----|-----|------|
| R_struct | 0.30 | ランダム回路サンプリングという特定タスクの性質、cross-entropy benchmark の定義、ノイズモデル、fidelity推定は消失。「200秒 vs 10,000年」の数値のみ流通 |
| R_context | 0.35 | 「量子超越性」の定義（任意のタスクではなく特定タスクでの優位性）が多くの記事で曖昧。IBMの反論（古典で2.5日で可能）は一部報道のみ。実用的量子計算との距離感が不足 |

---

## Case 7: ワイルズによるフェルマーの最終定理の証明

- **論文**: "Modular elliptic curves and Fermat's Last Theorem" — Wiles, A. (1995)
- **DOI**: [10.2307/2118559](https://doi.org/10.2307/2118559)
- **主要主張**: 半安定楕円曲線に対する谷山-志村予想を証明（= Frey曲線の非存在 = フェルマーの最終定理）。主要手法: Galois表現の変形理論、Hecke環、Selmer群。
- **ニュース**: "At Last, Shout of 'Eureka!' In Age-Old Math Mystery" — NY Times, 1993-06-24
- **URL**: <https://www.nytimes.com/1993/06/24/us/at-last-shout-of-eureka-in-age-old-math-mystery.html>
- **ニュース主張**: 「350年間の数学の謎がついに解かれた」

| 軸 | 値 | 根拠 |
|----|-----|------|
| R_struct | 0.05 | Galois表現、モジュラー形式、楕円曲線の関係は技術的に報道不可能。証明の内部構造は完全に失われ、「証明した」という事実のみ |
| R_context | 0.55 | 350年の歴史、フェルマーの余白の逸話、ワイルズの7年の秘密研究は豊かに報道。ただし谷山-志村予想の位置づけ、Frey-Ribet-Serreの貢献チェーンは省略される傾向 |

---

## Case 8: 超伝導体LK-99騒動

- **論文**: "The First Room-Temperature Ambient-Pressure Superconductor" — Lee, S. et al. (2023)
- **URL**: [arXiv:2307.12008](https://arxiv.org/abs/2307.12008)
- **主要主張**: Cu置換鉛アパタイト (Pb₁₀₋ₓCuₓ(PO₄)₆O) が室温常圧で超伝導を示す。Tc > 400K。抵抗ゼロとマイスナー効果を主張。
- **ニュース**: "Scientists claim high-temp superconductor breakthrough; skeptics abound" — Ars Technica, 2023-07-27
- **URL**: <https://arstechnica.com/science/2023/07/room-temperature-superconductor-claim-heats-up-scientific-skepticism/>
- **ニュース主張**: 「室温超伝導体の発見を主張、懐疑論も」

| 軸 | 値 | 根拠 |
|----|-----|------|
| R_struct | 0.20 | 結晶構造、電気抵抗測定の詳細、磁気浮上の定量データは省略。ただしArs Technicaは比較的技術的報道で、主張の構造は一部保存 |
| R_context | 0.65 | 室温超伝導の歴史的背景、過去の偽陽性（Dias事件等）、再現実験の必要性は良く報道された。査読前プレプリントであることも明記。この件は文脈報道が比較的良好だった例 |

---

## Case 9: AlphaFold2によるタンパク質構造予測

- **論文**: "Highly accurate protein structure prediction with AlphaFold" — Jumper, J. et al. (2021)
- **DOI**: [10.1038/s41586-021-03819-2](https://doi.org/10.1038/s41586-021-03819-2)
- **主要主張**: CASP14コンペでGDT > 92.4を達成（中央値）。Evoformer + Structure Moduleアーキテクチャ。MSA表現とペア表現の反復的精緻化。end-to-end微分可能。
- **ニュース**: "DeepMind's AI makes gigantic leap in solving protein structures" — Nature News, 2020-11-30
- **URL**: <https://www.nature.com/articles/d41586-020-03348-4>
- **ニュース主張**: 「AIが50年来のタンパク質折りたたみ問題を解決」

| 軸 | 値 | 根拠 |
|----|-----|------|
| R_struct | 0.35 | Evoformerのattention機構、MSA処理、構造精緻化ループの技術詳細は省略。GDTスコアとCASP14での圧倒的成績は保存。「end-to-end」という概念は言及あり |
| R_context | 0.50 | 50年来の問題という文脈あり。ただしCASPコンペの評価方法、GDTの定義、予測精度と実験的構造決定（X線/cryo-EM）との関係、膜タンパク質等の限界は不足 |

---

## Case 10: 暗黒エネルギーの発見（加速膨張）

- **論文**: "Observational Evidence from Supernovae for an Accelerating Universe and a Cosmological Constant" — Riess, A.G. et al. (1998)
- **DOI**: [10.1086/300499](https://doi.org/10.1086/300499)
- **主要主張**: Ia型超新星の光度距離-赤方偏移関係から、宇宙膨張が加速していることを発見。Ω_Λ > 0 を 99.7% C.L. (3σ) で示唆。宇宙定数 Λ の復活。
- **ニュース**: "Astronomers See a Cosmic Antigravity Force at Work" — NY Times, 1998-02-22
- **URL**: <https://www.nytimes.com/1998/02/22/us/astronomers-see-a-cosmic-antigravity-force-at-work.html>
- **ニュース主張**: 「宇宙に反重力が働いている」

| 軸 | 値 | 根拠 |
|----|-----|------|
| R_struct | 0.25 | 標準光源としてのIa型超新星の較正、光度曲線フィッティング、系統誤差の処理、Bayesian解析は消失。「加速膨張」という結論のみ。「反重力」は構造的に不正確な翻訳 |
| R_context | 0.45 | 宇宙定数のアインシュタインによる導入と破棄の歴史は言及。ただしΩ_m + Ω_Λ = 1 の制約、CMBとの独立検証、Perlmutter グループとの並行発見は部分的にのみ |

---

## 統計サマリー

| 指標 | R_struct | R_context |
|------|----------|-----------|
| 平均 | 0.260 | 0.475 |
| 中央値 | 0.275 | 0.475 |
| 最小 | 0.05 (Case 7) | 0.35 (Cases 5,6) |
| 最大 | 0.45 (Case 1) | 0.65 (Case 8) |
| 標準偏差 | 0.113 | 0.094 |

### 観察

1. **R_struct は常に R_context より低い**: 全10ケースで R_struct < R_context。論文の技術的構造（数式・方法論）はニュース翻訳で最も失われやすい
2. **数学系（Case 4,7）は R_struct が極端に低い**: 純粋数学の証明構造はほぼ翻訳不可能
3. **文脈は比較的保存される**: 歴史的背景・社会的意義は報道のインセンティブと合致するため保存されやすい
4. **懐疑的報道は R_context が高い**: Case 8 (LK-99) は懐疑的文脈が豊富に報道され、R_context が最高値
5. **HTLF.md の定性的見積もり（数学→自然言語: R_struct=0.70）は楽観的**: 実データでは 0.05-0.45 の範囲。見積もりの再較正が必要

---

*10 cases collected. Ready for automated scoring pipeline development in Phase 1.*
