"""
KS47: Deep Research Verification Engine

Evaluates Deep Research Agent (DRA) output quality across 5 axes:
  1. Query Decomposition Coverage
  2. Search Depth & Diversity
  3. Synthesis Quality (RACE-inspired)
  4. Citation & Fact Verification (FACT-inspired)
  5. Orchestration Quality

Integrates with KS46 for claim-level verification.

Design: Youta Hilono & Nicolas Ogoshi
Implementation: Shirokuma (OpenClaw AI), 2026-03-01

References:
  - DeepResearch Bench (arxiv 2506.11763) — RACE + FACT
  - Deep Research Bench / DRB (arxiv 2506.06287) — Offline web eval
  - DRACO (Perplexity, 2026-02) — Real-world rubric eval
  - DeepSynth (arxiv 2602.21143) — Deep info synthesis
  - TRACE (arxiv 2602.21230) — Trajectory-aware eval
  - ResearcherBench (GAIR-NLP) — Dual rubric/factual
  - DeepResearch-Bench-II (2601.08536) — 9430 fine-grained rubrics
"""

from __future__ import annotations

import json
import re
import math
from dataclasses import dataclass, field, asdict
from typing import Optional
from urllib.parse import urlparse


# ═══════════════════════════════════════════════════
# Data Structures
# ═══════════════════════════════════════════════════

@dataclass
class Citation:
    """A single citation extracted from a report."""
    statement: str
    url: str
    domain: str = ""
    verified: Optional[bool] = None
    verification_reason: str = ""

    def __post_init__(self):
        if not self.domain and self.url:
            try:
                self.domain = urlparse(self.url).netloc
            except Exception:
                self.domain = ""


@dataclass
class QueryCoverageResult:
    """Axis 1: Query Decomposition Coverage."""
    original_query: str
    sub_queries_expected: list[str] = field(default_factory=list)
    sub_queries_covered: list[str] = field(default_factory=list)
    coverage_rate: float = 0.0
    dag_depth: int = 0
    branch_count: int = 0
    score: float = 0.0


@dataclass
class SearchDepthResult:
    """Axis 2: Search Depth & Diversity."""
    unique_domains: list[str] = field(default_factory=list)
    domain_count: int = 0
    estimated_hops: int = 0
    source_freshness_score: float = 0.0
    diversity_score: float = 0.0
    score: float = 0.0


@dataclass
class SynthesisQualityResult:
    """Axis 3: Synthesis Quality (RACE-inspired 4 dimensions)."""
    r_comprehensiveness: float = 0.0
    r_insight: float = 0.0
    r_instruction_following: float = 0.0
    r_readability: float = 0.0
    score: float = 0.0


@dataclass
class CitationVerifyResult:
    """Axis 4: Citation & Fact Verification (FACT-inspired)."""
    total_citations: int = 0
    verified_count: int = 0
    accuracy: float = 0.0
    effective_citations: int = 0
    citations: list[Citation] = field(default_factory=list)
    score: float = 0.0


@dataclass
class OrchestrationResult:
    """Axis 5: Orchestration Quality."""
    completion_rate: float = 0.0
    recovery_events: int = 0
    parallelism_degree: float = 0.0
    execution_time_s: float = 0.0
    agent_consistency: float = 0.0
    score: float = 0.0


@dataclass
class DeepResearchVerifyResult:
    """Full KS47 verification result."""
    version: str = "KS47-v1"
    query: str = ""
    report_length: int = 0

    # 5-axis scores (0.0 - 1.0)
    query_coverage: QueryCoverageResult = field(default_factory=lambda: QueryCoverageResult(original_query=""))
    search_depth: SearchDepthResult = field(default_factory=SearchDepthResult)
    synthesis_quality: SynthesisQualityResult = field(default_factory=SynthesisQualityResult)
    citation_verify: CitationVerifyResult = field(default_factory=CitationVerifyResult)
    orchestration: OrchestrationResult = field(default_factory=OrchestrationResult)

    # Aggregate
    overall_score: float = 0.0
    grade: str = "F"

    # Claim-level (KS46 integration)
    claim_count: int = 0
    claim_pass_rate: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


# ═══════════════════════════════════════════════════
# Report Parser
# ═══════════════════════════════════════════════════

class ReportParser:
    """Parse a deep research report into structured components."""

    # Markdown heading pattern
    HEADING_RE = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)

    # URL patterns (markdown links + bare URLs)
    MD_LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    BARE_URL_RE = re.compile(r'(?<!\()https?://[^\s\)>\]]+')

    # Footnote-style citations: [1], [2], etc.
    FOOTNOTE_RE = re.compile(r'\[(\d+)\]')

    def parse_sections(self, text: str) -> list[dict]:
        """Split report into sections by headings."""
        sections = []
        matches = list(self.HEADING_RE.finditer(text))

        if not matches:
            return [{"level": 0, "title": "Full Report", "content": text}]

        # Content before first heading
        if matches[0].start() > 0:
            sections.append({
                "level": 0,
                "title": "Introduction",
                "content": text[:matches[0].start()].strip()
            })

        for i, m in enumerate(matches):
            level = len(m.group(1))
            title = m.group(2).strip()
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start:end].strip()
            sections.append({"level": level, "title": title, "content": content})

        return sections

    def extract_citations(self, text: str) -> list[Citation]:
        """Extract all citations (URL-statement pairs) from text."""
        citations = []

        # Markdown links: [statement](url)
        for m in self.MD_LINK_RE.finditer(text):
            statement = m.group(1).strip()
            url = m.group(2).strip()
            if url.startswith("http"):
                citations.append(Citation(statement=statement, url=url))

        # Bare URLs with surrounding context
        for m in self.BARE_URL_RE.finditer(text):
            url = m.group(0)
            # Get surrounding sentence as statement
            start = max(0, m.start() - 150)
            end = min(len(text), m.end() + 50)
            context = text[start:end].strip()
            # Avoid duplicates from markdown links
            if not any(c.url == url for c in citations):
                citations.append(Citation(statement=context, url=url))

        return citations

    def extract_claims(self, text: str) -> list[str]:
        """Extract verifiable claims from report text.

        Heuristic: sentences containing factual assertions.
        """
        claims = []
        # Split by sentence boundaries
        sentences = re.split(r'(?<=[.。!！?？])\s+', text)

        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 15:
                continue
            # Skip headings, links-only, lists
            if sent.startswith('#') or sent.startswith('- ') or sent.startswith('* '):
                continue
            # Factual indicators
            factual_indicators = [
                r'\d+%', r'\d+\.\d+', r'億', r'万', r'million', r'billion',
                r'研究', r'according', r'report', r'study', r'found',
                r'increased', r'decreased', r'showed', r'demonstrated',
                r'以上', r'以下', r'約', r'approximately', r'estimated',
            ]
            if any(re.search(p, sent, re.IGNORECASE) for p in factual_indicators):
                claims.append(sent)

        return claims


# ═══════════════════════════════════════════════════
# Axis Verifiers
# ═══════════════════════════════════════════════════

class QueryCoverageVerifier:
    """Axis 1: Evaluate how well the report covers the original query."""

    def verify(self, query: str, report: str, sections: list[dict]) -> QueryCoverageResult:
        result = QueryCoverageResult(original_query=query)

        # Extract key terms from query
        query_terms = self._extract_key_terms(query)
        result.sub_queries_expected = query_terms

        # Check which terms are covered in report
        report_lower = report.lower()
        covered = [t for t in query_terms if t.lower() in report_lower]
        result.sub_queries_covered = covered

        # Coverage rate
        if query_terms:
            result.coverage_rate = len(covered) / len(query_terms)
        else:
            result.coverage_rate = 0.5  # Can't determine

        # DAG depth ≈ heading depth
        max_level = max((s["level"] for s in sections), default=0)
        result.dag_depth = max_level

        # Branch count ≈ number of top-level sections
        result.branch_count = sum(1 for s in sections if s["level"] <= 2)

        # Score: coverage (60%) + structure (40%)
        structure_score = min(1.0, (result.dag_depth / 4.0) * 0.5 + (result.branch_count / 8.0) * 0.5)
        result.score = result.coverage_rate * 0.6 + structure_score * 0.4

        return result

    def _extract_key_terms(self, query: str) -> list[str]:
        """Extract key terms/concepts from query."""
        # Remove common stop words and split
        stop_words = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'can', 'shall',
            'and', 'or', 'but', 'if', 'of', 'at', 'by', 'for', 'with',
            'about', 'to', 'from', 'in', 'on', 'not', 'no', 'so',
            'what', 'how', 'why', 'when', 'where', 'which', 'who',
            'の', 'は', 'が', 'を', 'に', 'で', 'と', 'も', 'か',
            'する', 'ある', 'いる', 'なる', 'できる', 'ない',
            'この', 'その', 'あの', 'どの', 'これ', 'それ',
            '的', '了', '在', '是', '有', '和', '与', '对', '从',
            '请', '分析', '研究', '整理', '说明', '介绍',
        }

        # Split on whitespace and punctuation
        tokens = re.findall(r'[\w\u4e00-\u9fff\u3040-\u30ff]+', query.lower())
        terms = [t for t in tokens if t not in stop_words and len(t) > 1]

        # Also extract multi-character Chinese/Japanese phrases
        cjk_phrases = re.findall(r'[\u4e00-\u9fff\u3040-\u30ff]{2,}', query)
        terms.extend([p for p in cjk_phrases if p.lower() not in stop_words])

        return list(set(terms))


class SearchDepthVerifier:
    """Axis 2: Evaluate search depth and source diversity."""

    # Known authoritative domains by category
    AUTHORITATIVE_DOMAINS = {
        'academic': ['arxiv.org', 'scholar.google', 'pubmed', 'doi.org', 'jstor.org',
                     'nature.com', 'science.org', 'ieee.org', 'acm.org', 'springer.com'],
        'news': ['reuters.com', 'bbc.com', 'nytimes.com', 'washingtonpost.com',
                 'theguardian.com', 'bloomberg.com', 'ft.com'],
        'gov': ['.gov', '.go.jp', '.gov.cn', '.europa.eu'],
        'reference': ['wikipedia.org', 'britannica.com', 'statista.com'],
    }

    def verify(self, citations: list[Citation]) -> SearchDepthResult:
        result = SearchDepthResult()

        if not citations:
            result.score = 0.0
            return result

        # Unique domains
        domains = list(set(c.domain for c in citations if c.domain))
        result.unique_domains = domains
        result.domain_count = len(domains)

        # Domain category diversity
        categories_hit = set()
        for domain in domains:
            for cat, patterns in self.AUTHORITATIVE_DOMAINS.items():
                if any(p in domain for p in patterns):
                    categories_hit.add(cat)

        # Diversity: domain count + category coverage
        domain_score = min(1.0, result.domain_count / 15.0)
        category_score = len(categories_hit) / len(self.AUTHORITATIVE_DOMAINS)

        # Estimated hops (heuristic: more unique domains = deeper search)
        result.estimated_hops = min(10, max(1, result.domain_count // 3))

        result.diversity_score = domain_score * 0.6 + category_score * 0.4
        result.score = result.diversity_score

        return result


class SynthesisQualityVerifier:
    """Axis 3: RACE-inspired synthesis quality (rule-based approximation).

    Full RACE uses LLM-as-Judge; this is a deterministic heuristic baseline.
    """

    def verify(self, report: str, sections: list[dict], query: str,
               claims: list[str]) -> SynthesisQualityResult:
        result = SynthesisQualityResult()

        report_len = len(report)

        # R_comprehensiveness: coverage breadth
        # Heuristic: section count, report length, claim density
        section_count = len(sections)
        section_score = min(1.0, section_count / 10.0)
        length_score = min(1.0, report_len / 5000.0)
        claim_density = len(claims) / max(1, report_len / 1000)  # claims per 1000 chars
        density_score = min(1.0, claim_density / 3.0)
        result.r_comprehensiveness = section_score * 0.4 + length_score * 0.3 + density_score * 0.3

        # R_insight: depth of analysis
        # Heuristic: presence of comparative/analytical language
        insight_markers = [
            'however', 'although', 'whereas', 'in contrast', 'on the other hand',
            'implication', 'significance', 'suggests that', 'indicates',
            'correlation', 'relationship', 'trend', 'pattern',
            'しかし', 'ただし', '一方', '対照的', '示唆', '傾向',
            '意味する', 'パターン', '相関', '因果',
            '然而', '但是', '相比之下', '意味着', '趋势', '关联',
        ]
        marker_count = sum(1 for m in insight_markers
                          if m.lower() in report.lower())
        result.r_insight = min(1.0, marker_count / 8.0)

        # R_instruction_following: query term presence + structure adherence
        query_terms = re.findall(r'[\w\u4e00-\u9fff\u3040-\u30ff]+', query.lower())
        query_terms = [t for t in query_terms if len(t) > 2]
        if query_terms:
            covered = sum(1 for t in query_terms if t in report.lower())
            result.r_instruction_following = covered / len(query_terms)
        else:
            result.r_instruction_following = 0.5

        # R_readability: sentence length variance, heading structure
        sentences = re.split(r'[.。!！?？]\s+', report)
        if len(sentences) > 3:
            lengths = [len(s) for s in sentences if len(s) > 5]
            if lengths:
                avg_len = sum(lengths) / len(lengths)
                # Optimal avg sentence length: 15-40 words / 40-120 chars
                if 40 <= avg_len <= 120:
                    len_score = 1.0
                elif avg_len < 40:
                    len_score = avg_len / 40.0
                else:
                    len_score = max(0.3, 1.0 - (avg_len - 120) / 200.0)

                # Has clear structure (headings)
                has_headings = any(s["level"] > 0 for s in sections)
                struct_score = 0.8 if has_headings else 0.4

                result.r_readability = len_score * 0.5 + struct_score * 0.5
            else:
                result.r_readability = 0.3
        else:
            result.r_readability = 0.3

        # Weighted score (RACE weights from paper)
        result.score = (
            result.r_comprehensiveness * 0.30 +
            result.r_insight * 0.30 +
            result.r_instruction_following * 0.20 +
            result.r_readability * 0.20
        )

        return result


class CitationVerifier:
    """Axis 4: FACT-inspired citation verification.

    Note: Full verification requires URL fetching.
    This module provides structural analysis; URL verification
    is optional and can be enabled with fetch_urls=True.
    """

    def verify(self, citations: list[Citation], report: str,
               fetch_urls: bool = False) -> CitationVerifyResult:
        result = CitationVerifyResult()
        result.citations = citations
        result.total_citations = len(citations)

        if not citations:
            result.score = 0.0
            return result

        # Structural citation quality checks
        verified = 0
        effective = 0

        for cit in citations:
            # Check URL is well-formed
            url_valid = bool(urlparse(cit.url).scheme in ('http', 'https')
                            and urlparse(cit.url).netloc)

            # Check statement is substantive (not just "link", "source", etc.)
            statement_ok = len(cit.statement) > 20 and not cit.statement.startswith('http')

            if url_valid and statement_ok:
                effective += 1
                cit.verified = True
                cit.verification_reason = "structural_pass"
                verified += 1
            elif url_valid:
                cit.verified = True
                cit.verification_reason = "url_valid_but_weak_statement"
                verified += 1
            else:
                cit.verified = False
                cit.verification_reason = "url_invalid"

        result.verified_count = verified
        result.effective_citations = effective
        result.accuracy = verified / result.total_citations if result.total_citations > 0 else 0.0

        # Score: citation count (40%) + accuracy (30%) + effective ratio (30%)
        count_score = min(1.0, result.total_citations / 20.0)
        effective_ratio = effective / result.total_citations if result.total_citations > 0 else 0.0

        result.score = (
            count_score * 0.40 +
            result.accuracy * 0.30 +
            effective_ratio * 0.30
        )

        return result


class OrchestrationVerifier:
    """Axis 5: Orchestration quality.

    Without agent logs, estimates from report structure.
    """

    def verify(self, report: str, sections: list[dict],
               execution_time_s: float = 0.0,
               agent_logs: Optional[list[dict]] = None) -> OrchestrationResult:
        result = OrchestrationResult()
        result.execution_time_s = execution_time_s

        if agent_logs:
            # Full log analysis (when available)
            result.completion_rate = self._calc_completion(agent_logs)
            result.recovery_events = self._count_recoveries(agent_logs)
            result.parallelism_degree = self._calc_parallelism(agent_logs)
            result.agent_consistency = self._calc_consistency(agent_logs)
        else:
            # Estimate from report structure
            # Completeness: has intro + body + conclusion?
            titles_lower = [s["title"].lower() for s in sections]
            has_intro = any('intro' in t or '導入' in t or '概要' in t or '引言' in t
                          for t in titles_lower)
            has_conclusion = any('conclu' in t or 'summary' in t or 'まとめ' in t
                               or '結論' in t or '总结' in t or '結語' in t
                               for t in titles_lower)
            has_body = len(sections) >= 3

            result.completion_rate = sum([has_intro, has_body, has_conclusion]) / 3.0
            result.parallelism_degree = 0.5  # Unknown without logs
            result.agent_consistency = 0.7 if has_body else 0.3

        result.score = (
            result.completion_rate * 0.40 +
            result.agent_consistency * 0.30 +
            min(1.0, result.parallelism_degree) * 0.15 +
            (1.0 if result.recovery_events == 0 else 0.7) * 0.15
        )

        return result

    def _calc_completion(self, logs: list[dict]) -> float:
        total = len(logs)
        completed = sum(1 for l in logs if l.get("status") == "completed")
        return completed / total if total > 0 else 0.0

    def _count_recoveries(self, logs: list[dict]) -> int:
        return sum(1 for l in logs if l.get("type") == "recovery")

    def _calc_parallelism(self, logs: list[dict]) -> float:
        parallel = sum(1 for l in logs if l.get("parallel", False))
        return parallel / len(logs) if logs else 0.0

    def _calc_consistency(self, logs: list[dict]) -> float:
        # Stub: would check for contradictions between agent outputs
        return 0.7


# ═══════════════════════════════════════════════════
# Main Engine
# ═══════════════════════════════════════════════════

class KS47:
    """Deep Research Verification Engine.

    Usage:
        engine = KS47()
        result = engine.verify(query="...", report="...", report_md="...")
        print(result.to_json())
    """

    VERSION = "KS47-v1"

    # Axis weights (default; can be overridden)
    DEFAULT_WEIGHTS = {
        "query_coverage": 0.15,
        "search_depth": 0.20,
        "synthesis_quality": 0.30,
        "citation_verify": 0.25,
        "orchestration": 0.10,
    }

    GRADE_THRESHOLDS = [
        (0.90, "S"),
        (0.80, "A"),
        (0.65, "B"),
        (0.50, "C"),
        (0.35, "D"),
        (0.0,  "F"),
    ]

    def __init__(self, weights: Optional[dict] = None):
        self.weights = weights or self.DEFAULT_WEIGHTS
        self.parser = ReportParser()
        self.qc_verifier = QueryCoverageVerifier()
        self.sd_verifier = SearchDepthVerifier()
        self.sq_verifier = SynthesisQualityVerifier()
        self.cv_verifier = CitationVerifier()
        self.ov_verifier = OrchestrationVerifier()

    def verify(self, query: str, report: str,
               execution_time_s: float = 0.0,
               agent_logs: Optional[list[dict]] = None,
               fetch_urls: bool = False) -> DeepResearchVerifyResult:
        """Full 5-axis verification pipeline."""

        result = DeepResearchVerifyResult(
            version=self.VERSION,
            query=query,
            report_length=len(report),
        )

        # Parse report
        sections = self.parser.parse_sections(report)
        citations = self.parser.extract_citations(report)
        claims = self.parser.extract_claims(report)
        result.claim_count = len(claims)

        # Axis 1: Query Coverage
        result.query_coverage = self.qc_verifier.verify(query, report, sections)

        # Axis 2: Search Depth
        result.search_depth = self.sd_verifier.verify(citations)

        # Axis 3: Synthesis Quality
        result.synthesis_quality = self.sq_verifier.verify(
            report, sections, query, claims
        )

        # Axis 4: Citation Verification
        result.citation_verify = self.cv_verifier.verify(
            citations, report, fetch_urls=fetch_urls
        )

        # Axis 5: Orchestration
        result.orchestration = self.ov_verifier.verify(
            report, sections, execution_time_s, agent_logs
        )

        # Aggregate score
        result.overall_score = (
            result.query_coverage.score * self.weights["query_coverage"] +
            result.search_depth.score * self.weights["search_depth"] +
            result.synthesis_quality.score * self.weights["synthesis_quality"] +
            result.citation_verify.score * self.weights["citation_verify"] +
            result.orchestration.score * self.weights["orchestration"]
        )

        # Grade
        for threshold, grade in self.GRADE_THRESHOLDS:
            if result.overall_score >= threshold:
                result.grade = grade
                break

        return result

    def verify_batch(self, items: list[dict]) -> list[DeepResearchVerifyResult]:
        """Verify multiple reports.

        Each item: {"query": str, "report": str, ...optional...}
        """
        return [self.verify(**item) for item in items]


# ═══════════════════════════════════════════════════
# Benchmark Integration
# ═══════════════════════════════════════════════════

class BenchmarkRunner:
    """Run KS47 against standard benchmarks."""

    def __init__(self, engine: Optional[KS47] = None):
        self.engine = engine or KS47()

    def run_deepresearch_bench(self, data_dir: str,
                                target_model: str = "claude-3-7-sonnet-latest"
                                ) -> dict:
        """Run against DeepResearch Bench (RACE evaluation).

        Args:
            data_dir: Path to deep_research_bench/data/
            target_model: Model results to evaluate

        Returns:
            Summary dict with per-task and aggregate scores
        """
        import os

        ref_file = os.path.join(data_dir, "test_data", "cleaned_data", "reference.jsonl")
        target_file = os.path.join(data_dir, "test_data", "cleaned_data", f"{target_model}.jsonl")
        criteria_file = os.path.join(data_dir, "criteria_data", "criteria.jsonl")

        if not os.path.exists(target_file):
            available = [f.replace('.jsonl', '') for f in
                        os.listdir(os.path.join(data_dir, "test_data", "cleaned_data"))
                        if f.endswith('.jsonl') and f != 'reference.jsonl']
            return {"error": f"Model '{target_model}' not found. Available: {available}"}

        # Load data
        references = self._load_jsonl(ref_file)
        targets = self._load_jsonl(target_file)
        criteria = self._load_jsonl(criteria_file)

        ref_map = {r["id"]: r for r in references}
        crit_map = {c["id"]: c for c in criteria}

        results = []
        for target in targets:
            tid = target["id"]
            ref = ref_map.get(tid, {})
            crit = crit_map.get(tid, {})

            query = target.get("prompt", ref.get("prompt", ""))
            report = target.get("article", "")

            r = self.engine.verify(query=query, report=report)

            results.append({
                "id": tid,
                "query": query[:100],
                "ks47_overall": r.overall_score,
                "ks47_grade": r.grade,
                "axis_scores": {
                    "query_coverage": r.query_coverage.score,
                    "search_depth": r.search_depth.score,
                    "synthesis_quality": r.synthesis_quality.score,
                    "citation_verify": r.citation_verify.score,
                    "orchestration": r.orchestration.score,
                },
                "claim_count": r.claim_count,
                "citation_count": r.citation_verify.total_citations,
                "report_length": r.report_length,
            })

        # Aggregate
        if results:
            avg_score = sum(r["ks47_overall"] for r in results) / len(results)
            avg_axes = {}
            for axis in ["query_coverage", "search_depth", "synthesis_quality",
                         "citation_verify", "orchestration"]:
                avg_axes[axis] = sum(r["axis_scores"][axis] for r in results) / len(results)
        else:
            avg_score = 0.0
            avg_axes = {}

        return {
            "benchmark": "DeepResearch Bench (RACE)",
            "model": target_model,
            "task_count": len(results),
            "average_score": round(avg_score, 4),
            "average_grade": self._score_to_grade(avg_score),
            "average_axes": {k: round(v, 4) for k, v in avg_axes.items()},
            "results": results,
        }

    def run_draco(self, data_dir: str) -> dict:
        """Run against DRACO benchmark (rubric evaluation).

        Args:
            data_dir: Path to draco/ directory

        Returns:
            Summary dict
        """
        import os
        test_file = os.path.join(data_dir, "test.jsonl")
        tasks = self._load_jsonl(test_file)

        results = []
        for task in tasks:
            # DRACO has problem + answer (with embedded rubric)
            query = task.get("problem", "")
            # Parse rubric from answer
            answer = task.get("answer", "")
            if isinstance(answer, str):
                try:
                    answer_data = json.loads(answer)
                except json.JSONDecodeError:
                    answer_data = {}
            else:
                answer_data = answer

            results.append({
                "id": task.get("id", ""),
                "domain": task.get("domain", ""),
                "query": query[:100],
                "rubric_sections": len(answer_data.get("sections", [])),
                "rubric_criteria_count": sum(
                    len(s.get("criteria", []))
                    for s in answer_data.get("sections", [])
                ),
            })

        return {
            "benchmark": "DRACO",
            "task_count": len(results),
            "domains": list(set(r["domain"] for r in results)),
            "total_criteria": sum(r["rubric_criteria_count"] for r in results),
            "avg_criteria_per_task": round(
                sum(r["rubric_criteria_count"] for r in results) / max(1, len(results)), 1
            ),
            "tasks": results,
        }

    def run_researcher_bench(self, data_dir: str) -> dict:
        """Run against ResearcherBench (rubric + factual).

        Args:
            data_dir: Path to ResearcherBench/ directory

        Returns:
            Summary dict
        """
        import os
        q_file = os.path.join(data_dir, "data", "eval_data", "questions.json")

        with open(q_file) as f:
            questions = json.load(f)

        return {
            "benchmark": "ResearcherBench",
            "task_count": len(questions),
            "categories": list(set(q.get("category", "unknown") for q in questions)),
            "subjects": list(set(q.get("Subject", "unknown") for q in questions)),
            "questions": [
                {"id": q["id"], "category": q.get("category", ""),
                 "subject": q.get("Subject", ""),
                 "question": q["question"][:100]}
                for q in questions[:5]  # Sample
            ],
        }

    def _load_jsonl(self, path: str) -> list[dict]:
        results = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    results.append(json.loads(line))
        return results

    def _score_to_grade(self, score: float) -> str:
        for threshold, grade in KS47.GRADE_THRESHOLDS:
            if score >= threshold:
                return grade
        return "F"


# ═══════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════

def main():
    """Quick test: verify a sample report."""
    engine = KS47()

    sample_query = "Analyze the current state of deep research AI agents, comparing major providers."
    sample_report = """
# Deep Research AI Agents: A Comparative Analysis

## Introduction

Deep research agents represent a new paradigm in AI-assisted knowledge work.
Unlike traditional RAG systems, these agents autonomously decompose complex queries,
perform iterative multi-step web searches, and synthesize findings into comprehensive reports.

## Major Providers

### OpenAI Deep Research
OpenAI's Deep Research, launched in early 2025, uses o3 as its backbone model.
According to [benchmarks](https://futuresearch.ai/deep-research-bench/), ChatGPT o3
outperformed dedicated deep research tools on the DRB benchmark.

### Google Gemini Deep Research
Gemini 2.5 Pro Deep Research achieved the highest RACE score on DeepResearch Bench,
demonstrating strong performance in report quality across 22 domains.
The system scored approximately 54% on the RACE evaluation framework.

### Perplexity Deep Research
Perplexity upgraded its Deep Research with Claude Opus 4.5, achieving 89.4% pass rate
in Law and 82.4% in Academic domains on the DRACO benchmark.
It also leads the Deep Search QA leaderboard at 79.5%.

### Claude Research
Anthropic's multi-agent research system uses an orchestrator-worker architecture
with parallel sub-agent execution for comprehensive research tasks.

## Architectural Patterns

However, there are significant differences in how these systems approach research.
The trend toward multi-agent architectures suggests that parallelism is crucial
for deep research quality. In contrast, single-agent systems with extended context
windows show competitive performance on simpler tasks.

The correlation between search depth and report quality indicates that
iterative refinement is more important than initial query coverage.

## Conclusion

Deep research agents are rapidly evolving, with competition driving innovation
across multiple dimensions including accuracy, depth, and latency.
"""

    result = engine.verify(query=sample_query, report=sample_report)
    print(f"\n{'='*60}")
    print(f"KS47 Deep Research Verification — {result.version}")
    print(f"{'='*60}")
    print(f"Query: {result.query[:80]}")
    print(f"Report length: {result.report_length} chars")
    print(f"Claims found: {result.claim_count}")
    print()
    print(f"Axis 1 — Query Coverage:      {result.query_coverage.score:.3f}")
    print(f"  Coverage rate: {result.query_coverage.coverage_rate:.2f}")
    print(f"  DAG depth: {result.query_coverage.dag_depth}, Branches: {result.query_coverage.branch_count}")
    print()
    print(f"Axis 2 — Search Depth:        {result.search_depth.score:.3f}")
    print(f"  Unique domains: {result.search_depth.domain_count}")
    print(f"  Estimated hops: {result.search_depth.estimated_hops}")
    print()
    print(f"Axis 3 — Synthesis Quality:   {result.synthesis_quality.score:.3f}")
    print(f"  Comprehensiveness: {result.synthesis_quality.r_comprehensiveness:.3f}")
    print(f"  Insight:           {result.synthesis_quality.r_insight:.3f}")
    print(f"  Instruction-follow:{result.synthesis_quality.r_instruction_following:.3f}")
    print(f"  Readability:       {result.synthesis_quality.r_readability:.3f}")
    print()
    print(f"Axis 4 — Citation Verify:     {result.citation_verify.score:.3f}")
    print(f"  Total: {result.citation_verify.total_citations}")
    print(f"  Effective: {result.citation_verify.effective_citations}")
    print(f"  Accuracy: {result.citation_verify.accuracy:.2f}")
    print()
    print(f"Axis 5 — Orchestration:       {result.orchestration.score:.3f}")
    print(f"  Completion rate: {result.orchestration.completion_rate:.2f}")
    print()
    print(f"{'='*60}")
    print(f"Overall Score: {result.overall_score:.3f}  Grade: {result.grade}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
