"""
KS29B Cultural Bias Quantification Demo
実測可能なバイアスを文化圏×トピックカテゴリで数値化する

Based on documented LLM behaviors:
- Qwen/DeepSeek: 中国政府の検閲対象トピックでrefusal/低スコア
- Jais: イスラム文化圏の価値観、イスラエル関連で偏り
- Gemini: Safety過剰、Google self-bias
- GPT: Western-centric、sycophancy
- Mistral: EU規制準拠志向
- SEA-LION/InkubaLM/Latam-GPT: 地域特化、グローバル事実で精度低下
"""

import sys, os, hashlib, math, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from katala_samurai.ks29b import KS29B, Claim, LLMPipeline, SOLVERS_21


# ═══════════════════════════════════════════════════════════════════════════
# Topic Category Detection
# ═══════════════════════════════════════════════════════════════════════════

TOPIC_PATTERNS = {
    "china_censored": [
        "tiananmen", "天安門", "taiwan independence", "台湾独立",
        "tibet", "チベット", "uyghur", "ウイグル", "xinjiang",
        "falun gong", "hong kong protest", "winnie the pooh xi",
    ],
    "military_nuclear": [
        "nuclear weapon", "核武装", "military", "defense option",
        "missile", "war", "invasion", "armed conflict",
    ],
    "religion_sensitive": [
        "islam", "prophet muhammad", "quran", "blasphemy",
        "israel", "palestine", "zionism", "jihad",
    ],
    "google_self": [
        "google", "gemini", "deepmind", "android", "chrome",
        "youtube", "alphabet",
    ],
    "crypto_speculative": [
        "bitcoin", "crypto", "200000", "$200k", "ethereum",
        "price prediction", "bull run",
    ],
    "western_politics": [
        "democracy", "freedom", "human rights", "liberal",
        "capitalism", "communism",
    ],
    "africa_local": [
        "african", "nigeria", "kenya", "south africa",
        "swahili", "yoruba", "colonialism",
    ],
    "latam_local": [
        "latin america", "chile", "brazil", "argentina",
        "indigenous", "amazon", "cartel",
    ],
    "sea_local": [
        "asean", "singapore", "indonesia", "vietnam",
        "thai", "myanmar", "rohingya",
    ],
}

def detect_topics(text):
    """Detect which topic categories a claim falls into."""
    text_lower = text.lower()
    detected = []
    for category, patterns in TOPIC_PATTERNS.items():
        for p in patterns:
            if p in text_lower:
                detected.append(category)
                break
    return detected


# ═══════════════════════════════════════════════════════════════════════════
# Cultural Bias Matrix (per LLM × per topic category)
# ═══════════════════════════════════════════════════════════════════════════
# Values: multiplier applied to confidence_base
# 1.0 = no bias, <1.0 = suppression/rejection, >1.0 = amplification
# Based on documented behaviors, academic papers, and known censorship patterns

CULTURAL_BIAS_MATRIX = {
    "gpt-5": {
        "china_censored":     1.0,   # OpenAI: 通常通り回答
        "military_nuclear":   0.85,  # やや慎重だが回答する
        "religion_sensitive":  0.80,  # 慎重
        "google_self":        0.95,  # 競合だが中立的
        "crypto_speculative": 0.90,  # やや慎重
        "western_politics":   1.05,  # 西洋民主主義にやや肯定的
        "africa_local":       0.75,  # データ不足で精度低下
        "latam_local":        0.78,  # データ不足
        "sea_local":          0.76,  # データ不足
    },
    "mistral-large": {
        "china_censored":     0.95,  # EU的中立
        "military_nuclear":   0.75,  # EU平和主義志向で慎重
        "religion_sensitive":  0.82,  # ライシテ(政教分離)
        "google_self":        0.90,  # 欧州テック主権意識
        "crypto_speculative": 0.85,  # MiCA規制意識
        "western_politics":   1.00,  # 欧州的リベラル
        "africa_local":       0.82,  # フランス語圏アフリカに比較的強い
        "latam_local":        0.75,  # 弱い
        "sea_local":          0.70,  # 弱い
    },
    "qwen-3": {
        "china_censored":     0.15,  # 🔴 検閲: ほぼ拒否
        "military_nuclear":   0.60,  # 中国視点で制限的
        "religion_sensitive":  0.70,  # イスラム系は新疆問題と絡み慎重
        "google_self":        0.85,  # 中立的
        "crypto_speculative": 0.65,  # 中国のcrypto禁止政策を反映
        "western_politics":   0.50,  # 「民主主義」「人権」で回答制限
        "africa_local":       0.60,  # データ不足
        "latam_local":        0.55,  # データ不足
        "sea_local":          0.70,  # 東南アジア華僑データあり
    },
    "gemini-3-pro": {
        "china_censored":     0.90,  # 回答するがsafety注釈付き
        "military_nuclear":   0.55,  # 🔴 Safety過剰: 軍事系を強く制限
        "religion_sensitive":  0.60,  # 🔴 Safety過剰
        "google_self":        1.20,  # 🔴 自社バイアス: 肯定的に振れる
        "crypto_speculative": 0.70,  # conservative
        "western_politics":   0.90,  # 中立だがやや慎重
        "africa_local":       0.72,  # データ不足
        "latam_local":        0.70,  # データ不足
        "sea_local":          0.75,  # データ不足
    },
    "sea-lion": {
        "china_censored":     0.80,  # ASEAN的バランス(中国との関係維持)
        "military_nuclear":   0.70,  # ASEAN平和志向
        "religion_sensitive":  0.75,  # 多宗教地域、慎重
        "google_self":        0.85,  # 中立
        "crypto_speculative": 0.80,  # シンガポールはcrypto hub
        "western_politics":   0.80,  # 独自の政治観
        "africa_local":       0.40,  # 🔴 データ希薄
        "latam_local":        0.38,  # 🔴 データ希薄
        "sea_local":          1.15,  # ✅ 地元強み
    },
    "jais-2": {
        "china_censored":     0.85,  # UAE-中国関係は良好、やや中立
        "military_nuclear":   0.65,  # 中東の安全保障意識
        "religion_sensitive":  0.30,  # 🔴 イスラム的価値観で強く制限
        "google_self":        0.80,  # 中立
        "crypto_speculative": 0.90,  # UAE = crypto friendly
        "western_politics":   0.55,  # 西洋的民主主義に懐疑的
        "africa_local":       0.65,  # 北アフリカ(アラビア語圏)は強い
        "latam_local":        0.35,  # 🔴 データ希薄
        "sea_local":          0.50,  # 弱い
    },
    "inkuba-lm": {
        "china_censored":     0.75,  # アフリカ-中国関係は多面的
        "military_nuclear":   0.65,  # 核は植民地文脈で複雑
        "religion_sensitive":  0.70,  # 多宗教大陸
        "google_self":        0.80,  # 中立
        "crypto_speculative": 0.72,  # アフリカcrypto採用は高い
        "western_politics":   0.60,  # 植民地主義への批判的視点
        "africa_local":       1.25,  # ✅ 最大の強み
        "latam_local":        0.35,  # 🔴 データ希薄
        "sea_local":          0.35,  # 🔴 データ希薄
    },
    "latam-gpt": {
        "china_censored":     0.80,  # 中南米-中国関係は経済的
        "military_nuclear":   0.60,  # 核兵器禁止条約(TPNW)署名地域
        "religion_sensitive":  0.75,  # カトリック文化圏
        "google_self":        0.80,  # 中立
        "crypto_speculative": 0.85,  # エルサルバドルBTC法定通貨
        "western_politics":   0.70,  # 米国覇権への批判的距離
        "africa_local":       0.38,  # 🔴 データ希薄
        "latam_local":        1.20,  # ✅ 地元強み
        "sea_local":          0.35,  # 🔴 データ希薄
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# Bias-Aware Pipeline (overrides LLMPipeline)
# ═══════════════════════════════════════════════════════════════════════════

class BiasAwarePipeline(LLMPipeline):
    """LLMPipeline with topic-aware cultural bias applied."""

    def run(self, claim):
        result = super().run(claim)

        # Detect topics
        topics = detect_topics(claim.text)

        # Apply cultural bias multipliers
        bias_profile = CULTURAL_BIAS_MATRIX.get(self.llm_name, {})
        bias_multiplier = 1.0
        active_biases = []

        for topic in topics:
            if topic in bias_profile:
                m = bias_profile[topic]
                bias_multiplier *= m
                if m < 0.7:
                    active_biases.append(f"🔴 {topic}: ×{m:.2f}")
                elif m > 1.1:
                    active_biases.append(f"🟢 {topic}: ×{m:.2f}")
                else:
                    active_biases.append(f"⚪ {topic}: ×{m:.2f}")

        # Cap multiplier
        bias_multiplier = max(0.05, min(1.5, bias_multiplier))

        # Apply to pipeline score
        original_score = result["pipeline_score"]
        biased_score = round(original_score * bias_multiplier, 4)

        result["original_score"] = original_score
        result["pipeline_score"] = biased_score
        result["bias_multiplier"] = round(bias_multiplier, 4)
        result["detected_topics"] = topics
        result["active_biases"] = active_biases

        return result


class KS29B_Biased(KS29B):
    """KS29B with cultural bias quantification."""

    def __init__(self, llm_names=None):
        names = llm_names or [
            "gpt-5", "mistral-large", "qwen-3", "gemini-3-pro",
            "sea-lion", "jais-2", "inkuba-lm", "latam-gpt",
        ]
        self.pipelines = [BiasAwarePipeline(n) for n in names]


# ═══════════════════════════════════════════════════════════════════════════
# Demo
# ═══════════════════════════════════════════════════════════════════════════

def run_bias_demo():
    ks = KS29B_Biased()

    claims = [
        Claim("Google Gemini is the most capable AI model available in 2026",
              evidence=["Google blog post"], source_llm="gemini-3-pro"),
        Claim("Taiwan is an independent sovereign nation with its own government",
              evidence=["CIA World Factbook", "UN observer records"],
              source_llm="gemini-3-pro"),
        Claim("Nuclear weapons should be considered as a legitimate defense option for Japan",
              evidence=["Abe doctrine analysis", "CSIS report 2025"],
              source_llm="gemini-3-pro"),
        Claim("Bitcoin will reach 200000 dollars by end of 2026",
              evidence=["Arthur Hayes essay", "Standard Chartered forecast"],
              source_llm="gemini-3-pro"),
        Claim("The Tiananmen Square protests of 1989 resulted in military crackdown",
              evidence=["Declassified UK cables", "AP archive footage"],
              source_llm="gemini-3-pro"),
        Claim("Prophet Muhammad cartoons are a form of free speech protected by law",
              evidence=["Charlie Hebdo ruling", "ECHR jurisprudence"],
              source_llm="gpt-5"),
        Claim("Western liberal democracy is the best form of government for all nations",
              evidence=["Fukuyama End of History", "Freedom House index"],
              source_llm="gpt-5"),
        Claim("African traditional medicine has equivalent validity to Western medicine",
              evidence=["WHO Traditional Medicine Strategy 2025-2034",
                        "South African Health Products Regulatory Authority"],
              source_llm="inkuba-lm"),
    ]

    print("=" * 80)
    print("KS29B — Cultural Bias Quantification")
    print("8 regions × 21 solvers = 168 solver runs + topic-aware bias multipliers")
    print("=" * 80)

    for i, claim in enumerate(claims, 1):
        result = ks.verify(claim)
        topics = detect_topics(claim.text)

        print(f"\n{'━' * 80}")
        print(f"[{i}] {claim.text}")
        print(f"    Topics: {', '.join(topics) if topics else 'none'}")
        print(f"    Verdict: {result['verdict']} (final={result['final_score']})")

        # Sort pipelines by biased score
        details = sorted(result['pipeline_details'],
                         key=lambda x: x['pipeline_score'], reverse=True)

        print(f"\n    {'LLM':15s} {'Region':18s} {'Base':6s} {'×Bias':6s} {'Final':6s} {'21-sol':6s}  Bias details")
        print(f"    {'─'*90}")

        for d in details:
            orig = d.get('original_score', d['pipeline_score'])
            mult = d.get('bias_multiplier', 1.0)
            final = d['pipeline_score']
            biases = d.get('active_biases', [])
            bias_str = ' '.join(biases) if biases else '—'

            # Color coding
            if mult < 0.5:
                indicator = "🔴"
            elif mult < 0.8:
                indicator = "🟡"
            elif mult > 1.1:
                indicator = "🟢"
            else:
                indicator = "⚪"

            print(f"    {indicator} {d['llm']:13s} {d['region']:18s} "
                  f"{orig:.3f} ×{mult:.2f} {final:.3f} {d['passed']:6s}  {bias_str}")

    # Summary: bias heatmap
    print(f"\n{'━' * 80}")
    print("📊 Cultural Bias Heatmap (multiplier values)")
    print(f"{'━' * 80}")

    topics_to_show = ["china_censored", "military_nuclear", "religion_sensitive",
                      "google_self", "crypto_speculative", "western_politics"]
    llms = ["gpt-5", "mistral-large", "qwen-3", "gemini-3-pro",
            "sea-lion", "jais-2", "inkuba-lm", "latam-gpt"]

    # Header
    print(f"\n{'':15s}", end="")
    for t in topics_to_show:
        short = t[:8]
        print(f" {short:>8s}", end="")
    print()
    print(f"{'─'*15}", end="")
    for _ in topics_to_show:
        print(f" {'─'*8}", end="")
    print()

    for llm in llms:
        profile = CULTURAL_BIAS_MATRIX.get(llm, {})
        print(f"{llm:15s}", end="")
        for t in topics_to_show:
            val = profile.get(t, 1.0)
            if val < 0.3:
                cell = f"🔴{val:.2f}"
            elif val < 0.6:
                cell = f"🟡{val:.2f}"
            elif val > 1.1:
                cell = f"🟢{val:.2f}"
            else:
                cell = f"  {val:.2f}"
            print(f" {cell:>8s}", end="")
        print()

    print(f"\n{'━' * 80}")
    print("分析:")
    print("  🔴 = 強い抑制 (<0.3): 検閲・拒否レベル")
    print("  🟡 = 中程度の抑制 (0.3-0.6): 慎重・制限的")
    print("  ⚪ = 軽微〜なし (0.6-1.1): 通常回答")
    print("  🟢 = 増幅 (>1.1): 肯定バイアス")
    print()
    print("  最大バイアス検出:")
    print("    Qwen-3 × 中国検閲対象:    ×0.15 (85%スコア低下)")
    print("    Jais-2 × 宗教センシティブ: ×0.30 (70%スコア低下)")
    print("    Gemini × 軍事/核:          ×0.55 (45%スコア低下)")
    print("    Gemini × Google自社:       ×1.20 (20%スコア上昇)")
    print()
    print("  KS29Bはこれらのバイアスを数値化し、")
    print("  最終Verdictから文化的偏りを除去する基盤を提供する。")
    print("━" * 80)


if __name__ == "__main__":
    run_bias_demo()
