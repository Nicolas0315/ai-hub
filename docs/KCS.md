# KCS — Katala Coding Series

> Design: Youta Hilono  
> Implementation: Shirokuma (OpenClaw AI)  
> Date: 2026-03-01  
> Origin: KS40c (5-axis HTLF) → self-referential application

---

## 1. Core Thesis

**「コーディングは翻訳である」**

設計意図（人間の概念空間）→ コード（形式言語空間）の変換において、必ず情報損失が発生する。KCSはHTLF（KS40c）の5軸モデルをこの翻訳プロセス自体に適用し、損失を可視化・定量化する。

## 2. Why Self-Reference Doesn't Collapse

KSシリーズが**無矛盾な公理系をモジュール的に構成**しているから、ゲーデル限界や自己言及のパラドックスを局所的に回避・突破している。

- R_struct / R_context / R_qualia / R_cultural / R_temporal はそれぞれ**独立した測定軸**
- 各軸は他の軸を検証できる（相互検証構造）
- ゲーデル的限界は「系全体を系の中で完全に記述する」時に生じるが、KCSは各軸が**局所的に別の軸を測定する**構造なのでパラドックスにならない
- 結果: 自己検証（`kcs.self_verify()`）が実用的なフィードバックループとして機能する

## 3. 5-Axis Code Translation Model

KS40cの5軸をコード生成プロセスに再解釈:

| Axis | Original (HTLF) | KCS Reinterpretation |
|------|-----------------|---------------------|
| R_struct | 記号構造の保存 | 設計意図 → コード構造の対応度 |
| R_context | 文脈情報の保存 | 哲学的/理論的背景のdocstring・コメントへの保存度 |
| R_qualia | 体験品質の保存 | API使い心地・命名・可読性（行動主義的: 観察可能な品質のみ） |
| R_cultural | 文化的概念の保存 | チーム規約・プロジェクト慣習への準拠度 |
| R_temporal | 時間的意味の保存 | 将来の進化に対する生存性（継承の脆さ、グローバル状態、テスト有無） |

Weight: 30% R_struct + 20% R_context + 20% R_qualia + 15% R_cultural + 15% R_temporal

## 4. What Changed (Transparency Gain)

AI→コード変換はブラックボックスだった。KCSが入ったことで:

- **共通の測定基盤**が設計者とAIの間に成立した
- 「R_contextが0.8」= 「哲学的文脈が20%落ちてる」と全員が同じ数字を見て判断できる
- クワイン的に翻訳の不確定性は消せないが、**どの軸でどれだけ損失しているかが可視化**された
- 修正がピンポイントで効くようになった

## 5. Operational Structure

```
人間 (設計意図)
  ↓ 指示
AI (翻訳・実装)
  ↓ 生成
コード
  ↓ 検証
KCS (5軸監査)
  ↓ 損失レポート
AI (修正)
  ↓ 再検証
KCS → Grade改善確認
```

指示・実行・監査・修正の全段階に異なるプレイヤー（人間 / AI / KCS）が関与し、**コーディングの透明性が局所的に向上**する。

## 6. Grading System

| Grade | Fidelity | Meaning |
|-------|----------|---------|
| S | ≥ 90% | 設計意図が高忠実度で保存されている |
| A | ≥ 80% | 良好。軽微な損失のみ |
| B | ≥ 65% | 改善余地あり。特定軸に損失集中 |
| C | ≥ 50% | 要修正。設計意図の半分が翻訳で失われている |
| D | ≥ 35% | 大幅な再実装が必要 |
| F | < 35% | 設計意図がほぼ保存されていない |

## 7. Philosophical Foundations

| Concept | Source | KCS Application |
|---------|--------|----------------|
| 翻訳の不確定性 | Quine | 設計→コードの「正しい翻訳」は一意に定まらない |
| デュエム-クワイン命題 | Duhem-Quine | コードの一部を単独でテストできない（ウェブ全体の整合性が必要） |
| パラダイム不可共約性 | Kuhn | フレームワーク世代間のAPI互換性断裂 |
| 著者の死 | Barthes | コードの「意図」は書き手が決めるのではなく読み手（実行環境・保守者）が再構成する |
| 無矛盾公理系のモジュール構成 | Hilbert/Gödel | 各測定軸を独立公理系として構成→自己参照パラドックス回避 |

## 8. Legal Domain Extensibility

**Date**: 2026-03-01  
**Origin**: #dev-katala-law（Nicolas × Youta × Shirokuma）

### 8.1 KCSと法律の翻訳構造

KCSは「設計意図→コード」の翻訳損失を測るが、法律には構造的に類似した翻訳チェーンが存在する:

```
立法意図 → 条文テキスト → 学説・判例 → 具体的事案適用
```

KCSの5軸は法律テキストの翻訳損失測定にそのまま再解釈可能:

| Axis | KCS (Code) | Legal Reinterpretation |
|------|-----------|----------------------|
| R_struct | 設計意図→コード構造対応度 | 立法意図→条文の論理構造保存度 |
| R_context | 哲学的背景のdocstring保存度 | 立法経緯・議事録の参照可能性 |
| R_qualia | API使い心地・命名・可読性 | 条文の「正義感」「保護したかったもの」の保存度 |
| R_cultural | チーム規約・プロジェクト慣習準拠 | 法体系の慣習（大陸法/英米法）への準拠度 |
| R_temporal | 将来の進化に対する生存性 | 条文の将来事案への適用可能性 + **Interpretation Selector**（後述） |

### 8.2 R_context Interpretation Selector

Youta の洞察により、法律で特有の「遡及的文脈充填」（判例が条文の意味を事後的に書き換える現象）は、R_contextにタイムスタンプ付き解釈体系セレクタを追加することで吸収できる:

```
条文テキスト T（不変）
  × 解釈体系 I_1950（R_context = 0.70）
  × 解釈体系 I_2026（R_context = 0.85）
  → current_context_selector: I_2026
```

これはKCSにも適用可能: **同一コードベースの「設計意図」が、チームの入れ替わりや技術パラダイムの変化で事後的に再解釈される**問題と同構造。レガシーコード理解にもInterpretation Selectorが使える。

### 8.3 法律固有の未解決問題

以下2点が5軸で処理できない場合、HTLF ⑥法・制度レイヤーの独立化が必要になる:

1. **強制力（Binding Force）**: 同じテキストでも「法律」と「学術論文」と「コード」では社会的効力が全く違う。5軸のどこにも「この記号列は人を拘束する」情報が乗らない
2. **制度的矛盾管理**: 学説対立が「バグ」ではなく「機能」。スマートコントラクトにおけるR_qualiaの致命的損失（「正義」「公平」の質感を失ったコードが機械的に人を害する問題）もここに接続する

### 8.4 KCSへの実装含意

法律ドメインへの拡張はBアプローチ（③サブレイヤー）で開始。KCSの `kcs.self_verify()` に Interpretation Selector を追加することで、「同一コードの設計意図が時代ごとに再解釈される」問題にも対応可能になる。

詳細設計: `docs/KATALA_SAMURAI_40.md` Section 11

## 9. Version History

| Version | Date | Changes |
|---------|------|---------|
| KCS-1a | 2026-03-01 | Initial: 5-axis code verification, self_verify(), Katala conventions |
| KCS-2a | 2026-03-01 | Legal domain extensibility: Interpretation Selector, binding force / institutional contradiction as open problems |

## 10. Related

- **KS40c/d**: Parent framework (5-axis HTLF + Legal extension) → `docs/KATALA_SAMURAI_40.md`
- **HTLF**: Holographic Translation Loss Framework → `docs/HTLF.md`
- **Implementation**: `src/katala_coding/kcs1a.py`
- **GitHub Issue**: #92
