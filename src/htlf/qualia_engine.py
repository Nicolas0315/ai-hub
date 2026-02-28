"""Behavioral measurement engine for HTLF R_qualia.

Implements three modes:
- online: no human participants, baseline-regularized approximation
- behavioral: participant response vectors
- physio: physiological proxy vectors (GSR/HRV/etc.)
"""

from __future__ import annotations

import math
import re
import statistics
from dataclasses import dataclass
from typing import Any, Literal

from .qualia_baselines import EMOTION_MECHANISM_WEIGHTS, merged_baseline_space

DistanceMetric = Literal["cosine", "mahalanobis", "wasserstein"]


@dataclass(slots=True)
class QualiaComputation:
    score: float
    backend: str
    mode: str
    raw_distance: float


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _safe_mean(values: list[float], default: float = 0.0) -> float:
    return statistics.fmean(values) if values else default


def _normalize_l2(vec: list[float]) -> list[float]:
    if not vec:
        return []
    norm = math.sqrt(sum(v * v for v in vec))
    if norm <= 1e-12:
        return [0.0 for _ in vec]
    return [v / norm for v in vec]


def _cosine_distance(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 1.0
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 1e-12 or nb <= 1e-12:
        return 1.0
    cos = sum(x * y for x, y in zip(a, b)) / (na * nb)
    cos = max(-1.0, min(1.0, cos))
    return (1.0 - cos) / 2.0


def _diag_mahalanobis(a: list[float], b: list[float], variances: list[float] | None = None) -> float:
    if not a or not b or len(a) != len(b):
        return 1.0
    if variances is None or len(variances) != len(a):
        variances = [max(1e-6, ((abs(x) + abs(y)) / 2.0) ** 2 + 1e-3) for x, y in zip(a, b)]
    s = 0.0
    for i, (x, y) in enumerate(zip(a, b)):
        v = max(1e-6, variances[i])
        d = x - y
        s += (d * d) / v
    return min(1.0, math.sqrt(s) / math.sqrt(len(a)))


def _wasserstein_approx(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 1.0
    sa = sorted(a)
    sb = sorted(b)
    dist = _safe_mean([abs(x - y) for x, y in zip(sa, sb)], default=1.0)
    return min(1.0, dist)


def _compute_distance(a: list[float], b: list[float], metric: DistanceMetric) -> float:
    if metric == "mahalanobis":
        return _diag_mahalanobis(a, b)
    if metric == "wasserstein":
        return _wasserstein_approx(a, b)
    return _cosine_distance(a, b)


class BehavioralExperiment:
    """Compute R_qualia from participant behavioral response vectors."""

    def __init__(self, distance: DistanceMetric = "cosine") -> None:
        self.distance = distance

    def compute_response_vector(
        self,
        choices: list[str] | dict[str, int],
        reaction_times: list[float],
        valence_arousal: list[float] | tuple[float, float],
    ) -> list[float]:
        """選択分布 + RT統計 + V-A評定 → 正規化ベクトル B(x)"""
        if isinstance(choices, dict):
            total = max(1, sum(max(0, int(v)) for v in choices.values()))
            choice_feats = [max(0.0, float(v)) / total for _, v in sorted(choices.items())]
        else:
            counts: dict[str, int] = {}
            for c in choices:
                counts[c] = counts.get(c, 0) + 1
            total = max(1, len(choices))
            choice_feats = [v / total for _, v in sorted(counts.items())]

        rts = [max(1e-3, float(x)) for x in reaction_times if isinstance(x, (int, float))]
        rt_mean = _safe_mean(rts, default=1.0)
        rt_std = statistics.pstdev(rts) if len(rts) >= 2 else 0.0
        rt_inv = 1.0 / (1.0 + rt_mean)
        rt_cv = rt_std / max(1e-6, rt_mean)

        if isinstance(valence_arousal, tuple):
            valence, arousal = float(valence_arousal[0]), float(valence_arousal[1])
        else:
            vals = [float(v) for v in valence_arousal]
            valence = vals[0] if vals else 0.5
            arousal = vals[1] if len(vals) > 1 else 0.5

        base = choice_feats + [_clamp01(rt_inv), _clamp01(rt_cv), _clamp01(valence), _clamp01(arousal)]
        return _normalize_l2(base)

    def compute_qualia_loss(self, b_source: list[float], b_target: list[float], lambda_: float = 1.0) -> tuple[float, float]:
        """ΔB = D(B_source, B_target), R_qualia = exp(-λ·ΔB)"""
        delta_b = _compute_distance(b_source, b_target, metric=self.distance)
        r_qualia = math.exp(-max(0.0, lambda_) * max(0.0, delta_b))
        return delta_b, _clamp01(r_qualia)

    def adjust_for_context(self, r_qualia_raw: float, r_context: float) -> float:
        """R_qualia_adj = R_qualia_raw * (0.5 + 0.5 * R_context)"""
        return _clamp01(r_qualia_raw * (0.5 + 0.5 * _clamp01(r_context)))


class PhysiologicalProxy:
    """Build behavioral proxy vectors from physiological signals."""

    def parse_gsr_features(self, gsr_signal: list[float]) -> list[float]:
        """GSR → [peak_count, mean_amplitude, latency, recovery_time]"""
        if not gsr_signal:
            return [0.0, 0.0, 1.0, 1.0]
        sig = [float(x) for x in gsr_signal]
        mean = _safe_mean(sig)
        threshold = mean + (statistics.pstdev(sig) if len(sig) >= 2 else 0.0)
        peaks = [i for i, x in enumerate(sig) if x > threshold]
        peak_count = len(peaks) / max(1, len(sig))
        amp = _safe_mean([max(0.0, x - mean) for x in sig])
        latency = (peaks[0] / max(1, len(sig))) if peaks else 1.0
        recovery_time = ((len(sig) - peaks[-1]) / max(1, len(sig))) if peaks else 1.0
        return [_clamp01(peak_count), _clamp01(amp), _clamp01(latency), _clamp01(recovery_time)]

    def parse_hrv_features(self, rr_intervals: list[float]) -> list[float]:
        """RR intervals → [RMSSD, LF/HF ratio, mean_HR]"""
        if not rr_intervals:
            return [0.0, 0.5, 0.5]
        rr = [max(1e-3, float(x)) for x in rr_intervals]
        diffs = [rr[i + 1] - rr[i] for i in range(len(rr) - 1)]
        rmssd = math.sqrt(_safe_mean([d * d for d in diffs], default=0.0))

        low = [d for d in diffs if abs(d) < 0.08]
        high = [d for d in diffs if abs(d) >= 0.08]
        lf_hf = (len(low) + 1e-6) / (len(high) + 1e-6)

        mean_rr = _safe_mean(rr, default=1.0)
        mean_hr = 60.0 / max(1e-3, mean_rr)

        rmssd_n = min(1.0, rmssd / 0.2)
        lf_hf_n = min(1.0, lf_hf / 3.0)
        hr_n = min(1.0, mean_hr / 180.0)
        return [_clamp01(rmssd_n), _clamp01(lf_hf_n), _clamp01(hr_n)]

    def build_physio_vector(
        self,
        gsr_features: list[float],
        hrv_features: list[float],
        additional: list[float] | None = None,
    ) -> list[float]:
        """生理特徴量 → 正規化ベクトル"""
        vec = [float(v) for v in gsr_features + hrv_features]
        if additional:
            vec.extend(float(v) for v in additional)
        return _normalize_l2([_clamp01(v) for v in vec])


class OnlineApproximation:
    """Baseline-regularized approximation without participant data."""

    def __init__(self, distance: DistanceMetric = "cosine") -> None:
        self.distance = distance
        self._baselines = self.load_baseline_distributions()

    def load_baseline_distributions(self) -> dict[str, dict[str, tuple[float, float]]]:
        return merged_baseline_space()

    def _infer_baseline_key(self, text: str) -> str:
        t = text.lower()
        if re.search(r"\b(major|bright|happy)\b", t) and re.search(r"\b(fast|tempo|rapid)\b", t):
            return "major_fast"
        if re.search(r"\b(minor|sad|dark)\b", t) and re.search(r"\b(slow|calm|adagio)\b", t):
            return "minor_slow"
        if re.search(r"\b(disson|harsh|rough|tense)\b", t):
            return "dissonant"
        if re.search(r"\b(warm|red|orange|gold)\b", t) and re.search(r"\b(contrast|sharp|high)\b", t):
            return "warm_high_contrast"
        if re.search(r"\b(cool|blue|green)\b", t) and re.search(r"\b(low contrast|soft|mist|faint)\b", t):
            return "cool_low_contrast"
        return "rothko_color_field"

    def _text_affect_features(self, text: str) -> tuple[float, float]:
        t = text.lower()
        positive = len(re.findall(r"\b(joy|happy|warm|beautiful|pleasant|resolution|hope)\b", t))
        negative = len(re.findall(r"\b(sad|dark|fear|tense|dissonant|angry|anxious)\b", t))
        energetic = len(re.findall(r"\b(fast|rapid|explosive|intense|crescendo|staccato)\b", t))
        calm = len(re.findall(r"\b(slow|calm|quiet|gentle|legato|soft)\b", t))

        valence = 0.5 + 0.1 * (positive - negative)
        arousal = 0.5 + 0.1 * (energetic - calm)
        return _clamp01(valence), _clamp01(arousal)

    def simulate_forced_choice(self, source_text: str, target_text: str, n_virtual: int = 5) -> list[dict[str, float | int | str]]:
        """Temperature-diverse virtual respondents for forced-choice style preference."""
        temperatures = [0.0, 0.3, 0.6, 0.9, 1.2][: max(1, n_virtual)]

        src_v, src_a = self._text_affect_features(source_text)
        tgt_v, tgt_a = self._text_affect_features(target_text)
        src_key = self._infer_baseline_key(source_text)
        tgt_key = self._infer_baseline_key(target_text)

        responses: list[dict[str, float | int | str]] = []
        for idx, temp in enumerate(temperatures):
            noise = (idx - (len(temperatures) - 1) / 2.0) * 0.02 * (1.0 + temp)
            src_score = 0.6 * src_v + 0.4 * src_a + noise
            tgt_score = 0.6 * tgt_v + 0.4 * tgt_a - noise
            choice = "target" if tgt_score >= src_score else "source"
            confidence = abs(tgt_score - src_score)
            responses.append(
                {
                    "choice": choice,
                    "temperature": temp,
                    "confidence": _clamp01(confidence),
                    "source_valence": src_v,
                    "source_arousal": src_a,
                    "target_valence": tgt_v,
                    "target_arousal": tgt_a,
                    "source_key": src_key,
                    "target_key": tgt_key,
                }
            )
        return responses

    def regularize_with_baseline(
        self,
        llm_responses: list[dict[str, float | int | str]],
        baseline_dist: dict[str, tuple[float, float]],
    ) -> tuple[float, float]:
        """Regularize virtual responses with baseline stats to suppress model bias."""
        if not llm_responses:
            return baseline_dist["valence"][0], baseline_dist["arousal"][0]

        valences = [float(r.get("target_valence", 0.5)) for r in llm_responses]
        arousals = [float(r.get("target_arousal", 0.5)) for r in llm_responses]
        llm_v = _safe_mean(valences, default=0.5)
        llm_a = _safe_mean(arousals, default=0.5)

        b_v, b_v_std = baseline_dist["valence"]
        b_a, b_a_std = baseline_dist["arousal"]

        # Weight by mechanism confidence + baseline uncertainty (lower std => stronger pull).
        mech_weight = sum(EMOTION_MECHANISM_WEIGHTS.values()) / max(1.0, len(EMOTION_MECHANISM_WEIGHTS))
        w_v = _clamp01(mech_weight * (1.0 / (1.0 + b_v_std * 3.0)))
        w_a = _clamp01(mech_weight * (1.0 / (1.0 + b_a_std * 3.0)))

        reg_v = (1.0 - w_v) * llm_v + w_v * b_v
        reg_a = (1.0 - w_a) * llm_a + w_a * b_a
        return _clamp01(reg_v), _clamp01(reg_a)

    def compute_online_qualia(self, source: str, target: str, r_context: float) -> tuple[float, float]:
        """LLM-like forced-choice + baseline regularization + context conditioning."""
        responses = self.simulate_forced_choice(source, target, n_virtual=5)

        src_key = self._infer_baseline_key(source)
        tgt_key = self._infer_baseline_key(target)
        src_base = self._baselines.get(src_key, self._baselines["rothko_color_field"])
        tgt_base = self._baselines.get(tgt_key, self._baselines["rothko_color_field"])

        src_v, src_a = self.regularize_with_baseline(responses, src_base)
        tgt_v, tgt_a = self.regularize_with_baseline(responses, tgt_base)

        b_src = _normalize_l2([src_v, src_a])
        b_tgt = _normalize_l2([tgt_v, tgt_a])
        delta = _compute_distance(b_src, b_tgt, self.distance)

        raw = math.exp(-delta)
        adjusted = _clamp01(raw * (0.5 + 0.5 * _clamp01(r_context)))
        return delta, adjusted


def compute_qualia(
    source_text: str,
    target_text: str,
    r_context: float,
    *,
    mode: Literal["online", "behavioral", "physio"] = "online",
    responses_data: dict[str, Any] | None = None,
    physio_data: dict[str, Any] | None = None,
    distance: DistanceMetric = "cosine",
) -> QualiaComputation:
    """Mode-dispatched R_qualia computation entrypoint."""
    if mode == "behavioral" and responses_data:
        be = BehavioralExperiment(distance=distance)
        src = responses_data.get("source", {})
        tgt = responses_data.get("target", {})
        b_src = be.compute_response_vector(
            choices=src.get("choices", []),
            reaction_times=src.get("reaction_times", []),
            valence_arousal=src.get("valence_arousal", [0.5, 0.5]),
        )
        b_tgt = be.compute_response_vector(
            choices=tgt.get("choices", []),
            reaction_times=tgt.get("reaction_times", []),
            valence_arousal=tgt.get("valence_arousal", [0.5, 0.5]),
        )
        delta, raw = be.compute_qualia_loss(b_src, b_tgt)
        adj = be.adjust_for_context(raw, r_context)
        return QualiaComputation(score=adj, backend="behavioral_experiment", mode="behavioral", raw_distance=delta)

    if mode == "physio" and physio_data:
        pp = PhysiologicalProxy()
        be = BehavioralExperiment(distance=distance)

        src = physio_data.get("source", {})
        tgt = physio_data.get("target", {})

        src_vec = pp.build_physio_vector(
            pp.parse_gsr_features(src.get("gsr", [])),
            pp.parse_hrv_features(src.get("rr_intervals", [])),
            additional=src.get("additional", []),
        )
        tgt_vec = pp.build_physio_vector(
            pp.parse_gsr_features(tgt.get("gsr", [])),
            pp.parse_hrv_features(tgt.get("rr_intervals", [])),
            additional=tgt.get("additional", []),
        )

        delta, raw = be.compute_qualia_loss(src_vec, tgt_vec)
        adj = be.adjust_for_context(raw, r_context)
        return QualiaComputation(score=adj, backend="physiological_proxy", mode="physio", raw_distance=delta)

    oa = OnlineApproximation(distance=distance)
    delta, score = oa.compute_online_qualia(source_text, target_text, r_context)
    return QualiaComputation(score=score, backend="online_approximation", mode="online", raw_distance=delta)
