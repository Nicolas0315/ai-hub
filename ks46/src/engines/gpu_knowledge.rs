//! GPU Knowledge Engine (KS43) — CUDA/GPGPU architecture rules

use crate::GpuRecommendation;

// Architecture constants (from empirical benchmarks on ultra2025/nicolas2025)
const CC_BLACKWELL: f64 = 12.0;
const CC_AMPERE: f64 = 8.6;
const RTX5070TI_VRAM_GB: f64 = 16.0;
const RTX5070TI_BW_GB_S: f64 = 672.0;
const RTX3070_VRAM_GB: f64 = 8.0;
const RTX3070_BW_GB_S: f64 = 448.0;
const VRAM_OVERHEAD: f64 = 1.10;

pub struct GpuKnowledgeEngine;

impl GpuKnowledgeEngine {
    pub fn new() -> Self { Self }

    pub fn recommend_if_relevant(&self, claim: &str) -> Option<GpuRecommendation> {
        let lower = claim.to_lowercase();
        let gpu_keywords = ["gpu", "cuda", "rtx", "vram", "nvidia", "ollama",
            "tok/s", "推論", "inference", "gguf", "quantiz"];
        if !gpu_keywords.iter().any(|kw| lower.contains(kw)) {
            return None;
        }

        // Detect GPU type from claim
        let (gpu_name, vram, bw, cc) = if lower.contains("5070") || lower.contains("blackwell") {
            ("RTX 5070 Ti", RTX5070TI_VRAM_GB, RTX5070TI_BW_GB_S, CC_BLACKWELL)
        } else if lower.contains("3070") || lower.contains("ampere") {
            ("RTX 3070", RTX3070_VRAM_GB, RTX3070_BW_GB_S, CC_AMPERE)
        } else {
            ("Generic GPU", 16.0, 500.0, 10.0)
        };

        // Optimal model size: 80% of VRAM (Q4_K_M ≈ 0.58 bytes/param)
        let usable_vram = vram / VRAM_OVERHEAD;
        let optimal_params_b = usable_vram / 0.58;

        // Recommended context
        let ctx = if usable_vram > 12.0 { 8192 }
            else if usable_vram > 6.0 { 4096 }
            else { 2048 };

        // KV cache type: q8_0 only for CC >= 12.0 (Blackwell)
        let kv_cache = if cc >= CC_BLACKWELL { "q8_0" } else { "f16" };

        // Predicted tok/s (empirical: qwen3:8b Q4_K_M)
        let predicted_tok = (bw / 0.58 / 8.0 * 0.85).round();  // Rough estimate

        Some(GpuRecommendation {
            gpu_name: gpu_name.to_string(),
            vram_gb: vram,
            optimal_model_size_b: (optimal_params_b * 10.0).round() / 10.0,
            recommended_ctx: ctx,
            kv_cache_type: kv_cache.to_string(),
            flash_attention: true,  // Always recommended
            predicted_tok_s: predicted_tok,
        })
    }
}
