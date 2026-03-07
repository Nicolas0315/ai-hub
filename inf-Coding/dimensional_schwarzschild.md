# [Katala思考済] Dimensional Gradient Schwarzschild Solution

## 1. 目的
重力場を「固定された4次元時空の曲率」ではなく、「局所的な次元 $D(r)$ の勾配」として再定義し、シュヴァルツシルト解を次元変動の観点から導出する。

## 2. 前提公理 (from L3)
- $D(r)$ は動径 $r$ の関数であり、無限遠で $D(\infty) = n = 3$ (空間次元) とする。
- 観測される計量 $g_{\mu\nu}$ は、次元スケーリング因子 $\omega(D) = \frac{\text{Vol}(D)}{\text{Vol}(n)}$ に依存する。

## 3. 次元の動径依存性
物理マッピングに基づき、重力ポテンシャル $\Phi(r) = -GM/r$ を次元の変化に関連付ける。

$$D(r) = n \cdot \exp\left( \alpha \cdot \frac{\Phi(r)}{c^2} \right)$$
ここで $\alpha$ は、計量と次元スケーリングの整合性を取るための調整定数である。

## 4. 計量の再構成
シュヴァルツシルト計量の $g_{00}$ 成分を、次元比 $\omega(r)$ を用いて表現する。

$$g_{00}(r) = - \left[ \frac{\text{Vol}(D(r))}{\text{Vol}(n)} \right]^\beta$$

弱場近似 ($|\Phi| \ll c^2$) において：
$\text{Vol}(D(r)) \approx \text{Vol}(n) + \text{Vol}'(n) \cdot (D(r) - n)$
$D(r) \approx n (1 + \alpha \Phi/c^2) = n + n\alpha \Phi/c^2$
$\omega(r) \approx 1 + \frac{n \text{Vol}'(n)}{\text{Vol}(n)} \alpha \frac{\Phi}{c^2}$

GRのシュヴァルツシルト解 $g_{00} \approx -(1 + 2\Phi/c^2)$ と一致させるための条件：
$$\beta \cdot \alpha \cdot \frac{n \text{Vol}'(n)}{\text{Vol}(n)} = 2$$

## 5. 特異点の再定義
$r \to 0$ において $\Phi \to -\infty$ となるため、$D(r) \to 0$ となる。
これは、特異点が「無限の密度」を持つ場所ではなく、「次元が0に収束し、幾何学的広がりを失った点」であることを意味する。
従来の一般相対性理論では $r=0$ で計算不能となるが、Katalaの枠組みでは $\text{Vol}(D)$ が $D \to 0$ で 0 に収束するため、物理量が有限の極限（または幾何学的な回収）を持つ可能性がある。

## 6. 次の課題
- 光の測地線方程式を $D(r)$ を含む形式で記述し、光の屈曲角への影響を計算する。
- $\alpha, \beta$ の物理的意味（宇宙定数やプランク長との関連）の特定。
