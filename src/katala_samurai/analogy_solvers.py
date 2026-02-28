
# ─── Analogy Solvers (A01-A05) ──────────────────────────────────────────────
# Design: Youta Hilono, 2026-02-28
# Principle: Complete non-LLM implementation. All A-solvers use deterministic
# algorithms, static dictionaries, and API calls — never LLM inference.

import re
import os
import urllib.request
import urllib.parse
import json as _json


# ─── A01: Semantic Decomposition ────────────────────────────────────────────

def a01_semantic_decomposition(text):
    """Decompose text into morphemes and candidate sub-meanings.
    
    Non-LLM: regex-based morpheme splitting + common prefix/suffix detection.
    """
    # Common English prefixes and suffixes for decomposition
    prefixes = ["un", "re", "dis", "over", "mis", "out", "pre", "non", "sub",
                "super", "inter", "trans", "counter", "anti", "neo"]
    suffixes = ["tion", "sion", "ment", "ness", "ible", "able", "ful", "less",
                "ous", "ive", "ing", "ment", "ence", "ance", "ity", "ly"]
    
    words = re.findall(r'[A-Za-z]+', text)
    decompositions = {}
    
    for word in words:
        lower = word.lower()
        parts = []
        
        # Try compound splitting (CamelCase or known compounds)
        camel = re.findall(r'[A-Z][a-z]+|[a-z]+', word)
        if len(camel) > 1:
            parts = [p.lower() for p in camel]
        
        # Try common compound boundaries
        if not parts and len(lower) > 6:
            for i in range(3, len(lower) - 2):
                left, right = lower[:i], lower[i:]
                if len(left) >= 3 and len(right) >= 3:
                    parts.append(f"{left}+{right}")
        
        # Prefix/suffix detection
        detected_prefix = None
        detected_suffix = None
        for p in prefixes:
            if lower.startswith(p) and len(lower) > len(p) + 2:
                detected_prefix = p
                break
        for s in suffixes:
            if lower.endswith(s) and len(lower) > len(s) + 2:
                detected_suffix = s
                break
        
        decompositions[word] = {
            "original": word,
            "compound_splits": parts[:5],  # limit candidates
            "prefix": detected_prefix,
            "suffix": detected_suffix,
        }
    
    return decompositions


# ─── A02: Phonetic Neighbor ─────────────────────────────────────────────────

_cmu_dict_cache = None  # loaded once per process, not persisted

def _get_cmu_dict():
    """Load CMU dictionary. Cached in process memory only (not disk)."""
    global _cmu_dict_cache
    if _cmu_dict_cache is None:
        try:
            import cmudict
            _cmu_dict_cache = cmudict.dict()
        except ImportError:
            _cmu_dict_cache = {}
    return _cmu_dict_cache


def _phonetic_distance(phones1, phones2):
    """Compute edit distance between two phone sequences (ARPAbet).
    
    Simple Levenshtein on phone tokens. Stress markers stripped.
    """
    p1 = [re.sub(r'\d', '', p) for p in phones1]
    p2 = [re.sub(r'\d', '', p) for p in phones2]
    
    m, n = len(p1), len(p2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if p1[i-1] == p2[j-1] else 1
            dp[i][j] = min(dp[i-1][j] + 1, dp[i][j-1] + 1, dp[i-1][j-1] + cost)
    return dp[m][n]


def a02_phonetic_neighbor(word, max_distance=2, max_results=10):
    """Find phonetically similar words using CMU Pronouncing Dictionary.
    
    Non-LLM: deterministic phonetic edit distance computation.
    Also searches OpenAlex for phonology papers related to the word.
    """
    cmu = _get_cmu_dict()
    word_lower = word.lower()
    
    # Get pronunciation of target word
    target_phones = cmu.get(word_lower)
    if not target_phones:
        # Try sub-parts for compounds
        return {"word": word, "phones": None, "neighbors": [], 
                "note": "not in CMU dictionary", "papers": []}
    
    target = target_phones[0]  # use first pronunciation
    
    # Find neighbors
    neighbors = []
    for candidate, phone_lists in cmu.items():
        if candidate == word_lower:
            continue
        for phones in phone_lists:
            dist = _phonetic_distance(target, phones)
            if dist <= max_distance:
                neighbors.append({
                    "word": candidate,
                    "phones": phones,
                    "distance": dist,
                })
                break
    
    # Guarantee representation from each distance level
    # Sort within each distance by: word length similarity to target, then alphabetical
    by_dist = {}
    for n in neighbors:
        by_dist.setdefault(n["distance"], []).append(n)
    
    def _str_dist(a, b):
        """Simple string edit distance (Levenshtein)."""
        m, n = len(a), len(b)
        dp = list(range(n + 1))
        for i in range(1, m + 1):
            prev, dp[0] = dp[0], i
            for j in range(1, n + 1):
                temp = dp[j]
                dp[j] = min(dp[j] + 1, dp[j-1] + 1, prev + (0 if a[i-1] == b[j-1] else 1))
                prev = temp
        return dp[n]
    
    for d_list in by_dist.values():
        d_list.sort(key=lambda x: _str_dist(x["word"], word_lower))
    
    # Allocate slots per distance level
    result_neighbors = []
    for dist in sorted(by_dist.keys()):
        slots = max(3, max_results // max(len(by_dist), 1))
        result_neighbors.extend(by_dist[dist][:slots])
    
    neighbors = result_neighbors[:max_results]
    
    # Search OpenAlex for phonology papers
    papers = []
    try:
        params = {
            "search": f"phonetic similarity {word}",
            "per_page": "3",
            "select": "id,title,publication_year,cited_by_count",
            "sort": "relevance_score:desc",
            "mailto": "katala@openclaw.ai",
        }
        url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "KS30d/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = _json.loads(resp.read().decode())
            for p in data.get("results", []):
                papers.append({
                    "title": p.get("title", "")[:100],
                    "year": p.get("publication_year"),
                    "cited_by": p.get("cited_by_count", 0),
                })
    except Exception:
        pass
    
    # Phoneme pattern search: find words with similar vowel structure
    pattern_matches = []
    if target:
        target_stripped = [re.sub(r'\d', '', p) for p in target]
        vowel_set = {"AA","AE","AH","AO","AW","AY","EH","ER","EY","IH","IY","OW","OY","UH","UW"}
        target_vowels = [p for p in target_stripped if p in vowel_set]
        
        for candidate, phone_lists in cmu.items():
            if candidate == word_lower:
                continue
            for phones in phone_lists:
                cand_stripped = [re.sub(r'\d', '', p) for p in phones]
                if len(cand_stripped) == len(target_stripped):
                    cand_vowels = [p for p in cand_stripped if p in vowel_set]
                    if len(cand_vowels) == len(target_vowels):
                        vowel_diff = sum(1 for a, b in zip(target_vowels, cand_vowels) if a != b)
                        if vowel_diff <= 1:
                            pattern_matches.append({
                                "word": candidate,
                                "phones": phones,
                                "vowel_diff": vowel_diff,
                            })
                break
        
        # Guarantee both vowel_diff=0 and vowel_diff=1 appear
        # Sort by string similarity to target word (most similar first)
        def _str_sim(w):
            shared = sum(1 for a, b in zip(w, word_lower) if a == b)
            return -shared
        d0 = sorted([p for p in pattern_matches if p["vowel_diff"] == 0], key=lambda x: _str_sim(x["word"]))
        d1 = sorted([p for p in pattern_matches if p["vowel_diff"] == 1], key=lambda x: _str_sim(x["word"]))
        pattern_matches = d0[:7] + d1[:8]

    return {
        "word": word,
        "phones": target,
        "neighbors": neighbors,
        "pattern_matches": pattern_matches,
        "papers": papers,
    }


# ─── A03: Structural Mapping ───────────────────────────────────────────────

def _fetch_conceptnet_edges(concept, limit=10):
    """Fetch concept relations from ConceptNet API. Fresh, no cache."""
    try:
        url = f"http://api.conceptnet.io/c/en/{concept.lower()}?limit={limit}"
        req = urllib.request.Request(url, headers={"User-Agent": "KS30d/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = _json.loads(resp.read().decode())
            edges = []
            for edge in data.get("edges", []):
                edges.append({
                    "relation": edge.get("rel", {}).get("label", ""),
                    "start": edge.get("start", {}).get("label", ""),
                    "end": edge.get("end", {}).get("label", ""),
                    "weight": edge.get("weight", 0),
                })
            return edges
    except Exception:
        return []


def _extract_attributes_text(concept):
    """Extract attributes from a concept using text analysis (non-LLM fallback).
    
    When ConceptNet is unavailable, use basic semantic decomposition.
    """
    # Basic attribute extraction from word structure
    attrs = set()
    lower = concept.lower()
    
    # Common attribute patterns
    if lower.endswith("tion") or lower.endswith("sion"):
        attrs.add("process")
    if lower.endswith("ness") or lower.endswith("ity"):
        attrs.add("quality")
    if lower.endswith("er") or lower.endswith("or"):
        attrs.add("agent")
    
    attrs.add(lower)  # the concept itself
    return attrs


# ─── A03 Internal Probes ─────────────────────────────────────────────────────
# Self-contained structural analysis. No dependency on S01-S28.

def _probe_morphological(word):
    """Morphological structure: prefix, suffix, syllable count estimate."""
    lower = word.lower()
    feats = set()
    _pfx = ["un","re","dis","over","mis","out","pre","non","sub","super","inter","trans","anti","neo"]
    _sfx = ["tion","sion","ment","ness","ible","able","ful","less","ous","ive","ing","ence","ance","ity","ly","er","or","ist","ism"]
    for p in _pfx:
        if lower.startswith(p) and len(lower) > len(p)+2: feats.add(f"pfx:{p}")
    for s in _sfx:
        if lower.endswith(s) and len(lower) > len(s)+2: feats.add(f"sfx:{s}")
    # Rough syllable count (vowel clusters)
    import re as _re
    vowels = len(_re.findall(r'[aeiouy]+', lower))
    feats.add(f"syl:{vowels}")
    feats.add(f"len:{len(lower)}")
    return feats


def _probe_phonetic(word):
    """Phonetic features: consonant/vowel pattern, stress position."""
    cmu = _get_cmu_dict()
    phones = cmu.get(word.lower())
    feats = set()
    if not phones:
        return feats
    p = phones[0]
    vowel_set = {"AA","AE","AH","AO","AW","AY","EH","ER","EY","IH","IY","OW","OY","UH","UW"}
    stripped = [re.sub(r'\d', '', x) for x in p]
    pattern = ''.join('V' if x in vowel_set else 'C' for x in stripped)
    feats.add(f"cv:{pattern}")
    feats.add(f"phones:{len(p)}")
    # Stress position
    for i, ph in enumerate(p):
        if ph.endswith('1'):
            feats.add(f"stress:{i}")
            break
    # Initial and final phone
    if stripped:
        feats.add(f"init:{stripped[0]}")
        feats.add(f"final:{stripped[-1]}")
    return feats


def _probe_semantic_class(word):
    """Semantic class from suffix/context patterns (non-LLM heuristic)."""
    lower = word.lower()
    feats = set()
    # Agent/action/state/object heuristics
    agent_sfx = ["er","or","ist","ant","ent"]
    action_sfx = ["tion","sion","ment","ing","ure","ance","ence"]
    state_sfx = ["ness","ity","dom","hood","ship"]
    quality_sfx = ["ous","ive","ful","less","able","ible","al","ic"]
    for s in agent_sfx:
        if lower.endswith(s): feats.add("class:agent")
    for s in action_sfx:
        if lower.endswith(s): feats.add("class:action")
    for s in state_sfx:
        if lower.endswith(s): feats.add("class:state")
    for s in quality_sfx:
        if lower.endswith(s): feats.add("class:quality")
    if lower[0].isupper() or (len(lower) > 1 and lower == word):
        pass  # can't tell proper noun from lowercased input
    if not feats:
        feats.add("class:noun_default")
    return feats


def _probe_compound(word):
    """Compound structure: meaningful sub-parts from A01-style decomposition."""
    feats = set()
    cmu = _get_cmu_dict()
    lower = word.lower()
    # Try splits where both halves are real words
    for i in range(3, len(lower)-2):
        left, right = lower[:i], lower[i:]
        if left in cmu and right in cmu:
            feats.add(f"compound:{left}+{right}")
    return feats


_A03_PROBES = [
    ("morphological", _probe_morphological),
    ("phonetic", _probe_phonetic),
    ("semantic_class", _probe_semantic_class),
    ("compound", _probe_compound),
]


def a03_structural_mapping(concept_a, concept_b):
    """Map structural similarities between two concepts.
    
    Non-LLM: uses 4 internal probes (morphological, phonetic, semantic class,
    compound) + ConceptNet API (with text fallback).
    Self-contained — no dependency on S01-S28 solvers.
    
    Returns: shared attributes, A-only attributes, B-only attributes,
    plus per-probe breakdown.
    """
    # Internal probes (self-contained, no external dependency)
    probe_results = {}
    all_feats_a = set()
    all_feats_b = set()
    for probe_name, probe_fn in _A03_PROBES:
        fa = probe_fn(concept_a)
        fb = probe_fn(concept_b)
        probe_results[probe_name] = {
            "shared": list(fa & fb),
            "a_only": list(fa - fb),
            "b_only": list(fb - fa),
        }
        all_feats_a |= fa
        all_feats_b |= fb
    
    # Try ConceptNet as supplementary source
    edges_a = _fetch_conceptnet_edges(concept_a)
    edges_b = _fetch_conceptnet_edges(concept_b)
    
    if edges_a and edges_b:
        # Extract relation sets
        attrs_a = set()
        for e in edges_a:
            attrs_a.add(f"{e['relation']}:{e['end']}")
            attrs_a.add(e['end'].lower())
        
        attrs_b = set()
        for e in edges_b:
            attrs_b.add(f"{e['relation']}:{e['end']}")
            attrs_b.add(e['end'].lower())
        
        shared = attrs_a & attrs_b
        a_only = attrs_a - attrs_b
        b_only = attrs_b - attrs_a
        source = "conceptnet"
    else:
        # Fallback: text-based attribute extraction
        attrs_a = _extract_attributes_text(concept_a)
        attrs_b = _extract_attributes_text(concept_b)
        shared = attrs_a & attrs_b
        a_only = attrs_a - attrs_b
        b_only = attrs_b - attrs_a
        source = "text_fallback"
    
    # Merge probe features with ConceptNet/text features
    all_feats_a |= attrs_a
    all_feats_b |= attrs_b
    total_shared = all_feats_a & all_feats_b
    total_a_only = all_feats_a - all_feats_b
    total_b_only = all_feats_b - all_feats_a
    
    return {
        "concept_a": concept_a,
        "concept_b": concept_b,
        "shared_attributes": list(total_shared)[:20],
        "a_only_attributes": list(total_a_only)[:20],
        "b_only_attributes": list(total_b_only)[:20],
        "overlap_ratio": round(len(total_shared) / max(len(all_feats_a | all_feats_b), 1), 3),
        "probes": probe_results,
        "external_source": source,
    }



# ─── A04: Conceptual Blending ──────────────────────────────────────────────

def a04_conceptual_blending(decomposition, phonetic_results, structural_map):
    """Generate blended concept candidates from A01-A03 outputs.
    
    Non-LLM: combinatorial enumeration of decomposition parts × 
    phonetic neighbors × structural overlaps.
    """
    candidates = []
    
    # From A01: each compound split
    for word, decomp in decomposition.items():
        for split in decomp.get("compound_splits", []):
            if "+" in split:
                left, right = split.split("+", 1)
                candidates.append({
                    "source": f"A01:{word}",
                    "blend": f"{left} + {right}",
                    "type": "compound_split",
                })
    
    # From A02: each phonetic neighbor creates a substitution candidate
    if phonetic_results and phonetic_results.get("neighbors"):
        original = phonetic_results["word"]
        for neighbor in phonetic_results["neighbors"][:5]:
            candidates.append({
                "source": f"A02:{original}>{neighbor['word']}",
                "blend": f"{original} ~ {neighbor['word']} (dist={neighbor['distance']})",
                "type": "phonetic_substitution",
                "substituted_word": neighbor["word"],
            })
    # From A02 pattern matches
    if phonetic_results and phonetic_results.get("pattern_matches"):
        original = phonetic_results["word"]
        for pm in phonetic_results["pattern_matches"][:3]:
            candidates.append({
                "source": f"A02:pattern:{original}>{pm['word']}",
                "blend": f"{original} ~ {pm['word']} (vowel_diff={pm['vowel_diff']})",
                "type": "phoneme_pattern_match",
                "substituted_word": pm["word"],
            })
    
    # From A03: shared attributes suggest mapping paths
    if structural_map:
        shared = structural_map.get("shared_attributes", [])
        if shared:
            candidates.append({
                "source": "A03:shared_structure",
                "blend": f"{structural_map['concept_a']} ↔ {structural_map['concept_b']} via {shared[:3]}",
                "type": "structural_analogy",
                "shared": shared[:5],
            })
    
    # Limit to top candidates
    return candidates[:10]


# ─── A05: Premise Challenger ────────────────────────────────────────────────

def a05_premise_challenger(text):
    """Detect implicit premises and generate challenges.
    
    Non-LLM: pattern matching for assumption indicators + 
    negation/antonym generation via text rules.
    """
    # Detect assumption indicators
    assumption_patterns = [
        (r'\b(obviously|clearly|naturally|of course)\b', "stated_as_obvious"),
        (r'\b(because|since|as)\s+\w+\s+\w+\s+(is|are|has|have)\b', "causal_assumption"),
        (r'\b(all|every|always|never|no one)\b', "universal_claim"),
        (r'\b(must|should|need to|have to)\b', "normative_assumption"),
        (r'\b(better|worse|superior|inferior)\b', "comparative_assumption"),
        (r'\b(impossible|cannot|can\'t)\b', "impossibility_claim"),
    ]
    
    premises = []
    for pattern, ptype in assumption_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            # Extract surrounding context (±30 chars)
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()
            
            # Generate challenge
            challenge = None
            if ptype == "stated_as_obvious":
                challenge = f"Is it actually obvious? What evidence supports this?"
            elif ptype == "universal_claim":
                challenge = f"Are there counterexamples to this universal claim?"
            elif ptype == "impossibility_claim":
                challenge = f"Under what conditions might this become possible?"
            elif ptype == "comparative_assumption":
                challenge = f"By what metric? Is the comparison framework appropriate?"
            elif ptype == "causal_assumption":
                challenge = f"Is the causal relationship established or assumed?"
            elif ptype == "normative_assumption":
                challenge = f"Whose norm? Is this culturally/contextually bound?"
            
            premises.append({
                "type": ptype,
                "trigger": match.group(),
                "context": context,
                "challenge": challenge,
            })
    
    return premises[:10]


# ─── Analogy Pipeline ───────────────────────────────────────────────────────

def run_analogy_solvers(claim_text, focus_words=None, store=None):
    """Run A01-A05 pipeline on claim text.
    
    Args:
        claim_text: input text to analyze
        focus_words: specific words to analyze phonetically (optional)
        store: StageStore for externalization (optional)
    
    Returns dict with all A-solver outputs + blended candidates.
    """
    # A01: Decompose all words
    decomposition = a01_semantic_decomposition(claim_text)
    
    # A02: Phonetic analysis on focus words + sub-parts from A01
    if focus_words is None:
        words = sorted(decomposition.keys(), key=len, reverse=True)
        focus_words = words[:3]  # top 3 longest
    
    # Also extract sub-parts from compound splits
    sub_parts = set()
    for word in focus_words:
        decomp = decomposition.get(word, {})
        for split in decomp.get("compound_splits", []):
            if "+" in split:
                for part in split.split("+"):
                    if len(part) >= 3:
                        sub_parts.add(part)
    
    phonetic_results = {}
    for word in focus_words:
        phonetic_results[word] = a02_phonetic_neighbor(word, max_distance=2, max_results=5)
    for part in sub_parts:
        phonetic_results[f"_{part}"] = a02_phonetic_neighbor(part, max_distance=2, max_results=15)
    
    # A03: Structural mapping between focus word pairs
    structural_maps = []
    if len(focus_words) >= 2:
        structural_maps.append(
            a03_structural_mapping(focus_words[0], focus_words[1])
        )
    
    # A04: Blend candidates from A01-A03
    first_phonetic = phonetic_results.get(focus_words[0]) if focus_words else None
    first_structural = structural_maps[0] if structural_maps else None
    blends = a04_conceptual_blending(decomposition, first_phonetic, first_structural)
    
    # A05: Challenge premises
    premises = a05_premise_challenger(claim_text)
    
    result = {
        "a01_decomposition": decomposition,
        "a02_phonetic": phonetic_results,
        "a03_structural": structural_maps,
        "a04_blends": blends,
        "a05_premises": premises,
        "candidates_generated": len(blends),
    }
    
    if store is not None:
        store.write("A_analogy_solvers", result)
    
    return result
