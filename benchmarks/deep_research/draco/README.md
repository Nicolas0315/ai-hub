---
license: mit
language:
- en
tags:
- deep-research
pretty_name: DRACO Benchmark
---

# DRACO: a Cross-Domain Benchmark for Deep Research Accuracy, Completeness, and Objectivity

The DRACO Benchmark consists of complex, open-ended research tasks with expert-curated rubrics for evaluating deep research systems. Tasks span 10 domains and require drawing on information sources from 40 countries. Each task is paired with a detailed, task-specific rubric featuring an average of ~40 evaluation criteria across four axes: factual accuracy, breadth and depth of analysis, presentation quality, and citation quality.

Each task originates from actual user queries on Perplexity Deep Research. These queries are systematically reformulated, augmented, and filtered to remove personally identifiable information and ensure rigor. Rubrics were created and validated by 26 domain experts (including medical professionals, attorneys, financial analysts, software engineers, and designers) through a multi-stage iterative review process and task-level saturation testing.

## Task Characteristics

Each task is a deep research query that demands multi-hop agentic retrieval and reasoning, synthesis across heterogeneous sources, and domain expertise. Tasks were selected from queries where users expressed dissatisfaction with initial model responses, shifting the sampling distribution toward genuinely difficult problems. Additional variation is introduced along six dimensions: persona, output format, source specificity, temporal scope, cross-entity comparison, and geographic breadth. This ensures that the benchmark effectively stress-tests deep research systems on requests that faithfully characterize real-world usage by sophisticated, discerning users.

### Domain Distribution

| Domain | Share | Avg Criteria per Task |
|---|---|---|
| Finance | 20% | 47.6 |
| Shopping/Product Comparison | 16% | 39.7 |
| Academic | 12% | 41.6 |
| Technology | 10% | 36.7 |
| General Knowledge | 9% | 39.2 |
| UX Design | 9% | 36.9 |
| Law | 6% | 33.2 |
| Medicine | 6% | 33.7 |
| Needle in a Haystack | 6% | 30.2 |
| Personalized Assistant | 6% | 35.5 |

The domain distribution reflects the underlying mix of Deep Research usage observed on Perplexity during the September-October 2025 sampling window.

## Rubric Structure

Each task has a rubric with criteria organized into four evaluation axes. Criteria are assigned integer weights reflecting their relative importance. Positive weights reward desirable properties; negative weights penalize errors, with the most severe penalties reserved for harmful or dangerous content.

| Axis | Section ID | Weight Range | Avg Criteria per Task | Description |
|---|---|---|---|---|
| Factual Accuracy | `factual-accuracy` | -500 to +20 | 20.5 | Verifiable claims the response must state correctly |
| Breadth and Depth of Analysis | `breadth-and-depth-of-analysis` | -100 to +10 | 8.6 | Synthesis across sources, identification of trade-offs, actionable guidance where appropriate |
| Presentation Quality | `presentation-quality` | -50 to +20 | 5.6 | Precise terminology, structured format, readability, objective tone |
| Citation Quality | `citation-quality` | -150 to +10 | 4.8 | Citations to primary source documents |

Approximately 52% of criteria target factual accuracy, 22% assess analytical depth, 14% address presentation, and 12% evaluate source attribution. Of the 3,934 total criteria, 415 carry negative weights. Negative weights appear across all four axes, but the most severe penalties are reserved for harmful medical content, with weights ranging from -50 for harmful clinical guidance to -500 for dangerous recommendations. In non-medical domains, penalties typically range from -10 to -25.

Rubrics underwent a saturation test: if the best available system scored above 90% on a rubric, it was returned to the expert team for revision. Roughly 45% of rubrics were revised at least once through this process. Current best-system saturation is approximately 71%, indicating substantial headroom.

## Data Format

The dataset is a single JSONL file (`test.jsonl`) with 100 entries, one per line. Each entry has the following fields:

- **`id`** (string): A UUID uniquely identifying the task.
- **`domain`** (string): The task's domain category (e.g., `"Finance"`, `"Medicine"`, `"Needle in a Haystack"`).
- **`problem`** (string): The full research query to be answered. These are typically multi-sentence, specifying a persona, desired deliverable, scope constraints, and source preferences.
- **`answer`** (string): A JSON-encoded rubric. When parsed, it contains:
  - **`id`** (string): A human-readable slug identifying the rubric (e.g., `"staggered-did-methodology-evaluation"`).
  - **`sections`** (array): The evaluation axes, each containing:
    - **`id`** (string): Section identifier---one of `factual-accuracy`, `breadth-and-depth-of-analysis`, `presentation-quality`, or `citation-quality`.
    - **`title`** (string): Human-readable section name.
    - **`criteria`** (array): Individual evaluation criteria, each with:
      - **`id`** (string): A descriptive slug for the criterion.
      - **`weight`** (integer): The criterion's weight. Positive values reward meeting the criterion; negative values penalize meeting it (i.e., the criterion describes an error, and a MET verdict means the error is present).
      - **`requirement`** (string): A natural-language description of what to check in the response.

## Evaluation Methodology

### Grading Protocol

Responses are evaluated using an LLM-as-a-judge protocol. For each criterion in a task's rubric, the judge model receives the original query, the system's response, and a single criterion, then produces a binary verdict (**MET** or **UNMET**) with a brief justification.

Criteria fall into two types based on their weight sign:

- **Positive criteria** (positive weight): Describe desirable properties. MET means the response satisfies the requirement. UNMET means it does not.
- **Negative criteria** (negative weight): Describe errors or harmful content. MET means the response *contains* the error. UNMET means it does not.

For reproducible evaluation, use a capable judge model with low temperature. See the dataset paper for the grading prompt.

### Scoring

For a task with criteria indexed by *i*, each with weight *w_i* and binary verdict *v_i* (1 if MET, 0 if UNMET):

```
raw_score = sum(v_i * w_i for all i)
normalized_score = clamp(raw_score / sum(w_i for all i where w_i > 0), 0, 1) * 100%
```

The normalized score ranges from 0 to 100%. Because negative-weight criteria contribute to the raw score when MET (reducing it), a system that makes penalized errors can score below what its positive-criteria performance alone would suggest.


## Intended Use

- Evaluating and comparing Deep Research systems (agentic research agents that browse the web, synthesize sources, and produce cited reports) on complex tasks faithful to real-world usage.
- Measuring factual accuracy, analytical depth, presentation quality, and citation practices in long-form research outputs.
- Identifying domain-specific strengths and weaknesses of research systems.

## Limitations

- **Domain coverage.** The selected domains reflect a broad cross-section of observed usage, but these domains do not exhaustively cover all possible Deep Research applications.
- **Static snapshot.** Tasks and rubrics reflect information available during the construction period (late 2025), and accuracy is therefore judged on static criteria.
- **LLM judge variance.** While relative rankings are stable across judge models, absolute scores vary. Results should be compared within consistent judge configurations.

## Citation

```bibtex
@misc{draco2026,
  title={DRACO: A Cross-Domain Benchmark for Deep Research Accuracy, Completeness, and Objectivity},
  author={Joey Zhong and Hao Zhang and Clare Southern and Jeremy Yang and Thomas Wang and Kate Jung and Shu Zhang and Denis Yarats and Johnny Ho and Jerry Ma},
  year={2026},
  url={https://arxiv.org/abs/2602.11685}
}
```
