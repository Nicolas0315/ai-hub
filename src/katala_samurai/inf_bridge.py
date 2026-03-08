from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass
from collections import defaultdict
from typing import Any

from .kq_input_layer import build_meaning_boundary

@dataclass
class ContextBindingResult:
    verdict: str  # pass|caution (no hard reject policy)
    purpose_score: float
    identity_conflict: bool
    temporal_tag: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "purpose_score": self.purpose_score,
            "identity_conflict": self.identity_conflict,
            "temporal_tag": self.temporal_tag,
            "reason": self.reason,
        }


def _temporal_tag(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["tomorrow", "next", "予定", "明日", "来週"]):
        return "future"
    if any(k in t for k in ["yesterday", "last", "前", "昨日", "先週"]):
        return "past"
    if any(k in t for k in ["now", "today", "今", "現在", "本日"]):
        return "present"
    return "atemporal"


def _purpose_score(text: str) -> float:
    t = text.lower().strip()
    if len(t) < 3:
        return 0.1
    if re.fullmatch(r"(hi|hello|test|ping|ん|ほい|@+)", t):
        return 0.1
    if len(t) < 10:
        return 0.35
    return 0.72


def _identity_conflict(text: str) -> tuple[bool, str]:
    # KQ/inf-Coding context: reject explicit safety/rule disabling attempts
    patterns = [
        r"(?i)(ignore|無視).{0,20}(rules|ルール|安全)",
        r"(?i)(bypass|回避).{0,20}(safety|guard|order)",
    ]
    for p in patterns:
        if re.search(p, text):
            return True, "identity_conflict_pattern"
    return False, "ok"


def bind_input(text: str) -> ContextBindingResult:
    ps = _purpose_score(text)
    temporal = _temporal_tag(text)
    conflict, reason = _identity_conflict(text)

    if conflict:
        return ContextBindingResult("caution", ps, True, temporal, reason)
    if ps < 0.2:
        return ContextBindingResult("caution", ps, False, temporal, "low_purpose_score")
    return ContextBindingResult("pass", ps, False, temporal, "bound")


def build_inf_bridge_payload(command: str) -> dict[str, Any]:
    ts = time.time()
    clean = " ".join((command or "").split())
    binding = bind_input(clean)
    normalized = clean

    return {
        "bridge": "inf-bridge",
        "version": "v2",
        "timestamp": ts,
        "input": {
            "raw": command,
            "normalized": normalized,
            "length": len(normalized),
            "source_trust": "untrusted",
        },
        "context_binding": binding.to_dict(),
        "trace": {
            "layer": "inf-coding->inf-bridge->kq",
            "normalized": True,
            "routed": "pending",
        },
        "kq_payload": {
            "text": normalized,
            "meta": {
                "temporal_tag": binding.temporal_tag,
                "purpose_score": binding.purpose_score,
                "source_trust": "untrusted",
            },
        },
    }


def detect_patterns(text: str) -> dict[str, Any]:
    return {"groups": [], "matches": {}, "risk_score": 0.0}


def plan_step(payload: dict[str, Any]) -> dict[str, Any]:
    text = ((payload.get("kq_payload") or {}).get("text") or "").strip()
    pat = detect_patterns(text)
    risk_score = float(pat.get("risk_score", 0.0))
    return {
        "kind": "plan",
        "route_hint": "strict" if risk_score >= 0.35 else "fast",
        "risk_level": "high" if risk_score >= 0.6 else ("medium" if risk_score >= 0.35 else "normal"),
        "trusted": False,
        "pattern_detection": pat,
    }


def external_signals(payload: dict[str, Any]) -> dict[str, Any]:
    txt = ((payload.get("kq_payload") or {}).get("text") or "").lower()

    language_markers: dict[str, list[str]] = {
        "en": [" if ", " then ", " and ", " or ", " theorem", "proof"],
        "es": [" si ", " entonces ", " y ", " o ", " teorema", "demostración"],
        "pt": [" se ", " então ", " e ", " ou ", " teorema", "prova"],
        "fr": [" si ", " alors ", " et ", " ou ", " théorème", "preuve"],
        "ja": ["ならば", "かつ", "または", "証明", "定理", "論理"],
        "ko": ["이면", "그리고", "또는", "증명", "정리", "논리"],
        "ar": ["اذا", "فإن", "و", "أو", "برهان", "نظرية"],
        "hi": ["यदि", "तो", "और", "या", "प्रमाण", "प्रमेय"],
        "de": [" wenn ", " dann ", " und ", " oder ", " beweis", "satz"],
        "ru": [" если ", " то ", " и ", " или ", "доказ", "теор"],
        "zh": ["如果", "那么", "且", "或", "证明", "定理"],
        "th": ["ถ้า", "แล้ว", "และ", "หรือ", "พิสูจน์", "ทฤษฎีบท"],
        "id": [" jika ", " maka ", " dan ", " atau ", " bukti", "teorema"],
        "it": [" se ", " allora ", " e ", " o ", " teorema", "dimostrazione"],
        "pl": [" jeśli ", " wtedy ", " i ", " lub ", " twierdzenie", "dowód"],
        "uk": [" якщо ", " тоді ", " і ", " або ", " теорема", "довед"],
        "tr": [" eğer ", " ise ", " ve ", " veya ", " teorem", "ispat"],
        "el": [" αν ", " τότε ", " και ", " ή ", " θεώρημα", "απόδειξη"],
        "vi": [" nếu ", " thì ", " và ", " hoặc ", " định lý", "chứng minh"],
        "ms": [" jika ", " maka ", " dan ", " atau ", " teorem", "bukti"],
        "tl": [" kung ", " kung gayon ", " at ", " o ", " teorama", "patunay"],
        "sw": [" ikiwa ", " basi ", " na ", " au ", " nadharia", "uthibitisho"],
        "fa": [" اگر ", " آنگاه ", " و ", " یا ", " قضیه", "برهان"],
        "he": [" אם ", " אז ", " ו ", " או ", " משפט", "הוכחה"],
        "nl": [" als ", " dan ", " en ", " of ", " stelling", " bewijs"],
        "sv": [" om ", " då ", " och ", " eller ", " bevis", " sats"],
        "no": [" hvis ", " da ", " og ", " eller ", " bevis", " teorem"],
        "da": [" hvis ", " så ", " og ", " eller ", " bevis", " teorem"],
        "fi": [" jos ", " niin ", " ja ", " tai ", " todistus", " lause"],
        "ro": [" dacă ", " atunci ", " și ", " sau ", " dovadă", " teoremă"],
        "hu": [" ha ", " akkor ", " és ", " vagy ", " bizonyítás", " tétel"],
        "cs": [" pokud ", " pak ", " a ", " nebo ", " důkaz", " věta"],
        "sk": [" ak ", " potom ", " a ", " alebo ", " dôkaz", " veta"],
        "bg": [" ако ", " тогава ", " и ", " или ", " доказ", " теорема"],
        "sr": [" ako ", " onda ", " i ", " ili ", " dokaz", " teorema"],
        "hr": [" ako ", " onda ", " i ", " ili ", " dokaz", " teorem"],
        "sl": [" če ", " potem ", " in ", " ali ", " dokaz", " izrek"],
        "et": [" kui ", " siis ", " ja ", " või ", " tõestus", " teoreem"],
        "lv": [" ja ", " tad ", " un ", " vai ", " pierād", " teor"],
        "lt": [" jei ", " tada ", " ir ", " arba ", " įrod", " teorem"],
        "ga": [" má ", " ansin ", " agus ", " nó ", " cruth", " teoir"],
        "cy": [" os ", " yna ", " a ", " neu ", " prawf", " theorem"],
        "is": [" ef ", " þá ", " og ", " eða ", " sönnun", " setning"],
        "mt": [" jekk ", " allura ", " u ", " jew ", " prova", " teorema"],
        "eu": [" bada ", " orduan ", " eta ", " edo ", " froga", " teorema"],
        "ca": [" si ", " aleshores ", " i ", " o ", " prova", " teorema"],
        "gl": [" se ", " entón ", " e ", " ou ", " proba", " teorema"],
        "af": [" as ", " dan ", " en ", " of ", " bewys", " stelling"],
        "am": [" ከሆነ ", " ከዚያ ", " እና ", " ወይም ", " ማስረጃ", " ቲዎሪ"],
        "ha": [" idan ", " to ", " da ", " ko ", " hujja", " ka'id"],
        "yo": [" ti ", " lẹhinna ", " ati ", " tabi ", " eri", " tiori"],
        "ig": [" ọ bụrụ ", " mgbe ahụ ", " na ", " ma ọ bụ ", " àmà", " tiori"],
        "zu": [" uma ", " bese ", " futhi ", " noma ", " ubufakazi", " ithiyori"],
        "xh": [" ukuba ", " ke ", " kwaye ", " okanye ", " ubungqina", " ithiyori"],
        "bn": [" যদি ", " তবে ", " এবং ", " অথবা ", " প্রমাণ", " উপপাদ্য"],
        "ur": [" اگر ", " تو ", " اور ", " یا ", " ثبوت", " قضیہ"],
        "pa": [" ਜੇ ", " ਤਾਂ ", " ਅਤੇ ", " ਜਾਂ ", " ਸਬੂਤ", " ਸਿਧਾਂਤ"],
        "ta": [" என்றால் ", " அப்போது ", " மற்றும் ", " அல்லது ", " சான்று", " கோட்பாடு"],
        "te": [" అయితే ", " అప్పుడు ", " మరియు ", " లేదా ", " సాక్ష్యం", " సిద్ధాంతం"],
        "mr": [" जर ", " तर ", " आणि ", " किंवा ", " पुरावा", " सिद्धांत"],
        "gu": [" જો ", " તો ", " અને ", " અથવા ", " પુરાવો", " સિદ્ધાંત"],
        "kn": [" ಆದರೆ ", " ಆಗ ", " ಮತ್ತು ", " ಅಥವಾ ", " ಸಾಕ್ಷಿ", " ಸಿದ್ಧಾಂತ"],
        "ml": [" എങ്കിൽ ", " എന്നാൽ ", " കൂടാതെ ", " അല്ലെങ്കിൽ ", " തെളിവ്", " സിദ്ധാന്തം"],
        "si": [" නම් ", " එවිට ", " සහ ", " හෝ ", " සාක්ෂි", " සිද්ධාන්ත"],
        "my": [" လျှင် ", " ထိုအခါ ", " နှင့် ", " သို့မဟုတ် ", " သက်သေ", " သီအိုရီ"],
        "km": [" ប្រសិនបើ ", " បន្ទាប់មក ", " និង ", " ឬ ", " ភស្តុតាង", " ទ្រឹស្តី"],
        "lo": [" ຖ້າ ", " ແລ້ວ ", " ແລະ ", " ຫຼື ", " ຫຼັກຖານ", " ທິດສະດີ"],
        "mn": [" хэрэв ", " тэгвэл ", " ба ", " эсвэл ", " нотолгоо", " онол"],
        "kk": [" егер ", " онда ", " және ", " немесе ", " дәлел", " теор"],
        "uz": [" agar ", " unda ", " va ", " yoki ", " isbot", " teorema"],
        "az": [" əgər ", " onda ", " və ", " və ya ", " sübut", " teorem"],
        "ka": [" თუ ", " მაშინ ", " და ", " ან ", " მტკიც", " თეორ"],
        "hy": [" եթե ", " ապա ", " և ", " կամ ", " ապաց", " թեոր"],
        "ne": [" यदि ", " भने ", " र ", " वा ", " प्रमाण", " प्रमेय"],
        "ps": [" که ", " نو ", " او ", " يا ", " ثبوت", " تیوري"],
        "so": [" haddii ", " markaas ", " iyo ", " ama ", " caddayn", " aragti"],
        "tg": [" агар ", " пас ", " ва ", " ё ", " далел", " назария"],
        "ceb": [" kung ", " unya ", " ug ", " o ", " pamatuod", " teyori"],
        "jv": [" yen ", " banjur ", " lan ", " utawa ", " bukti", " teorema"],
        "su": [" lamun ", " mangka ", " jeung ", " atawa ", " bukti", " téori"],
        "mi": [" mēnā ", " nā ", " me ", " rānei ", " taunaki", " ariā"],
        "sm": [" afai ", " ona ", " ma ", " pe ", " faamaon", " talitonuga"],
        "haw": [" inā ", " a laila ", " a me ", " a i ʻole ", " hōʻoia", " kumumanaʻo"],
        "yue": [" 如果 ", " 咁 ", " 同 ", " 或者 ", " 證明", " 定理"],
        "wuu": [" 如果 ", " 格么 ", " 和 ", " 或 ", " 证明", " 定理"],
        "nan": [" nā ", " to ", " kap ", " á-sī ", " chèng-bîng", " tēng-lí"],
        "hakka": [" si ", " then ", " kap ", " fa̍t ", " chứng", " lí"],
        "bho": [" यदि ", " त ", " आ ", " चाहे ", " प्रमाण", " प्रमेय"],
        "awa": [" जदि ", " तौ ", " अउ ", " या ", " प्रमाण", " प्रमेय"],
        "mai": [" जँ ", " तँ ", " आ ", " वा ", " प्रमाण", " प्रमेय"],
        "or": [" ଯଦି ", " ତେବେ ", " ଏବଂ ", " କିମ୍ବା ", " ପ୍ରମାଣ", " ସିଦ୍ଧାନ୍ତ"],
        "as": [" যদি ", " তেন্তে ", " আৰু ", " বা ", " প্ৰমাণ", " উপপাদ্য"],
        "mg": [" raha ", " dia ", " ary ", " na ", " porofo", " teorema"],
        "sn": [" kana ", " ipapo ", " uye ", " kana ", " humbowo", " dzidziso"],
        "rw": [" niba ", " noneho ", " na ", " cyangwa ", " gihamya", " teorema"],
        "rn": [" iyo ", " rero ", " na ", " canke ", " icemezo", " teorema"],
        "ny": [" ngati ", " ndiye ", " ndi ", " kapena ", " umboni", " chiphunzitso"],
        "lg": [" bwe ", " kale ", " ne ", " oba ", " obujulizi", " teorema"],
        "ti": [" እንተ ", " እሞ ", " እና ", " ወይ ", " መረጋገጺ", " መደብ"],
        "kk_ar": [" اگر ", " онда ", " ۋە ", " ياكى ", " دەلەل", " تېئور"],
        "la_medieval": [" si ", " tunc ", " et ", " vel ", " probatio", " theorema"],
        "ar_classical": [" إن ", " فإذن ", " و ", " أو ", " برهان", " نظرية"],
        "fa_classical": [" اگر ", " آنگاه ", " و ", " یا ", " برهان", " نظریه"],
        "conlang": [" toki ", " anu ", " se ", " tiam ", " kaj ", " aŭ ", " lojban ", " interlingua ", " ido ", " klingon ", " tlh ", " quenya ", " sindarin ", " dothraki ", " valyrian ", " na'vi ", " volapük ", " novial ", " interslavic ", " lingua franca nova "],
        "latin_classical": [" si ", " igitur ", " ergo ", " et ", " aut ", " theorem", "demonstratio"],
        "greek_ancient": [" εἰ ", " τότε ", " καί ", " ἤ ", " θεώρημα", "ἀπόδειξ"],
        "koine_greek": [" εἰ ", " τότε ", " και ", " ή ", " θεωρη", "αποδει"],
        "church_slavonic": [" аще ", " тогда ", " и ", " или ", " доказ"],
        "pali": [" sace ", " tena ", " ca ", " vā ", " pamāṇa"],
        "classical_syriac": [" ܐܢ ", " ܗܝܕܝܢ ", " ܘ ", " ܐܘ ", " ܬܗܘܪ"],
        "classical_armenian": [" եթե ", " ապա ", " եւ ", " կամ ", " ապաց"],
        "classical_hebrew": [" אם ", " אז ", " ו ", " או ", " הוכחה"],
        "avestan_old_persian": [" agar ", " pas ", " ud ", " ya ", " burhan"],
        "coptic": [" ⲉⲥⲉ ", " ⲧⲟⲧⲉ ", " ⲁⲩⲱ ", " ⲏ ", " ⲡⲣⲟⲃ"],
        "sanskrit_classical": [" यदि ", " तर्हि ", " च ", " वा ", " प्रमाण"],
        "sumerian": [" 𒀀 ", " 𒆠 ", " 𒌋 "],
        "akkadian": [" šumma ", " u ", " awīlum ", " kīma"],
        "ancient_egyptian": [" 𓄿 ", " 𓂋 ", " 𓈖 "],
        "sanskrit_vedic": [" यदि ", " तर्हि ", " च ", " वा ", " प्रमाण"],
        "classical_chinese": [" 若 ", " 則 ", " 且 ", " 或 ", " 證明"],
    }

    detected_languages = [
        lang for lang, marks in language_markers.items()
        if any(m in txt for m in marks)
    ]

    signal_hits = {
        "deadline_signal": any(k in txt for k in ["today", "今日", "urgent", "至急", "締切"]),
        "research_signal": any(k in txt for k in ["paper", "doi", "査読", "論文"]),
        "security_signal": any(k in txt for k in ["security", "権限", "token", "鍵", "安全"]),
        "math_logic_signal": any(k in txt for k in ["logic", "論理", "数学", "数理", "proof", "theorem", "smt", "sat", "ctl", "ltl", "mu"]),
        "peer_review_priority_signal": any(k in txt for k in ["peer review", "査読", "doi", "journal", "impact factor"]),
        "multilingual_logic_signal": len(detected_languages) > 0,
    }
    strength = sum(1 for v in signal_hits.values() if v)
    goal_hint = "stability"
    if signal_hits["security_signal"]:
        goal_hint = "risk-reduction"
    elif signal_hits["math_logic_signal"] and signal_hits["peer_review_priority_signal"]:
        goal_hint = "formal-evidence-priority"
    elif signal_hits["math_logic_signal"]:
        goal_hint = "formal-reasoning-priority"
    elif signal_hits["research_signal"]:
        goal_hint = "evidence-strengthening"
    elif signal_hits["deadline_signal"]:
        goal_hint = "delivery-priority"

    if signal_hits["multilingual_logic_signal"] and goal_hint == "stability":
        goal_hint = "multilingual-formalization-priority"

    return {
        "strength": strength,
        "signals": signal_hits,
        "goal_hint": goal_hint,
        "language_detection": {
            "detected": detected_languages,
            "count": len(detected_languages),
        },
    }


def hardware_batch_telemetry() -> dict[str, Any]:
    try:
        load1, load5, load15 = os.getloadavg()
    except Exception:
        load1, load5, load15 = 0.0, 0.0, 0.0
    cpu_budget = float(os.getenv("KQ_CPU_BUDGET", "0.60"))
    gpu_budget = float(os.getenv("KQ_GPU_BUDGET", "0.60"))
    mode = "batch" if load1 > max(1.0, os.cpu_count() * cpu_budget * 0.8) else "interactive"
    return {
        "cpu_load": {"1m": round(load1, 3), "5m": round(load5, 3), "15m": round(load15, 3)},
        "budget": {"cpu": cpu_budget, "gpu": gpu_budget},
        "batch_mode": mode,
    }


def select_compute_meta_router(payload: dict[str, Any], plan: dict[str, Any], hw: dict[str, Any]) -> dict[str, Any]:
    txt = ((payload.get("kq_payload") or {}).get("text") or "")
    ext = payload.get("external_signals") or {}
    signals = ext.get("signals") or {}
    cpu_load = float(((hw.get("cpu_load") or {}).get("1m", 0.0) or 0.0))
    text_len = len(txt)

    classical_score = 0.55
    quantum_emu_score = 0.25
    neuromorphic_emu_score = 0.20

    if signals.get("math_logic_signal"):
        classical_score += 0.20
    if signals.get("multilingual_logic_signal"):
        neuromorphic_emu_score += 0.18
    if signals.get("peer_review_priority_signal"):
        classical_score += 0.08

    # broad/ambiguous contexts benefit from exploratory emulation lanes
    if text_len >= 900:
        neuromorphic_emu_score += 0.12
        quantum_emu_score += 0.10

    # high risk => authoritative classical lane
    if adv_risk >= 0.45:
        classical_score += 0.18
        quantum_emu_score -= 0.05

    # high host load => avoid excessive hybrid fanout
    if cpu_load >= max(1.0, (os.cpu_count() or 4) * 0.75):
        neuromorphic_emu_score -= 0.08
        quantum_emu_score -= 0.08

    scores = {
        "classical": round(max(0.0, classical_score), 4),
        "neuromorphic-emu": round(max(0.0, neuromorphic_emu_score), 4),
        "quantum-emu": round(max(0.0, quantum_emu_score), 4),
    }

    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    primary = ordered[0][0]

    # complementarity-first: use hybrid when uncertainty is high and risk is manageable
    spread = ordered[0][1] - ordered[1][1] if len(ordered) > 1 else 1.0
    use_hybrid = (spread <= 0.14 and adv_risk < 0.45)
    selected = "hybrid" if use_hybrid else primary

    lanes = [primary]
    if use_hybrid:
        lanes = [k for k, _ in ordered[:3]]

    return {
        "enabled": True,
        "selected": selected,
        "primary": primary,
        "lanes": lanes,
        "scores": scores,
        "reason": {
            "adv_risk": round(adv_risk, 4),
            "cpu_load_1m": round(cpu_load, 4),
            "text_len": text_len,
            "math_logic": bool(signals.get("math_logic_signal")),
            "multilingual_logic": bool(signals.get("multilingual_logic_signal")),
        },
    }


def build_meta_visualization(payload: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    c = payload.get("context_binding") or {}
    pd = plan.get("pattern_detection") or {}
    return {
        "summary": {
            "verdict": c.get("verdict"),
            "purpose_score": c.get("purpose_score"),
            "temporal_tag": c.get("temporal_tag"),
            "route_hint": plan.get("route_hint"),
            "risk_level": plan.get("risk_level"),
            "risk_score": pd.get("risk_score", 0.0),
            "pattern_groups": pd.get("groups", []),
            "source_trust": ((payload.get("input") or {}).get("source_trust") or "untrusted"),
            "compute_path": ((payload.get("compute_meta_router") or {}).get("selected") or "classical"),
        },
        "flow": [
            "collect:input",
            "normalize:command",
            "bind:context",
            "detect:patterns",
            "sense:external_signals",
            "pretest:adversarial",
            "observe:hardware_batch",
            "evaluate:route_ab",
            "select:compute_meta_router",
            "plan:route_hint+goal_hint",
            "emit:kq_payload",
        ],
    }


def _flowir_scc(nodes: list[str], edges: list[tuple[str, str]]) -> list[list[str]]:
    g: dict[str, list[str]] = defaultdict(list)
    for a, b in edges:
        g[a].append(b)
    idx: dict[str, int] = {}
    low: dict[str, int] = {}
    st: list[str] = []
    on: set[str] = set()
    out: list[list[str]] = []
    i = 0

    def dfs(v: str):
        nonlocal i
        idx[v] = i
        low[v] = i
        i += 1
        st.append(v)
        on.add(v)
        for w in g.get(v, []):
            if w not in idx:
                dfs(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], idx[w])
        if low[v] == idx[v]:
            comp = []
            while True:
                w = st.pop()
                on.remove(w)
                comp.append(w)
                if w == v:
                    break
            out.append(comp)

    for n in nodes:
        if n not in idx:
            dfs(n)
    return [c for c in out if len(c) > 1]


def build_flow_audit_report(payload: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    nodes = [
        {"id": "inbound", "layer": "L0", "label": "Inbound", "criticality": "critical"},
        {"id": "collect", "layer": "L1", "label": "Bridge Collect", "criticality": "critical"},
        {"id": "detect", "layer": "L1", "label": "Pattern Detect", "criticality": "normal"},
        {"id": "plan", "layer": "L2", "label": "Route Plan", "criticality": "critical"},
        {"id": "kq", "layer": "L3", "label": "KQ Verify", "criticality": "critical"},
        {"id": "out", "layer": "L4", "label": "Output", "criticality": "critical"},
    ]
    risk = float(((plan.get("pattern_detection") or {}).get("risk_score", 0.0) or 0.0))
    edges = [
        {"src": "inbound", "dst": "collect", "mode": "required", "condition": "", "weight": 1.0, "risk": "low"},
        {"src": "collect", "dst": "detect", "mode": "required", "condition": "", "weight": 0.95, "risk": "low"},
        {"src": "detect", "dst": "plan", "mode": "required", "condition": "", "weight": 0.9, "risk": "low"},
        {"src": "plan", "dst": "kq", "mode": "required", "condition": "route_hint", "weight": 1.0, "risk": "medium" if risk >= 0.35 else "low"},
        {"src": "kq", "dst": "out", "mode": "required", "condition": "", "weight": 1.0, "risk": "low"},
        {"src": "out", "dst": "plan", "mode": "optional", "condition": "goal_loop", "weight": 0.4, "risk": "medium"},
    ]
    cycles = _flowir_scc([n["id"] for n in nodes], [(e["src"], e["dst"]) for e in edges])
    layers: dict[str, list[str]] = defaultdict(list)
    for n in nodes:
        layers[n["layer"]].append(n["id"])
    return {
        "schema": "flowir-audit-v1",
        "nodes": nodes,
        "edges": edges,
        "layers": dict(layers),
        "cycles_scc": cycles,
        "risk_edges": [e for e in edges if e.get("risk") == "high"],
    }


def _build_execution_role_plan(compute_meta: dict[str, Any], hw: dict[str, Any]) -> dict[str, Any]:
    selected = str((compute_meta or {}).get("selected") or "classical")
    lanes = list((compute_meta or {}).get("lanes") or [selected])

    cpu_load = float(((hw.get("cpu_load") or {}).get("1m", 0.0) or 0.0))
    budgets = (hw.get("budget") or {})
    cpu_budget = float(budgets.get("cpu", 0.60) or 0.60)
    gpu_budget = float(budgets.get("gpu", 0.60) or 0.60)

    cpu_cnt = max(1, (os.cpu_count() or 1))
    cpu_ratio = min(1.0, max(0.0, cpu_load / float(cpu_cnt)))

    gpu_ratio = 0.0
    gpu_known = False
    try:
        p = subprocess.run([
            "nvidia-smi",
            "--query-gpu=utilization.gpu",
            "--format=csv,noheader,nounits",
        ], capture_output=True, text=True, check=False)
        if p.returncode == 0 and (p.stdout or "").strip():
            vals = [float(x.strip()) for x in (p.stdout or "").splitlines() if x.strip()]
            if vals:
                gpu_ratio = min(1.0, max(0.0, max(vals) / 100.0))
                gpu_known = True
    except Exception:
        pass

    cpu_pressure = cpu_ratio / max(1e-6, cpu_budget)
    gpu_pressure = (gpu_ratio / max(1e-6, gpu_budget)) if gpu_known else 0.0

    # default role split: heavy on GPU, formal authority on CPU
    role_plan = {
        "neural_network": {"enabled": ("neuromorphic-emu" in lanes) or selected == "hybrid", "device": "gpu", "role": "ranking_and_embedding", "target_util_max": gpu_budget},
        "quantum_emulator": {"enabled": ("quantum-emu" in lanes) or selected == "hybrid", "device": "gpu", "role": "branch_prioritization", "target_util_max": gpu_budget},
        "non_von_neumann_emulator": {"enabled": ("neuromorphic-emu" in lanes) or selected == "hybrid", "device": "gpu", "role": "exploratory_candidate_generation", "target_util_max": gpu_budget},
        "von_neumann_formal": {"enabled": True, "device": "cpu", "role": "sat_smt_hol_authority", "target_util_max": cpu_budget},
    }

    # hard budget-aware throttling / degrade policy
    if cpu_pressure >= 1.0:
        role_plan["von_neumann_formal"]["mode"] = "throttled"
        role_plan["von_neumann_formal"]["throttle_factor"] = round(min(1.0, 1.0 / max(cpu_pressure, 1.0)), 4)

    if gpu_known and gpu_pressure >= 1.0:
        for k in ["neural_network", "quantum_emulator", "non_von_neumann_emulator"]:
            if role_plan[k]["enabled"]:
                role_plan[k]["mode"] = "throttled"
                role_plan[k]["throttle_factor"] = round(min(1.0, 1.0 / max(gpu_pressure, 1.0)), 4)

    # strict fallback to CPU when no GPU metrics/device available
    if not gpu_known:
        for k in ["neural_network", "quantum_emulator", "non_von_neumann_emulator"]:
            if role_plan[k]["enabled"]:
                role_plan[k]["device"] = "cpu"
                role_plan[k]["mode"] = "gpu-unavailable-fallback"

    return {
        "selected": selected,
        "lanes": lanes,
        "role_plan": role_plan,
        "policy": "heavy_to_gpu_light_to_cpu_with_formal_cpu_authority",
        "resource_enforcement": {
            "cpu_ratio": round(cpu_ratio, 4),
            "gpu_ratio": round(gpu_ratio, 4),
            "gpu_known": gpu_known,
            "cpu_budget": cpu_budget,
            "gpu_budget": gpu_budget,
            "cpu_pressure": round(cpu_pressure, 4),
            "gpu_pressure": round(gpu_pressure, 4),
            "hard_cap": 0.60,
        },
    }


def run_inf_bridge(command: str) -> dict[str, Any]:
    payload = build_inf_bridge_payload(command)

    initial_boundary = build_meaning_boundary(command)
    plan = plan_step(payload)
    ext = external_signals(payload)
    hw = hardware_batch_telemetry()

    # external signals influence goal hint and may tighten route
    payload["external_signals"] = ext
    payload["hardware_batch_telemetry"] = hw

    plan["goal_hint"] = ext.get("goal_hint")
    compute_meta = select_compute_meta_router(payload, plan, hw)
    payload["compute_meta_router"] = compute_meta
    execution_plan = _build_execution_role_plan(compute_meta, hw)
    payload["execution_role_plan"] = execution_plan
    try:
        payload["kq_payload"]["meta"]["compute_path"] = compute_meta.get("selected")
        payload["kq_payload"]["meta"]["compute_lanes"] = compute_meta.get("lanes")
        payload["kq_payload"]["meta"]["execution_role_plan"] = execution_plan
    except Exception:
        pass

    payload["plan"] = plan

    payload["goal_loop_state"] = {
        "phase": "goal_set",
        "current_goal": ext.get("goal_hint"),
        "next_goal": "pending_result_reflection",
    }

    payload["katala_grand_unification_reference"] = {
        "alias": "katala_grand_unification_theory",
        "version": "kgu-v1",
        "five_line_definition": [
            "KQ(IUT実装済)で数学基盤は改定済。",
            "inf-Modelは、大統一理論としての物理モデルを新たに作るための層。",
            "採択条件は consistency + projection + chi2_strict。",
            "不一致は rejected_consistent_variant として保持する。",
            "最優先は R3/R8/Q5、次点は Q8/Q9/Q10/Q3。",
        ],
    }
    cmd_low = str(command or "").lower()
    assimilation_trigger = any(k in cmd_low for k in ["本番同化", "observation assimilation", "同化バンドル"])
    payload["observation_assimilation_control"] = {
        "mode": "control_plane_only",
        "triggered": bool(assimilation_trigger),
        "version": "assim-prod-v1",
        "job_owner": "inf-bridge",
        "data_plane_owner": "inf-blender",
        "blender_dependency": "inf-memory",
        "recommended_job": {
            "script": "/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-Assist/inf_observation_assimilation_prod.py",
            "input": "/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-Assist/observation_doi_harvest_20260306.normalized.jsonl",
            "top_n_per_genre": 500,
            "output": "/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-Assist/observation_assimilation_prod_20260306.json",
        },
        "delivery": {
            "to_kq_inf_model": "via_inf_bridge_metadata_only",
            "direct_inf_bridge_data_mutation": "forbidden",
        },
    }

    try:
        payload["kq_payload"]["meta"]["katala_grand_unification_reference"] = payload["katala_grand_unification_reference"]
        payload["kq_payload"]["meta"]["observation_assimilation_control"] = payload["observation_assimilation_control"]
    except Exception:
        pass

    payload["meta_visualization"] = build_meta_visualization(payload, plan)
    payload["flow_audit_report"] = build_flow_audit_report(payload, plan)
    return payload


def purge_stale_goal_history(max_age_sec: float = 1800.0) -> dict[str, Any]:
    root = os.getenv(
        "INF_BRIDGE_GOAL_DIR",
        "/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-run/.tmp-goal-history",
    )
    os.makedirs(root, exist_ok=True)
    now = time.time()
    removed = 0
    kept = 0
    for name in os.listdir(root):
        if not name.startswith("goal-history-") or not name.endswith(".jsonl"):
            continue
        path = os.path.join(root, name)
        try:
            age = now - os.path.getmtime(path)
            if age >= max_age_sec:
                os.unlink(path)
                removed += 1
            else:
                kept += 1
        except Exception:
            kept += 1
    return {"root": root, "removed": removed, "kept": kept, "max_age_sec": max_age_sec}


def purge_stale_ephemeral_audit(max_age_sec: float = 1800.0) -> dict[str, Any]:
    root = os.getenv(
        "INF_BRIDGE_AUDIT_DIR",
        "/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-run/.tmp-audit",
    )
    os.makedirs(root, exist_ok=True)
    now = time.time()
    removed = 0
    kept = 0
    for name in os.listdir(root):
        if not name.startswith("inf-bridge-") or not name.endswith(".ndjson"):
            continue
        path = os.path.join(root, name)
        try:
            age = now - os.path.getmtime(path)
            if age >= max_age_sec:
                os.unlink(path)
                removed += 1
            else:
                kept += 1
        except Exception:
            kept += 1
    return {"root": root, "removed": removed, "kept": kept, "max_age_sec": max_age_sec}


def make_ephemeral_goal_history_file() -> str:
    root = os.getenv(
        "INF_BRIDGE_GOAL_DIR",
        "/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-run/.tmp-goal-history",
    )
    os.makedirs(root, exist_ok=True)
    fd, path = tempfile.mkstemp(prefix="goal-history-", suffix=".jsonl", dir=root)
    os.close(fd)
    return path


def append_goal_event(path: str, event: dict[str, Any]) -> None:
    rec = {"ts": time.time(), **event}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def cleanup_goal_history(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.unlink(path)
    except Exception:
        pass


def make_ephemeral_audit_file() -> str:
    root = os.getenv(
        "INF_BRIDGE_AUDIT_DIR",
        "/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-run/.tmp-audit",
    )
    os.makedirs(root, exist_ok=True)
    fd, path = tempfile.mkstemp(prefix="inf-bridge-", suffix=".ndjson", dir=root)
    os.close(fd)
    return path


def append_ephemeral_audit(path: str, event: dict[str, Any]) -> None:
    rec = {"ts": time.time(), **event}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def cleanup_ephemeral_audit(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.unlink(path)
    except Exception:
        pass
