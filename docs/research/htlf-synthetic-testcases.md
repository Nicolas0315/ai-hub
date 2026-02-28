# HTLF Synthetic Test Cases (Phase 4/5)

Generated: 2026-02-28

5レイヤー（数学 / 形式言語 / 自然言語 / 音楽 / 創作）を横断する合成テストケース。
各ケースには手動アノテーション（想定R値）を付与。

## 追加10ペア

1) 数学→形式言語
- Source: `f(x)=x^2+1 を微分すると f'(x)=2x`
- Target: `def df(x): return 2*x`
- 予想: R_struct=0.90, R_context=0.72, R_qualia=0.00

2) 形式言語→数学
- Source: `for i in range(n): s += i`
- Target: `s = Σ_{i=0}^{n-1} i`
- 予想: R_struct=0.86, R_context=0.66, R_qualia=0.00

3) 数学→自然言語
- Source: `a^2+b^2=c^2`
- Target: `直角三角形では斜辺の二乗は他の二辺の二乗和に等しい`
- 予想: R_struct=0.72, R_context=0.58, R_qualia=0.02

4) 自然言語→数学
- Source: `全ての実数xについてxの二乗は0以上`
- Target: `∀x∈R, x^2 ≥ 0`
- 予想: R_struct=0.82, R_context=0.61, R_qualia=0.01

5) 音楽→自然言語
- Source: `slow minor melody with delayed resolution and crescendo`
- Target: `短調でゆっくり始まり、解決を遅らせながら緊張を高める旋律`
- 予想: R_struct=0.44, R_context=0.36, R_qualia=0.22

6) 自然言語→音楽
- Source: `嵐の前の静けさから、急激な爆発に移る`
- Target: `quiet intro -> sudden fortissimo burst`
- 予想: R_struct=0.38, R_context=0.33, R_qualia=0.27

7) 音楽→創作
- Source: `staccato rhythm, bright brass accents`
- Target: `断続的な短い筆致と高彩度の黄・金のアクセント`
- 予想: R_struct=0.34, R_context=0.41, R_qualia=0.54

8) 創作→音楽
- Source: `渦巻く黒と群青、中心に細い白線`
- Target: `dark drone with thin high-pitch sustained tone`
- 予想: R_struct=0.29, R_context=0.35, R_qualia=0.46

9) 創作→自然言語
- Source: `灰色の街並みに一本の赤い線`
- Target: `無機質な都市空間に反抗の象徴が差し込む`
- 予想: R_struct=0.52, R_context=0.45, R_qualia=0.24

10) 形式言語→創作
- Source: `state machine: idle -> run -> stop`
- Target: `3つのノードを矢印で接続した遷移図の作品`
- 予想: R_struct=0.25, R_context=0.22, R_qualia=0.08

## 追加5件（指定カテゴリ）

11) 音楽→自然言語（情動強調）
- Source: `fragile piano motif with sudden silence`
- Target: `繊細なピアノ主題が突然の沈黙で断ち切られる`
- 予想: R_struct=0.40, R_context=0.34, R_qualia=0.30

12) 音楽→自然言語（身体感覚）
- Source: `heavy kick pulse and rising noise`
- Target: `重低音の脈動が身体を押し、ノイズが上昇して圧迫感を生む`
- 予想: R_struct=0.37, R_context=0.31, R_qualia=0.35

13) 創作→自然言語（抽象）
- Source: `青のグラデーションに不規則な亀裂`
- Target: `静けさの中に断絶の予感が走る`
- 予想: R_struct=0.48, R_context=0.39, R_qualia=0.28

14) 創作→自然言語（物語化）
- Source: `傾いた家と過剰な遠近法`
- Target: `世界が不安定で崩れそうな感覚を示す構図`
- 予想: R_struct=0.50, R_context=0.42, R_qualia=0.26

15) 数学→音楽（高難度）
- Source: `periodic sin wave with phase shift π/2`
- Target: `stable ostinato with delayed entry by half beat`
- 予想: R_struct=0.28, R_context=0.20, R_qualia=0.10

## メモ

- R_qualiaは音楽/創作が関与するほど高くなりやすい想定。
- 数学・形式言語ペアではR_qualiaはほぼ0として扱う。
- 本ケース群はPhase 4分類器とPhase 5 E2Eテストの入力雛形として利用。