#!/bin/bash
# Setup script for Deep Research benchmark datasets
# Run from katala/benchmarks/deep_research/

set -e

echo "=== Cloning Deep Research Benchmarks ==="

# DeepResearch Bench (RACE + FACT evaluation, 100 tasks)
# Paper: arxiv 2506.11763
[ -d deep_research_bench ] || git clone https://github.com/Ayanami0730/deep_research_bench.git

# DeepResearch Bench II (9430 fine-grained rubrics, 132 tasks)
# Paper: arxiv 2601.08536
[ -d DeepResearch-Bench-II ] || git clone https://github.com/imlrz/DeepResearch-Bench-II.git

# ResearcherBench (65 frontier research questions, rubric + factual)
# Paper: arxiv 2507.16280
[ -d ResearcherBench ] || git clone https://github.com/GAIR-NLP/ResearcherBench.git

# FS-Researcher (SOTA dual-agent framework for reference)
# Paper: arxiv 2602.01566
[ -d FS-Researcher ] || git clone https://github.com/Ignoramus0817/FS-Researcher.git

# Vision-DeepResearch (multimodal benchmark)
# Paper: arxiv 2602.02185
[ -d Vision-DeepResearch ] || git clone https://github.com/Osilly/Vision-DeepResearch.git

# DRACO (Perplexity benchmark, 100 tasks, Hugging Face)
if [ ! -d draco ]; then
  echo "Downloading DRACO from Hugging Face..."
  python3 -c "
from huggingface_hub import snapshot_download
snapshot_download('perplexity-ai/draco', local_dir='draco', repo_type='dataset')
"
fi

echo ""
echo "=== Setup Complete ==="
echo "Available benchmarks:"
ls -d */ 2>/dev/null | sed 's/\///' | while read d; do echo "  - $d"; done
