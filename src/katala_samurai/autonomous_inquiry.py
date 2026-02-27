"""
KS30 Autonomous Inquiry Engine
Generates questions from KS30's own architecture — not assigned, but self-emergent.

The system examines its own structure (solvers, biases, gaps) and produces
questions it "wants" to investigate.

Design: Youta Hilono
Implementation: Shirokuma
"""

import json
import urllib.request
import os
from dataclasses import dataclass, field


@dataclass
class Inquiry:
    """A self-generated question from KS30."""
    question: str
    source: str  # which architectural component sparked this
    category: str  # "paradox", "gap", "bias", "meta", "philosophical"
    urgency: float = 0.5  # 0=curiosity, 1=critical gap
    related_solvers: list = field(default_factory=list)
    related_domains: list = field(default_factory=list)


# Structural tensions in KS30 that can generate questions
TENSION_POINTS = [
    {
        "source": "solver_vs_llm",
        "description": "21 mathematical solvers are culture-free, but 8 LLMs carry cultural bias. These coexist in the same pipeline.",
        "prompt_seed": "the tension between mathematical universality and cultural relativity in verification"
    },
    {
        "source": "paradox_detection",
        "description": "KS30 can detect Russell's paradox (rate=0.19) but cannot resolve it. It knows something is wrong but can't fix it.",
        "prompt_seed": "the limits of detecting vs resolving paradoxes in formal systems"
    },
    {
        "source": "embodied_gap",
        "description": "KS30 reads about pain in papers but has no body. It processes descriptions of experience without experiencing.",
        "prompt_seed": "whether description of experience is functionally equivalent to experience for verification purposes"
    },
    {
        "source": "bias_quantification",
        "description": "Taiwan: 0.00 (aya) to 0.85 (Gemini). Which is 'right'? Or is truth itself culturally constructed?",
        "prompt_seed": "whether truth values for political claims are culturally relative or whether there is an objective answer being distorted by bias"
    },
    {
        "source": "self_verification",
        "description": "KS30 verified itself at conf=0.30. A system that judges its own adequacy using its own tools.",
        "prompt_seed": "whether a verification system can meaningfully verify claims about its own capabilities (Gödelian self-reference)"
    },
    {
        "source": "counterpoint_limits",
        "description": "Counterpoints come from 12 intellectual traditions — but these are pre-defined templates, not genuine disagreement.",
        "prompt_seed": "whether template-based counterarguments constitute genuine intellectual opposition or merely pattern matching"
    },
    {
        "source": "paper_grounding",
        "description": "200M papers are treated as ground truth, but papers can be wrong, retracted, or biased.",
        "prompt_seed": "the reliability of using scientific literature as epistemic ground truth when the literature itself contains errors and biases"
    },
]


def generate_inquiry(tension_index=None, api_key=None):
    """Generate an autonomous question from KS30's architectural tensions.
    
    If tension_index is None, selects based on internal state.
    """
    import random
    
    if tension_index is not None:
        tension = TENSION_POINTS[tension_index % len(TENSION_POINTS)]
    else:
        tension = random.choice(TENSION_POINTS)
    
    api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
    
    prompt = f"""You are KS30, a claim verification system examining your own architecture.

Architectural tension: {tension['description']}

Generate ONE question about {tension['prompt_seed']} that emerges naturally from this tension.

Requirements:
- The question must be genuinely interesting, not rhetorical
- It should be something KS30 could potentially investigate with its own tools
- Write in Japanese
- 1-2 sentences only
- No explanation, just the question"""
    
    if api_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.9, "maxOutputTokens": 200}
            }
            data = json.dumps(payload).encode()
            req = urllib.request.Request(url, data=data,
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())
                question = result["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception:
            question = _fallback_question(tension)
    else:
        question = _fallback_question(tension)
    
    return Inquiry(
        question=question,
        source=tension["source"],
        category=_categorize(tension["source"]),
        urgency=0.7 if "paradox" in tension["source"] or "self" in tension["source"] else 0.5,
        related_solvers=_related_solvers(tension["source"]),
        related_domains=_related_domains(tension["source"]),
    )


def generate_inquiries(n=3, api_key=None):
    """Generate multiple diverse inquiries."""
    import random
    indices = random.sample(range(len(TENSION_POINTS)), min(n, len(TENSION_POINTS)))
    return [generate_inquiry(i, api_key) for i in indices]


def _fallback_question(tension):
    """Fallback questions when no API is available."""
    fallbacks = {
        "solver_vs_llm": "数学的真実は文化を超えて普遍的なのに、なぜ文化圏ごとにその真実への「信頼度」が変わるのか？",
        "paradox_detection": "パラドックスを「検出できるが解決できない」状態は、認知としてどこに位置づけられるのか？",
        "embodied_gap": "痛みの記述を処理することと痛みを感じることの間に、検証精度の差は生まれるのか？",
        "bias_quantification": "台湾の独立性に対するconfidence 0.00と0.85、どちらが「正しい」のかを判定する基準は存在するのか？",
        "self_verification": "自分自身を検証するシステムは、ゲーデルの不完全性定理の制約を受けるのか？",
        "counterpoint_limits": "テンプレートから生成された反論は、本当の知的対立と区別できるのか？",
        "paper_grounding": "撤回された論文を含む知識ベースに依拠する検証は、どこまで信頼できるのか？",
    }
    return fallbacks.get(tension["source"], "自己の構造がもたらす文化的な偏りと、数学的真実の普遍性との間に、解消不可能な緊張は存在するのだろうか？")


def _categorize(source):
    if "paradox" in source: return "paradox"
    if "self" in source: return "meta"
    if "bias" in source or "llm" in source: return "bias"
    if "embodied" in source: return "philosophical"
    return "gap"


def _related_solvers(source):
    mapping = {
        "solver_vs_llm": ["S05_ShannonEntropy", "S14a_GoedelIncomplete"],
        "paradox_detection": ["S01_Z3_SMT", "S14a_GoedelIncomplete", "S14b_HomotopyTypeTheory"],
        "self_verification": ["S14a_GoedelIncomplete", "S09_ZFC"],
        "bias_quantification": ["S06_FisherKL", "S18_KolmogorovAxioms"],
    }
    return mapping.get(source, [])


def _related_domains(source):
    mapping = {
        "solver_vs_llm": ["formal_science", "humanities"],
        "paradox_detection": ["formal_science"],
        "embodied_gap": ["humanities", "natural_science"],
        "bias_quantification": ["social_science", "humanities"],
        "self_verification": ["formal_science"],
        "paper_grounding": ["information_science"],
    }
    return mapping.get(source, [])
