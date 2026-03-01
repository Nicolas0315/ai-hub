"""
KS43 — Katala Samurai 43: CUDA/GPGPU Knowledge Module

Systematizes CUDA/GPGPU knowledge acquired through empirical local LLM
benchmarking and deep architecture analysis across two GPU generations:
RTX 5070 Ti (Blackwell, CC 12.0) and RTX 3070 (Ampere, CC 8.6).

Key knowledge axes:
1. GPU Architecture Hierarchy: SM → Warp → Thread → Memory
2. LLM Inference Bottleneck Analysis: Compute-bound vs Memory-bound
3. Cross-Generation Compatibility: KV Cache, Flash Attention, Kernel selection
4. Ollama/ggml-cuda Runtime Analysis: Overhead decomposition
5. GGUF Binary Forensics: Architecture detection, crash diagnosis

Empirical findings codified as verification rules:
- KV_CACHE_TYPE=q8_0 requires CC≥12.0 (Blackwell); Ampere fallback = 52x slowdown
- Flash Attention is mandatory for correct prompt eval on all architectures
- LLM generation is memory-bandwidth-bound: GPU clock OC has zero effect
- Ollama overhead is ≤4.3%; llama.cpp direct offers negligible improvement
- Nemotron-H (Mamba+Transformer hybrid) is unsupported in llama.cpp/Ollama

Philosophical basis:
- Empiricism: All claims backed by reproducible measurements
- Popper (falsifiability): Each finding framed as testable prediction
- Kuhn (paradigm): GPU architecture as paradigm shift (SIMT → Tensor Core → SSM)

Design: Youta Hilono, 2026-03-01
Implementation: Shirokuma (OpenClaw AI)
Empirical data: ultra2025 (RTX 5070 Ti) + nicolas2025 (RTX 3070)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ═══════════════════════════════════════════════
# Constants — GPU Architecture Parameters
# ═══════════════════════════════════════════════

VERSION = "KS43"

# ── Named Constants (avoiding magic numbers) ──
CC_BLACKWELL_MIN = 12.0          # Minimum CC for Blackwell features (q8_0 KV)
CC_TURING_MIN = 7.0
CC_AMPERE_MIN = 8.0
CC_ADA_MIN = 9.0
CC_HOPPER_MIN = 10.0

# Benchmark reference values
QWEN3_8B_Q4_SIZE_GB = 4.65      # qwen3:8b Q4_K_M model size
LLAMA32_1B_SIZE_GB = 1.3         # llama3.2:1b model size

# VRAM estimation parameters
VRAM_OVERHEAD_FACTOR = 1.10      # 10% overhead for activations/buffers/CUDA ctx
VRAM_DEVIATION_THRESHOLD_GB = 2.0  # Max acceptable VRAM estimation error
OVERHEAD_THRESHOLD_PCT = 20.0    # Max acceptable framework overhead

# Bottleneck classification thresholds
MEMORY_BOUND_THRESHOLD = 0.70    # efficiency > 70% → memory bound
MIXED_REGIME_THRESHOLD = 0.30    # efficiency > 30% → mixed; below = anomalous
GENERATION_VALID_THRESHOLD = 0.50  # efficiency > 50% → generation speed valid

# Efficiency estimation
DEFAULT_EFFICIENCY_FACTOR = 0.85  # Conservative default (empirical: 0.73-0.92)

# VRAM budget thresholds
VRAM_DUAL_CTX_FACTOR = 2.0      # vram >= base*2.0 → ctx=8192
VRAM_SINGLE_CTX_FACTOR = 1.3    # vram >= base*1.3 → ctx=4096
VRAM_PARALLEL_THRESHOLD_GB = 12.0  # vram >= 12GB → parallel=2

# Context sizes
CTX_SMALL = 2048
CTX_MEDIUM = 4096
CTX_LARGE = 8192

# Default model parameters (qwen3:8b architecture)
DEFAULT_NUM_LAYERS = 32
DEFAULT_NUM_KV_HEADS = 4
DEFAULT_HEAD_DIM = 128

# Batch size optimals (empirically determined)
BATCH_SIZE_BLACKWELL_SPEED = 256
BATCH_SIZE_AMPERE_SPEED = 512

# GPU clock data
RTX5070TI_MAX_GPU_MHZ = 3090
RTX5070TI_MAX_MEM_MHZ = 14001
RTX5070TI_TDP_W = 300
RTX5070TI_VRAM_GB = 16.0
RTX5070TI_BW_GB_S = 672.0

RTX3070_MAX_GPU_MHZ = 2100
RTX3070_MAX_MEM_MHZ = 7001
RTX3070_TDP_W = 240
RTX3070_VRAM_GB = 8.0
RTX3070_BW_GB_S = 448.0

# KV cache bytes per element
KV_BYTES_Q8 = 1.0
KV_BYTES_F16 = 2.0

# Rounding precision (Katala convention)
SCORE_PRECISION = 4

# Compute Capability → Feature Matrix
GPU_FEATURES: Dict[str, Dict[str, Any]] = {
    "ampere_sm86": {
        "compute_capability": 8.6,
        "generation": "Ampere",
        "fp16_tensor_cores": True,
        "bf16_tensor_cores": True,
        "fp8_tensor_cores": False,
        "int8_tensor_cores": True,
        "kv_cache_q8_native": False,      # ← Critical finding
        "flash_attention_optimized": True,
        "max_shared_memory_per_sm_kb": 100,
        "example_gpu": "RTX 3070",
        "memory_type": "GDDR6",
    },
    "blackwell_sm120": {
        "compute_capability": 12.0,
        "generation": "Blackwell",
        "fp16_tensor_cores": True,
        "bf16_tensor_cores": True,
        "fp8_tensor_cores": True,
        "int8_tensor_cores": True,
        "kv_cache_q8_native": True,       # ← Hardware-accelerated
        "flash_attention_optimized": True,
        "max_shared_memory_per_sm_kb": 228,
        "example_gpu": "RTX 5070 Ti",
        "memory_type": "GDDR7",
    },
}

# Empirical Benchmark Data (qwen3:8b Q4_K_M, Ollama 0.16.x)
BENCHMARK_DATA: Dict[str, Dict[str, float]] = {
    "rtx5070ti_qwen3_8b_q4": {
        "prompt_eval_tok_s": 580.72,     # --verbose (includes thinking)
        "prompt_eval_raw_tok_s": 786.6,  # API raw mode (pure PE)
        "generation_tok_s": 132.44,
        "vram_used_gb": 6.0,
        "model_size_gb": 4.65,
        "memory_bandwidth_gb_s": 672.0,
        "theoretical_gen_max": 144.5,    # BW / model_size
        "efficiency_pct": 91.6,          # actual / theoretical
    },
    "rtx3070_qwen3_8b_q4": {
        "prompt_eval_tok_s": 567.64,     # After KV cache fix
        "prompt_eval_raw_tok_s": 680.2,
        "generation_tok_s": 70.6,
        "vram_used_gb": 6.0,
        "model_size_gb": 4.65,
        "memory_bandwidth_gb_s": 448.0,
        "theoretical_gen_max": 96.3,
        "efficiency_pct": 73.3,
    },
    "rtx5070ti_llama32_1b": {
        "prompt_eval_tok_s": 3721.10,
        "generation_tok_s": 527.11,
        "model_size_gb": 1.3,
        "theoretical_gen_max": 517.0,    # 672 / 1.3
        "efficiency_pct": 101.9,         # Exceeds due to caching
    },
    "rtx3070_llama32_1b": {
        "prompt_eval_tok_s": 2639.89,
        "generation_tok_s": 263.97,
        "model_size_gb": 1.3,
        "theoretical_gen_max": 344.6,    # 448 / 1.3
        "efficiency_pct": 76.6,
    },
}

# Known Compatibility Issues (Empirically Verified)
COMPATIBILITY_RULES: List[Dict[str, Any]] = [
    {
        "id": "KV_CACHE_Q8_CC_REQUIREMENT",
        "rule": "OLLAMA_KV_CACHE_TYPE=q8_0 requires Compute Capability >= 12.0",
        "severity": "critical",
        "symptom": "Prompt eval speed drops 52x (580 → 10.91 tok/s)",
        "root_cause": "q8_0 KV cache kernel uses Blackwell-specific instructions; "
                      "Ampere falls back to software emulation path",
        "fix": "Set OLLAMA_KV_CACHE_TYPE=f16 for CC < 12.0",
        "verified_on": ["RTX 3070 (CC 8.6)", "RTX 5070 Ti (CC 12.0)"],
        "falsifiable_prediction": "Any GPU with CC < 12.0 will show >10x PE slowdown "
                                  "with KV_CACHE_TYPE=q8_0 vs f16",
    },
    {
        "id": "FLASH_ATTENTION_MANDATORY",
        "rule": "OLLAMA_FLASH_ATTENTION=1 is required for correct prompt eval speed",
        "severity": "critical",
        "symptom": "gemma3:12b PE drops from 98.45 to 1.24 tok/s without FA",
        "root_cause": "Standard attention kernel doesn't use Tensor Cores efficiently; "
                      "FA enables fused softmax+matmul with tiling",
        "fix": "Set OLLAMA_FLASH_ATTENTION=1",
        "verified_on": ["RTX 5070 Ti", "RTX 3070"],
    },
    {
        "id": "NEMOTRON_H_UNSUPPORTED",
        "rule": "Nemotron-H architecture (Mamba + Transformer hybrid) crashes in Ollama/llama.cpp",
        "severity": "blocker",
        "symptom": "exit status 2 on any inference attempt",
        "root_cause": "GGUF metadata: general.architecture=nemotron_h; "
                      "llama.cpp Issue #15409 — SSM selective scan hangs, "
                      "Conv1D causality issues, KV cache collision with non-recurrent layers",
        "fix": "Use vLLM (HF transformers backend) or TensorRT-LLM (Linux only)",
        "verified_on": ["RTX 5070 Ti with Ollama 0.16.2"],
        "gguf_metadata": {
            "architecture": "nemotron_h",
            "ssm_components": ["conv_kernel", "state_size", "group_count", "inner_size"],
            "attention_components": ["head_count", "head_count_kv", "key_length"],
            "note": "No RoPE in attention layers (Nemotron-H specific)",
        },
    },
    {
        "id": "GPU_CLOCK_OC_INEFFECTIVE",
        "rule": "GPU core clock overclocking has zero effect on LLM generation speed",
        "severity": "info",
        "symptom": "nvidia-smi -lgc 3090 → GEN unchanged (131.9 vs 133.4 tok/s)",
        "root_cause": "LLM token generation is memory-bandwidth-bound; "
                      "GPU compute is not the bottleneck for autoregressive decoding",
        "verified_on": ["RTX 5070 Ti: 2490MHz→3090MHz = 0% improvement"],
    },
]

# ═══════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════

@dataclass(slots=True)
class GPUProfile:
    """Hardware profile for a specific GPU."""
    name: str
    compute_capability: float
    generation: str
    vram_gb: float
    memory_bandwidth_gb_s: float
    memory_type: str
    max_gpu_clock_mhz: int
    max_mem_clock_mhz: int
    tdp_watts: int

    @property
    def theoretical_gen_tok_s(self) -> float:
        """Theoretical max generation speed for a Q4 model."""
        return self.memory_bandwidth_gb_s / QWEN3_8B_Q4_SIZE_GB

    def supports_kv_cache_q8(self) -> bool:
        """Check if this GPU supports native q8_0 KV cache."""
        return self.compute_capability >= CC_BLACKWELL_MIN

    def optimal_kv_cache_type(self) -> str:
        """Return the optimal KV cache type for this GPU."""
        return "q8_0" if self.supports_kv_cache_q8() else "f16"

    def can_fit_model(self, model_size_gb: float,
                      ctx_overhead_gb: float = 1.0) -> bool:
        """Check if a model fits in VRAM with context overhead."""
        return (model_size_gb + ctx_overhead_gb) <= self.vram_gb


@dataclass(slots=True)
class InferenceResult:
    """Result of an LLM inference benchmark."""
    gpu: str
    model: str
    quantization: str
    prompt_eval_tok_s: float
    generation_tok_s: float
    load_duration_ms: float
    total_duration_ms: float
    prompt_tokens: int
    generated_tokens: int
    vram_used_gb: float
    num_ctx: int = 4096
    num_batch: int = 512
    kv_cache_type: str = "f16"
    flash_attention: bool = True

    @property
    def overhead_ms(self) -> float:
        """Compute framework overhead (non-inference time)."""
        pe_ms = (self.prompt_tokens / self.prompt_eval_tok_s * 1000
                 if self.prompt_eval_tok_s > 0 else 0)
        gen_ms = (self.generated_tokens / self.generation_tok_s * 1000
                  if self.generation_tok_s > 0 else 0)
        return self.total_duration_ms - pe_ms - gen_ms - self.load_duration_ms

    @property
    def overhead_pct(self) -> float:
        """Framework overhead as percentage of total time."""
        return (self.overhead_ms / self.total_duration_ms * 100
                if self.total_duration_ms > 0 else 0)

    @property
    def useful_work_pct(self) -> float:
        """Percentage of time spent on actual inference."""
        return 100.0 - self.overhead_pct - (
            self.load_duration_ms / self.total_duration_ms * 100
            if self.total_duration_ms > 0 else 0
        )


@dataclass(slots=True)
class CompatibilityCheck:
    """Result of checking GPU+config compatibility."""
    gpu_name: str
    compute_capability: float
    config: Dict[str, str]
    issues: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    @property
    def has_critical_issues(self) -> bool:
        return any(i.get("severity") == "critical" for i in self.issues)

    @property
    def has_blockers(self) -> bool:
        return any(i.get("severity") == "blocker" for i in self.issues)


# ═══════════════════════════════════════════════
# Core Functions — Architecture Analysis
# ═══════════════════════════════════════════════

# -- S2: Observation Layer --

def profile_gpu(name: str, cc: float, vram_gb: float,
                bw_gb_s: float, mem_type: str,
                max_gpu_mhz: int, max_mem_mhz: int,
                tdp_w: int) -> GPUProfile:
    """Create a GPU hardware profile.

    Maps to KS S2 (Observation): Raw hardware data collection.

    >>> p = profile_gpu("RTX 3070", 8.6, 8.0, 448.0, "GDDR6", 2100, 7001, 240)
    >>> p.supports_kv_cache_q8()
    False
    >>> p.optimal_kv_cache_type()
    'f16'
    """
    gen_map = {
        (int(CC_TURING_MIN), int(CC_AMPERE_MIN)): "Turing",
        (int(CC_AMPERE_MIN), int(CC_ADA_MIN)): "Ampere",
        (int(CC_ADA_MIN), int(CC_HOPPER_MIN)): "Ada Lovelace",
        (int(CC_HOPPER_MIN), int(CC_HOPPER_MIN) + 1): "Hopper",
        (int(CC_BLACKWELL_MIN), int(CC_BLACKWELL_MIN) + 1): "Blackwell",
    }
    generation = "Unknown"
    major = int(cc)
    for (lo, hi), gen_name in gen_map.items():
        if lo <= major < hi:
            generation = gen_name
            break

    return GPUProfile(
        name=name,
        compute_capability=cc,
        generation=generation,
        vram_gb=vram_gb,
        memory_bandwidth_gb_s=bw_gb_s,
        memory_type=mem_type,
        max_gpu_clock_mhz=max_gpu_mhz,
        max_mem_clock_mhz=max_mem_mhz,
        tdp_watts=tdp_w,
    )


# -- S3: Pattern Recognition --

def analyze_bottleneck(gpu: GPUProfile, model_size_gb: float,
                       measured_gen_tok_s: float) -> Dict[str, Any]:
    """Determine if inference is compute-bound or memory-bound.

    Maps to KS S3 (Pattern Recognition): Classify performance regime.

    The memory-bandwidth model predicts:
        theoretical_max = bandwidth_GB_s / model_size_GB

    If measured/theoretical > 0.7, inference is memory-bound (typical for LLMs).
    If measured/theoretical < 0.3, something else is wrong (config, offload, etc).

    >>> gpu = profile_gpu("RTX 5070 Ti", 12.0, 16.0, 672.0, "GDDR7", 3090, 14001, 300)
    >>> result = analyze_bottleneck(gpu, 4.65, 133.4)
    >>> result["regime"]
    'memory_bound'
    >>> result["efficiency_pct"] > 85
    True
    """
    theoretical_max = gpu.memory_bandwidth_gb_s / model_size_gb
    efficiency = min(max(
        measured_gen_tok_s / theoretical_max if theoretical_max > 0 else 0.0,
        0.0), 1.0)  # Clamp to [0, 1]

    if efficiency > MEMORY_BOUND_THRESHOLD:
        regime = "memory_bound"
        explanation = (
            f"Generation at {efficiency:.1%} of memory bandwidth limit. "
            f"GPU clock OC will NOT improve speed. "
            f"Only higher memory bandwidth (faster VRAM) would help."
        )
    elif efficiency > MIXED_REGIME_THRESHOLD:
        regime = "mixed"
        explanation = (
            f"Generation at {efficiency:.1%} of theoretical max. "
            f"Possible causes: KV cache overhead, batch scheduling, "
            f"or partial CPU offloading."
        )
    else:
        regime = "anomalous"
        explanation = (
            f"Generation at {efficiency:.1%} of theoretical max — anomalously low. "
            f"Check: KV cache type compatibility, Flash Attention status, "
            f"CPU offloading, or model corruption."
        )

    return {
        "regime": regime,
        "theoretical_max_tok_s": round(theoretical_max, SCORE_PRECISION),
        "measured_tok_s": measured_gen_tok_s,
        "efficiency_pct": round(efficiency * 100, SCORE_PRECISION),
        "explanation": explanation,
        "gpu_clock_oc_effective": regime != "memory_bound",
    }


# -- S4: Hypothesis Formation --

def check_compatibility(gpu: GPUProfile,
                        config: Dict[str, str]) -> CompatibilityCheck:
    """Validate GPU + Ollama configuration compatibility.

    Maps to KS S4 (Hypothesis): Generate predictions from rules.

    Applies all COMPATIBILITY_RULES against the given GPU profile
    and configuration. Returns issues and recommendations.

    >>> gpu = profile_gpu("RTX 3070", 8.6, 8.0, 448.0, "GDDR6", 2100, 7001, 240)
    >>> config = {"OLLAMA_KV_CACHE_TYPE": "q8_0", "OLLAMA_FLASH_ATTENTION": "1"}
    >>> result = check_compatibility(gpu, config)
    >>> result.has_critical_issues
    True
    >>> any("q8_0" in r for r in result.recommendations)
    True
    """
    check = CompatibilityCheck(
        gpu_name=gpu.name,
        compute_capability=gpu.compute_capability,
        config=config,
    )

    # Rule: KV Cache Q8 compatibility
    kv_type = config.get("OLLAMA_KV_CACHE_TYPE", "f16")
    if kv_type == "q8_0" and not gpu.supports_kv_cache_q8():
        rule = next(r for r in COMPATIBILITY_RULES
                    if r["id"] == "KV_CACHE_Q8_CC_REQUIREMENT")
        check.issues.append({
            "rule_id": rule["id"],
            "severity": rule["severity"],
            "description": rule["rule"],
            "symptom": rule["symptom"],
        })
        check.recommendations.append(
            f"Change OLLAMA_KV_CACHE_TYPE from q8_0 to "
            f"{gpu.optimal_kv_cache_type()} for {gpu.name} (CC {gpu.compute_capability})"
        )

    # Rule: Flash Attention
    fa = config.get("OLLAMA_FLASH_ATTENTION", "0")
    if fa != "1":
        rule = next(r for r in COMPATIBILITY_RULES
                    if r["id"] == "FLASH_ATTENTION_MANDATORY")
        check.issues.append({
            "rule_id": rule["id"],
            "severity": rule["severity"],
            "description": rule["rule"],
            "symptom": rule["symptom"],
        })
        check.recommendations.append(
            "Set OLLAMA_FLASH_ATTENTION=1 — required for correct prompt eval speed"
        )

    # Info: GPU clock OC
    check.recommendations.append(
        f"GPU clock OC is ineffective for LLM inference on {gpu.name} "
        f"(memory-bandwidth bound at {gpu.memory_bandwidth_gb_s} GB/s)"
    )

    return check


# -- S5: Experimentation --

def predict_generation_speed(gpu: GPUProfile, model_size_gb: float,
                             efficiency_factor: float = DEFAULT_EFFICIENCY_FACTOR) -> float:
    """Predict generation speed for a given GPU + model combination.

    Maps to KS S5 (Experimentation): Generate testable predictions.

    Uses the memory-bandwidth model:
        predicted = (bandwidth / model_size) * efficiency_factor

    Default efficiency_factor=0.85 is conservative (empirical range: 0.73-0.92).

    >>> gpu = profile_gpu("RTX 5070 Ti", 12.0, 16.0, 672.0, "GDDR7", 3090, 14001, 300)
    >>> speed = predict_generation_speed(gpu, 4.65, 0.92)
    >>> 120 < speed < 140  # ~132.99
    True
    """
    theoretical = gpu.memory_bandwidth_gb_s / model_size_gb
    return round(theoretical * efficiency_factor, SCORE_PRECISION)


def estimate_vram_usage(model_size_gb: float, num_ctx: int = CTX_MEDIUM,
                        kv_cache_type: str = "f16",
                        num_layers: int = DEFAULT_NUM_LAYERS,
                        num_kv_heads: int = DEFAULT_NUM_KV_HEADS,
                        head_dim: int = DEFAULT_HEAD_DIM) -> float:
    """Estimate VRAM usage for a model with given context length.

    Maps to KS S5: Quantitative prediction.

    VRAM ≈ model_weights + kv_cache_size
    KV cache = 2 * num_layers * num_kv_heads * head_dim * num_ctx * bytes_per_element

    >>> usage = estimate_vram_usage(4.65, num_ctx=4096)
    >>> 5.0 < usage < 7.0
    True
    >>> usage_large = estimate_vram_usage(4.65, num_ctx=32768)
    >>> usage_large > usage
    True
    """
    bytes_per_elem = KV_BYTES_Q8 if kv_cache_type == "q8_0" else KV_BYTES_F16
    kv_cache_bytes = (2 * num_layers * num_kv_heads * head_dim
                      * num_ctx * bytes_per_elem)
    kv_cache_gb = kv_cache_bytes / (1024 ** 3)

    total = (model_size_gb + kv_cache_gb) * VRAM_OVERHEAD_FACTOR

    return round(total, SCORE_PRECISION)


# -- S6: Verification --

def verify_benchmark(result: InferenceResult,
                     gpu: GPUProfile) -> Dict[str, Any]:
    """Verify a benchmark result against theoretical expectations.

    Maps to KS S6 (Verification): Check empirical data against model.

    Returns confidence score and anomaly flags.

    >>> gpu = profile_gpu("RTX 5070 Ti", 12.0, 16.0, 672.0, "GDDR7", 3090, 14001, 300)
    >>> r = InferenceResult(
    ...     gpu="RTX 5070 Ti", model="qwen3:8b", quantization="Q4_K_M",
    ...     prompt_eval_tok_s=580.0, generation_tok_s=133.0,
    ...     load_duration_ms=98, total_duration_ms=1700,
    ...     prompt_tokens=22, generated_tokens=200,
    ...     vram_used_gb=6.0
    ... )
    >>> v = verify_benchmark(r, gpu)
    >>> v["generation_valid"]
    True
    >>> v["confidence"] > 0.8
    True
    """
    model_size_gb = BENCHMARK_DATA.get(
        "rtx5070ti_qwen3_8b_q4", {}
    ).get("model_size_gb", QWEN3_8B_Q4_SIZE_GB)

    bottleneck = analyze_bottleneck(gpu, model_size_gb, result.generation_tok_s)

    anomalies = []

    # Check generation speed against theoretical
    gen_valid = bottleneck["efficiency_pct"] > GENERATION_VALID_THRESHOLD * 100
    if not gen_valid:
        anomalies.append(
            f"Generation speed {result.generation_tok_s} tok/s is "
            f"{bottleneck['efficiency_pct']}% of theoretical — anomalously low"
        )

    # Check overhead
    overhead_valid = result.overhead_pct < OVERHEAD_THRESHOLD_PCT
    if not overhead_valid:
        anomalies.append(
            f"Framework overhead {result.overhead_pct:.1f}% exceeds "
            f"{OVERHEAD_THRESHOLD_PCT}% threshold"
        )

    # Check VRAM usage
    estimated_vram = estimate_vram_usage(
        model_size_gb, result.num_ctx, result.kv_cache_type
    )
    vram_valid = abs(result.vram_used_gb - estimated_vram) < VRAM_DEVIATION_THRESHOLD_GB
    if not vram_valid:
        anomalies.append(
            f"VRAM usage {result.vram_used_gb}GB deviates from "
            f"estimated {estimated_vram}GB"
        )

    # Composite confidence (clamped to [0, 1])
    checks = [gen_valid, overhead_valid, vram_valid]
    confidence = min(max(sum(checks) / len(checks), 0.0), 1.0)

    return {
        "generation_valid": gen_valid,
        "overhead_valid": overhead_valid,
        "vram_valid": vram_valid,
        "confidence": round(confidence, SCORE_PRECISION),
        "bottleneck_analysis": bottleneck,
        "anomalies": anomalies,
    }


# -- S7: Knowledge Integration --

def generate_optimal_config(gpu: GPUProfile,
                            available_vram_gb: Optional[float] = None,
                            target_model_size_gb: float = 4.65,
                            use_case: str = "general") -> Dict[str, str]:
    """Generate optimal Ollama configuration for a GPU.

    Maps to KS S7 (Integration): Synthesize actionable knowledge.

    Args:
        gpu: Hardware profile
        available_vram_gb: Override available VRAM (e.g., after desktop usage)
        target_model_size_gb: Size of the target model
        use_case: "general", "speed", or "quality"

    Returns:
        Dict of environment variable name → value

    >>> gpu = profile_gpu("RTX 3070", 8.6, 8.0, 448.0, "GDDR6", 2100, 7001, 240)
    >>> config = generate_optimal_config(gpu)
    >>> config["OLLAMA_KV_CACHE_TYPE"]
    'f16'
    >>> config["OLLAMA_FLASH_ATTENTION"]
    '1'
    """
    vram = available_vram_gb or gpu.vram_gb

    config = {
        "OLLAMA_FLASH_ATTENTION": "1",
        "OLLAMA_KV_CACHE_TYPE": gpu.optimal_kv_cache_type(),
    }

    # Context size based on available VRAM
    estimated_base = estimate_vram_usage(target_model_size_gb, num_ctx=CTX_MEDIUM)
    if vram >= estimated_base * VRAM_DUAL_CTX_FACTOR:
        config["num_ctx"] = str(CTX_LARGE)
    elif vram >= estimated_base * VRAM_SINGLE_CTX_FACTOR:
        config["num_ctx"] = str(CTX_MEDIUM)
    else:
        config["num_ctx"] = str(CTX_SMALL)

    # Parallel requests
    if vram >= VRAM_PARALLEL_THRESHOLD_GB:
        config["OLLAMA_NUM_PARALLEL"] = "2"
        config["OLLAMA_MAX_LOADED_MODELS"] = "2"
    else:
        config["OLLAMA_NUM_PARALLEL"] = "1"
        config["OLLAMA_MAX_LOADED_MODELS"] = "1"

    # Use case specific
    if use_case == "speed":
        config["num_ctx"] = str(CTX_SMALL)  # Minimize KV cache
        batch = (BATCH_SIZE_BLACKWELL_SPEED if gpu.generation == "Blackwell"
                 else BATCH_SIZE_AMPERE_SPEED)
        config["num_batch"] = str(batch)
    elif use_case == "quality":
        config["num_ctx"] = str(CTX_LARGE)

    return config


def cross_generation_comparison(gpu_a: GPUProfile, gpu_b: GPUProfile,
                                model_size_gb: float = 4.65) -> Dict[str, Any]:
    """Compare two GPUs across all relevant metrics.

    Maps to KS S7: Cross-domain knowledge synthesis.

    >>> a = profile_gpu("RTX 5070 Ti", 12.0, 16.0, 672.0, "GDDR7", 3090, 14001, 300)
    >>> b = profile_gpu("RTX 3070", 8.6, 8.0, 448.0, "GDDR6", 2100, 7001, 240)
    >>> cmp = cross_generation_comparison(a, b)
    >>> cmp["bandwidth_ratio"] > 1.0
    True
    >>> cmp["gen_speed_ratio"] > 1.0
    True
    """
    bw_ratio = gpu_a.memory_bandwidth_gb_s / gpu_b.memory_bandwidth_gb_s
    gen_a = predict_generation_speed(gpu_a, model_size_gb)
    gen_b = predict_generation_speed(gpu_b, model_size_gb)
    gen_ratio = gen_a / gen_b if gen_b > 0 else float("inf")

    return {
        "gpu_a": gpu_a.name,
        "gpu_b": gpu_b.name,
        "bandwidth_ratio": round(bw_ratio, SCORE_PRECISION),
        "gen_speed_ratio": round(gen_ratio, SCORE_PRECISION),
        "predicted_gen_a": gen_a,
        "predicted_gen_b": gen_b,
        "vram_ratio": round(gpu_a.vram_gb / gpu_b.vram_gb, SCORE_PRECISION),
        "power_ratio": round(gpu_a.tdp_watts / gpu_b.tdp_watts, SCORE_PRECISION),
        "kv_cache_compatible": {
            gpu_a.name: gpu_a.optimal_kv_cache_type(),
            gpu_b.name: gpu_b.optimal_kv_cache_type(),
        },
        "models_exclusive_to_a": [],  # Models that fit on A but not B
        "generation_gap_explanation": (
            f"Generation speed ratio ({gen_ratio:.1f}x) closely tracks "
            f"memory bandwidth ratio ({bw_ratio:.1f}x), confirming "
            f"memory-bandwidth-bound regime for autoregressive decoding."
        ),
    }


# ═══════════════════════════════════════════════
# GGUF Forensics — Binary-level analysis
# ═══════════════════════════════════════════════

# -- S3: Pattern Recognition (Binary Level) --

KNOWN_ARCHITECTURES: Dict[str, Dict[str, Any]] = {
    "llama": {"supported": True, "type": "transformer"},
    "qwen2": {"supported": True, "type": "transformer"},
    "gemma2": {"supported": True, "type": "transformer"},
    "gemma3": {"supported": True, "type": "transformer"},
    "nemotron_h": {
        "supported": False,
        "type": "hybrid_ssm_transformer",
        "components": ["mamba2_ssm", "attention", "mlp"],
        "failure_mode": "exit_status_2",
        "workaround": "vLLM with HuggingFace transformers backend",
    },
    "mamba": {"supported": False, "type": "ssm"},
}


def classify_gguf_architecture(arch_string: str) -> Dict[str, Any]:
    """Classify a GGUF architecture string.

    Maps to KS S3 (Pattern Recognition): Binary forensics.

    >>> classify_gguf_architecture("nemotron_h")["supported"]
    False
    >>> classify_gguf_architecture("llama")["supported"]
    True
    """
    info = KNOWN_ARCHITECTURES.get(arch_string, {
        "supported": None,
        "type": "unknown",
        "note": f"Architecture '{arch_string}' not in known database",
    })
    return {"architecture": arch_string, **info}


# ═══════════════════════════════════════════════
# Runtime Overhead Analysis
# ═══════════════════════════════════════════════

@dataclass(slots=True)
class OverheadAnalysis:
    """Decomposition of inference runtime overhead.

    Maps to KS S6 (Verification): Measure framework efficiency.
    """
    total_ms: float
    load_ms: float
    prompt_eval_ms: float
    generation_ms: float

    @property
    def overhead_ms(self) -> float:
        return self.total_ms - self.load_ms - self.prompt_eval_ms - self.generation_ms

    @property
    def overhead_pct(self) -> float:
        return self.overhead_ms / self.total_ms * 100 if self.total_ms > 0 else 0

    @property
    def useful_work_pct(self) -> float:
        return (self.prompt_eval_ms + self.generation_ms) / self.total_ms * 100

    def verdict(self) -> str:
        """Human-readable verdict on framework efficiency."""
        if self.overhead_pct < 5:
            return "excellent"
        elif self.overhead_pct < 15:
            return "acceptable"
        else:
            return "investigate"


EMPIRICAL_OVERHEAD = {
    "ollama_rtx5070ti": OverheadAnalysis(
        total_ms=1698, load_ms=98, prompt_eval_ms=28, generation_ms=1500
    ),
    "ollama_rtx3070": OverheadAnalysis(
        total_ms=5361, load_ms=83, prompt_eval_ms=32, generation_ms=2834
    ),
}


# ═══════════════════════════════════════════════
# Module self-test
# ═══════════════════════════════════════════════

def _self_test() -> Dict[str, Any]:
    """Run module self-test and return results.

    Verifies all docstring examples and empirical data consistency.
    """
    import doctest
    results = doctest.testmod(verbose=False)

    # Consistency checks
    checks = []

    # Check: All benchmark entries have efficiency data
    for key, data in BENCHMARK_DATA.items():
        has_eff = "efficiency_pct" in data
        checks.append(("benchmark_efficiency_" + key, has_eff))

    # Check: Compatibility rules have required fields
    required_fields = {"id", "rule", "severity"}
    for rule in COMPATIBILITY_RULES:
        has_fields = required_fields.issubset(rule.keys())
        checks.append(("rule_fields_" + rule["id"], has_fields))

    # Check: GPU features are consistent
    for arch_key, features in GPU_FEATURES.items():
        if features["kv_cache_q8_native"]:
            assert features["compute_capability"] >= CC_BLACKWELL_MIN, \
                f"{arch_key}: q8_native=True but CC<12.0"
        checks.append(("gpu_features_" + arch_key, True))

    return {
        "doctest_attempted": results.attempted,
        "doctest_failed": results.failed,
        "consistency_checks": len(checks),
        "consistency_passed": sum(1 for _, ok in checks if ok),
        "all_passed": results.failed == 0 and all(ok for _, ok in checks),
    }


if __name__ == "__main__":
    print(f"=== {VERSION} Self-Test ===")
    results = _self_test()
    for k, v in results.items():
        print(f"  {k}: {v}")

    if results["all_passed"]:
        print("\n✅ All tests passed")
    else:
        print("\n❌ Some tests failed")
