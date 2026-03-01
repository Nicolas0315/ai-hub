#!/usr/bin/env python3
"""
KS47 Deep Research Benchmark: Head-to-head comparison of DRA outputs.

Runs KS47 5-axis verification on all available model outputs from
DeepResearch Bench and produces a comparative leaderboard.

Usage:
  python3 benchmarks/deep_research/run_ks47_benchmark.py
"""

import sys
import os
import json
import time

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.katala_samurai.ks47_deep_research import KS47, BenchmarkRunner


DATA_DIR = os.path.join(os.path.dirname(__file__),
                        'deep_research_bench', 'data')

MODELS = [
    'gemini-2.5-pro-deepresearch',
    'openai-deepresearch',
    'perplexity-Research',
    'grok-deeper-search',
    'claude-3-7-sonnet-latest',
    'reference',  # Expert-written reference reports
]

# Full 5-axis weights
WEIGHTS_5AXIS = {
    "query_coverage": 0.15,
    "search_depth": 0.20,
    "synthesis_quality": 0.30,
    "citation_verify": 0.25,
    "orchestration": 0.10,
}

# Content-only weights (no URL data in cleaned reports)
WEIGHTS_CONTENT = {
    "query_coverage": 0.25,
    "search_depth": 0.00,
    "synthesis_quality": 0.45,
    "citation_verify": 0.00,
    "orchestration": 0.30,
}


def run_benchmark(weights: dict, label: str) -> list[dict]:
    """Run benchmark with given weights across all models."""
    engine = KS47(weights=weights)
    runner = BenchmarkRunner(engine)

    results = []
    for model in MODELS:
        target_file = os.path.join(
            DATA_DIR, 'test_data', 'cleaned_data', f'{model}.jsonl'
        )
        if not os.path.exists(target_file):
            print(f"  ⚠ Skipping {model} (file not found)")
            continue

        t0 = time.time()
        result = runner.run_deepresearch_bench(DATA_DIR, target_model=model)
        elapsed = time.time() - t0

        if 'error' in result:
            print(f"  ❌ {model}: {result['error']}")
            continue

        # Grade distribution
        grades = {}
        for r in result['results']:
            g = r['ks47_grade']
            grades[g] = grades.get(g, 0) + 1

        # Per-axis averages
        axes = result['average_axes']

        # Citation stats
        avg_citations = (sum(r['citation_count'] for r in result['results'])
                        / max(1, len(result['results'])))
        avg_claims = (sum(r['claim_count'] for r in result['results'])
                     / max(1, len(result['results'])))
        avg_len = (sum(r['report_length'] for r in result['results'])
                  / max(1, len(result['results'])))

        entry = {
            'model': model,
            'score': result['average_score'],
            'grade': result['average_grade'],
            'axes': axes,
            'grades': grades,
            'avg_citations': round(avg_citations, 1),
            'avg_claims': round(avg_claims, 1),
            'avg_report_length': round(avg_len, 0),
            'tasks': result['task_count'],
            'elapsed_s': round(elapsed, 2),
        }
        results.append(entry)
        print(f"  ✅ {model}: {entry['score']:.4f} ({entry['grade']}) [{elapsed:.1f}s]")

    # Sort by score descending
    results.sort(key=lambda x: x['score'], reverse=True)
    return results


def print_leaderboard(results: list[dict], label: str):
    """Print a formatted leaderboard."""
    print(f"\n{'='*80}")
    print(f"  KS47 Deep Research Leaderboard — {label}")
    print(f"{'='*80}")
    print(f"{'Rank':<5} {'Model':<35} {'Score':<8} {'Grade':<6} "
          f"{'QC':<7} {'SQ':<7} {'OV':<7} {'SD':<7} {'CV':<7}")
    print(f"{'-'*80}")

    for i, r in enumerate(results):
        ax = r['axes']
        print(f"  {i+1:<3} {r['model']:<35} {r['score']:.4f}  {r['grade']:<5} "
              f"{ax.get('query_coverage', 0):.4f} "
              f"{ax.get('synthesis_quality', 0):.4f} "
              f"{ax.get('orchestration', 0):.4f} "
              f"{ax.get('search_depth', 0):.4f} "
              f"{ax.get('citation_verify', 0):.4f}")

    print(f"{'-'*80}")

    # Stats
    print(f"\n  Report Stats:")
    print(f"  {'Model':<35} {'Avg Len':<10} {'Avg Claims':<12} {'Avg Citations':<14} {'Grade Distribution'}")
    print(f"  {'-'*80}")
    for r in results:
        grade_str = ' '.join(f"{g}={c}" for g, c in
                            sorted(r['grades'].items(),
                                   key=lambda x: 'SABCDF'.index(x[0])
                                   if x[0] in 'SABCDF' else 99))
        print(f"  {r['model']:<35} {r['avg_report_length']:<10.0f} "
              f"{r['avg_claims']:<12.1f} {r['avg_citations']:<14.1f} {grade_str}")


def main():
    print("KS47 Deep Research Benchmark Runner")
    print("=" * 50)

    # Run content-only evaluation (no URL data in cleaned reports)
    print("\n[1/2] Running content-only evaluation (3 axes)...")
    content_results = run_benchmark(WEIGHTS_CONTENT, "Content-Only (3 axes)")
    print_leaderboard(content_results, "Content-Only (Query Coverage + Synthesis + Orchestration)")

    # Run full 5-axis evaluation (search_depth and citation will be low without URLs)
    print("\n[2/2] Running full 5-axis evaluation...")
    full_results = run_benchmark(WEIGHTS_5AXIS, "Full 5-axis")
    print_leaderboard(full_results, "Full 5-axis (includes Search Depth + Citation)")

    # Save results
    output = {
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'ks47_version': 'KS47-v1',
        'benchmark': 'DeepResearch Bench (100 tasks, 22 domains)',
        'content_only': content_results,
        'full_5axis': full_results,
    }

    out_path = os.path.join(os.path.dirname(__file__), 'ks47_benchmark_results.json')
    with open(out_path, 'w') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to: {out_path}")


if __name__ == '__main__':
    main()
