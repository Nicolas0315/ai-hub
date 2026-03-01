"""
Katala Studio — Shape Recognition Engine
3つの図形認識アプローチを統合

Approach 1: KS Shape Classification (メッシュ幾何学特徴 → 形状分類)
Approach 2: CLIP Visual Verification (レンダリング画像 × テキスト → 類似度)
Approach 3: Mesh Feature Analysis (頂点分布・法線統計・凸包比率)

Design: Youta Hilono (architecture)
Implementation: Shirokuma (OpenClaw AI)
"""
from __future__ import annotations

import numpy as np
import os
import json
import time
from dataclasses import dataclass, field
from typing import Optional

# ═══════════════════════════════════════════════════
# Data Types
# ═══════════════════════════════════════════════════

@dataclass
class ShapeFeatures:
    """メッシュから抽出された幾何学特徴量"""
    # Basic stats
    vertex_count: int = 0
    face_count: int = 0
    tri_count: int = 0

    # Bounding box
    bbox_min: np.ndarray = field(default_factory=lambda: np.zeros(3))
    bbox_max: np.ndarray = field(default_factory=lambda: np.zeros(3))
    bbox_size: np.ndarray = field(default_factory=lambda: np.zeros(3))
    bbox_aspect_ratio: np.ndarray = field(default_factory=lambda: np.ones(3))

    # Centroid & spread
    centroid: np.ndarray = field(default_factory=lambda: np.zeros(3))
    std_dev: np.ndarray = field(default_factory=lambda: np.zeros(3))
    max_extent: float = 0.0

    # Normal distribution
    normal_mean: np.ndarray = field(default_factory=lambda: np.zeros(3))
    normal_variance: float = 0.0
    normal_isotropy: float = 0.0  # 0=all same direction, 1=uniformly distributed

    # Convex hull
    convex_hull_volume: float = 0.0
    mesh_volume_estimate: float = 0.0
    convexity_ratio: float = 0.0  # mesh_vol / hull_vol (1.0 = fully convex)

    # Surface
    surface_area_estimate: float = 0.0
    compactness: float = 0.0  # 36π V² / A³ (sphere = 1.0)

    # Radial distribution (from centroid)
    radial_mean: float = 0.0
    radial_std: float = 0.0
    radial_skewness: float = 0.0

    # Symmetry
    symmetry_x: float = 0.0  # Mirror symmetry score (0-1)
    symmetry_y: float = 0.0
    symmetry_z: float = 0.0

    # Topology hints
    genus_estimate: int = 0  # 0=sphere-like, 1=torus-like, etc.
    is_closed: bool = False
    has_holes: bool = False

    def to_dict(self) -> dict:
        d = {}
        for k, v in self.__dict__.items():
            if isinstance(v, np.ndarray):
                d[k] = v.tolist()
            else:
                d[k] = v
        return d


@dataclass
class ShapeClassification:
    """形状分類結果"""
    predicted_shape: str  # "ring", "sphere", "humanoid", "diamond", etc.
    confidence: float  # 0-1
    all_scores: dict = field(default_factory=dict)  # shape → score
    method: str = ""  # "ks_geometric", "clip_visual", "mesh_features", "ensemble"
    features: Optional[ShapeFeatures] = None
    clip_similarity: Optional[dict] = None  # label → cos_sim


# ═══════════════════════════════════════════════════
# Known Shape Profiles (for geometric classification)
# ═══════════════════════════════════════════════════

SHAPE_PROFILES = {
    "sphere": {
        "normal_isotropy": (0.8, 1.0),
        "convexity_ratio": (0.85, 1.0),
        "compactness": (0.7, 1.0),
        "radial_std_ratio": (0.0, 0.15),  # radial_std / radial_mean
        "symmetry_min": 0.7,
        "bbox_aspect_max": 1.3,
    },
    "ring": {
        "normal_isotropy": (0.5, 0.9),
        "convexity_ratio": (0.1, 0.6),
        "compactness": (0.01, 0.3),
        "genus_estimate": 1,
        "has_holes": True,
        "bbox_aspect_min_one": 1.5,  # At least one axis much longer
    },
    "cylinder": {
        "normal_isotropy": (0.3, 0.7),
        "convexity_ratio": (0.6, 0.95),
        "compactness": (0.2, 0.6),
        "symmetry_min": 0.5,
        "bbox_one_axis_dominant": True,
    },
    "humanoid": {
        "normal_isotropy": (0.4, 1.0),
        "convexity_ratio": (0.05, 0.45),
        "compactness": (0.001, 0.15),
        "bbox_aspect_y_dominant": True,  # Tall
        "vertex_count_min": 200,
    },
    "diamond": {
        "normal_isotropy": (0.5, 0.9),
        "convexity_ratio": (0.5, 0.95),
        "compactness": (0.15, 0.5),
        "symmetry_min": 0.4,
        "radial_std_ratio": (0.1, 0.5),
    },
    "cube": {
        "normal_isotropy": (0.0, 0.5),
        "convexity_ratio": (0.85, 1.0),
        "compactness": (0.4, 0.65),
        "symmetry_min": 0.8,
        "bbox_aspect_max": 1.2,
    },
    "plane": {
        "normal_isotropy": (0.0, 0.2),
        "convexity_ratio": (0.0, 0.3),
        "compactness": (0.0, 0.05),
        "bbox_one_axis_flat": True,
    },
    "clover": {
        "normal_isotropy": (0.3, 0.7),
        "convexity_ratio": (0.1, 0.5),
        "compactness": (0.01, 0.2),
        "symmetry_min": 0.3,
    },
}


# ═══════════════════════════════════════════════════
# Approach 1: KS Geometric Shape Classification
# ═══════════════════════════════════════════════════

def extract_features(positions: np.ndarray, normals: np.ndarray,
                     faces: list[list[int]]) -> ShapeFeatures:
    """メッシュからShapeFeaturesを抽出"""
    feat = ShapeFeatures()

    if len(positions) == 0:
        return feat

    feat.vertex_count = len(positions)
    feat.face_count = len(faces)
    feat.tri_count = sum(max(0, len(f) - 2) for f in faces)

    # Bounding box
    feat.bbox_min = positions.min(axis=0)
    feat.bbox_max = positions.max(axis=0)
    feat.bbox_size = feat.bbox_max - feat.bbox_min
    max_dim = feat.bbox_size.max()
    if max_dim > 0:
        feat.bbox_aspect_ratio = feat.bbox_size / max_dim
    feat.max_extent = float(max_dim)

    # Centroid & spread
    feat.centroid = positions.mean(axis=0)
    feat.std_dev = positions.std(axis=0)

    # Normal distribution
    if len(normals) > 0:
        feat.normal_mean = normals.mean(axis=0)
        # Isotropy: how uniformly are normals distributed?
        # If all point the same way → low isotropy
        # If uniformly distributed → high isotropy
        norm_lengths = np.linalg.norm(normals, axis=1)
        valid = norm_lengths > 1e-8
        if valid.sum() > 0:
            unit_normals = normals[valid] / norm_lengths[valid, np.newaxis]
            mean_normal = unit_normals.mean(axis=0)
            mean_length = np.linalg.norm(mean_normal)
            feat.normal_isotropy = float(1.0 - mean_length)
            feat.normal_variance = float(unit_normals.var())

    # Radial distribution
    radii = np.linalg.norm(positions - feat.centroid, axis=1)
    feat.radial_mean = float(radii.mean())
    feat.radial_std = float(radii.std())
    if feat.radial_mean > 0:
        mu3 = ((radii - feat.radial_mean) ** 3).mean()
        feat.radial_skewness = float(mu3 / (feat.radial_std ** 3)) if feat.radial_std > 1e-8 else 0.0

    # Convex hull
    try:
        from scipy.spatial import ConvexHull
        if len(positions) >= 4:
            hull = ConvexHull(positions)
            feat.convex_hull_volume = float(hull.volume)
            feat.surface_area_estimate = float(hull.area)
    except Exception:
        pass

    # Mesh volume estimate (sum of signed tetrahedra from origin)
    vol = 0.0
    for face in faces:
        if len(face) >= 3:
            v0 = positions[face[0]]
            for i in range(1, len(face) - 1):
                v1 = positions[face[i]]
                v2 = positions[face[i + 1]]
                vol += np.dot(v0, np.cross(v1, v2)) / 6.0
    feat.mesh_volume_estimate = abs(float(vol))

    if feat.convex_hull_volume > 0:
        feat.convexity_ratio = min(1.0, feat.mesh_volume_estimate / feat.convex_hull_volume)

    # Compactness: 36π V² / A³
    if feat.surface_area_estimate > 0:
        feat.compactness = float(
            36 * np.pi * feat.mesh_volume_estimate ** 2 / feat.surface_area_estimate ** 3
        )

    # Symmetry (mirror symmetry score per axis)
    for axis_idx, axis_name in enumerate(['x', 'y', 'z']):
        mirrored = positions.copy()
        mirrored[:, axis_idx] = -mirrored[:, axis_idx]
        # For each mirrored point, find nearest original point
        from scipy.spatial import cKDTree
        tree = cKDTree(positions)
        dists, _ = tree.query(mirrored)
        max_dist = feat.max_extent if feat.max_extent > 0 else 1.0
        sym_score = float(1.0 - np.clip(dists.mean() / (max_dist * 0.1), 0, 1))
        setattr(feat, f'symmetry_{axis_name}', sym_score)

    # Genus estimate (Euler: V - E + F = 2 - 2g for closed meshes)
    # Approximate edges from faces
    edges = set()
    for face in faces:
        for i in range(len(face)):
            e = tuple(sorted([face[i], face[(i + 1) % len(face)]]))
            edges.add(e)
    E = len(edges)
    V = feat.vertex_count
    F = feat.face_count
    chi = V - E + F  # Euler characteristic
    feat.genus_estimate = max(0, (2 - chi) // 2)
    feat.has_holes = feat.genus_estimate > 0
    feat.is_closed = chi == 2

    return feat


def classify_by_geometry(features: ShapeFeatures) -> ShapeClassification:
    """Approach 1: 幾何学特徴量から形状を分類"""
    scores = {}

    for shape_name, profile in SHAPE_PROFILES.items():
        score = 1.0

        # Normal isotropy
        if "normal_isotropy" in profile:
            lo, hi = profile["normal_isotropy"]
            if lo <= features.normal_isotropy <= hi:
                score *= 1.0
            else:
                dist = min(abs(features.normal_isotropy - lo), abs(features.normal_isotropy - hi))
                score *= max(0, 1.0 - dist * 2)

        # Convexity ratio
        if "convexity_ratio" in profile:
            lo, hi = profile["convexity_ratio"]
            if lo <= features.convexity_ratio <= hi:
                score *= 1.0
            else:
                dist = min(abs(features.convexity_ratio - lo), abs(features.convexity_ratio - hi))
                score *= max(0, 1.0 - dist * 2)

        # Compactness
        if "compactness" in profile:
            lo, hi = profile["compactness"]
            if lo <= features.compactness <= hi:
                score *= 1.0
            else:
                dist = min(abs(features.compactness - lo), abs(features.compactness - hi))
                score *= max(0, 1.0 - dist * 3)

        # Genus
        if "genus_estimate" in profile:
            if features.genus_estimate == profile["genus_estimate"]:
                score *= 1.2  # Bonus
            else:
                score *= 0.5

        # Has holes
        if "has_holes" in profile:
            if features.has_holes == profile["has_holes"]:
                score *= 1.1
            else:
                score *= 0.6

        # Symmetry minimum
        if "symmetry_min" in profile:
            avg_sym = (features.symmetry_x + features.symmetry_y + features.symmetry_z) / 3
            if avg_sym >= profile["symmetry_min"]:
                score *= 1.0
            else:
                score *= max(0.3, avg_sym / profile["symmetry_min"])

        # BBox aspect ratio checks
        if "bbox_aspect_max" in profile:
            max_ratio = features.bbox_aspect_ratio.max() / max(features.bbox_aspect_ratio.min(), 1e-8)
            if max_ratio <= profile["bbox_aspect_max"]:
                score *= 1.0
            else:
                score *= max(0.3, 1.0 - (max_ratio - profile["bbox_aspect_max"]) * 0.5)

        # Y-dominant (humanoid)
        if profile.get("bbox_aspect_y_dominant"):
            sorted_dims = np.sort(features.bbox_size)[::-1]
            if len(sorted_dims) >= 2 and sorted_dims[1] > 0:
                y_idx = np.argmax(features.bbox_size)
                y_ratio = features.bbox_size[1] / sorted_dims[1] if sorted_dims[1] > 0 else 0
                if y_idx == 1 and y_ratio > 3.0:
                    score *= 1.8  # Strong boost for tall objects
                elif y_idx == 1 and y_ratio > 2.0:
                    score *= 1.4
                elif y_idx == 1 and y_ratio > 1.5:
                    score *= 1.1
                else:
                    score *= 0.4

        # Vertex count minimum
        if "vertex_count_min" in profile:
            if features.vertex_count >= profile["vertex_count_min"]:
                score *= 1.0
            else:
                score *= 0.4

        # Radial std ratio
        if "radial_std_ratio" in profile and features.radial_mean > 0:
            ratio = features.radial_std / features.radial_mean
            lo, hi = profile["radial_std_ratio"]
            if lo <= ratio <= hi:
                score *= 1.0
            else:
                dist = min(abs(ratio - lo), abs(ratio - hi))
                score *= max(0.2, 1.0 - dist * 3)

        scores[shape_name] = min(1.0, max(0.0, score))

    # Normalize
    total = sum(scores.values())
    if total > 0:
        scores = {k: v / total for k, v in scores.items()}

    best = max(scores, key=scores.get) if scores else "unknown"

    return ShapeClassification(
        predicted_shape=best,
        confidence=scores.get(best, 0.0),
        all_scores=scores,
        method="ks_geometric",
        features=features,
    )


# ═══════════════════════════════════════════════════
# Approach 2: CLIP Visual Verification
# ═══════════════════════════════════════════════════

_clip_model = None
_clip_preprocess = None
_clip_tokenizer = None


def _load_clip():
    """Lazy-load CLIP model"""
    global _clip_model, _clip_preprocess, _clip_tokenizer
    if _clip_model is not None:
        return

    import open_clip
    import torch

    model, _, preprocess = open_clip.create_model_and_transforms(
        'ViT-B-32', pretrained='laion2b_s34b_b79k'
    )
    tokenizer = open_clip.get_tokenizer('ViT-B-32')

    model.eval()
    _clip_model = model
    _clip_preprocess = preprocess
    _clip_tokenizer = tokenizer


def classify_by_clip(image_path: str,
                     candidate_labels: list[str] | None = None) -> ShapeClassification:
    """Approach 2: CLIP画像-テキスト類似度による形状分類"""
    import torch
    from PIL import Image

    _load_clip()

    if candidate_labels is None:
        candidate_labels = [
            "a 3D ring", "a 3D sphere", "a 3D cube",
            "a 3D diamond gemstone", "a 3D humanoid figure",
            "a 3D cylinder", "a four-leaf clover",
            "a 3D torus", "a 3D plane surface",
            "a 3D abstract sculpture",
        ]

    # Label → shape name mapping
    label_to_shape = {
        "a 3D ring": "ring", "a 3D sphere": "sphere",
        "a 3D cube": "cube", "a 3D diamond gemstone": "diamond",
        "a 3D humanoid figure": "humanoid", "a 3D cylinder": "cylinder",
        "a four-leaf clover": "clover", "a 3D torus": "ring",
        "a 3D plane surface": "plane", "a 3D abstract sculpture": "sculpture",
    }

    image = Image.open(image_path).convert("RGB")
    image_input = _clip_preprocess(image).unsqueeze(0)

    text_tokens = _clip_tokenizer(candidate_labels)

    with torch.no_grad():
        image_features = _clip_model.encode_image(image_input)
        text_features = _clip_model.encode_text(text_tokens)

        image_features /= image_features.norm(dim=-1, keepdim=True)
        text_features /= text_features.norm(dim=-1, keepdim=True)

        similarities = (image_features @ text_features.T).squeeze(0)
        probs = similarities.softmax(dim=-1)

    clip_scores = {}
    shape_scores = {}
    for label, sim, prob in zip(candidate_labels, similarities.tolist(), probs.tolist()):
        clip_scores[label] = {"similarity": round(sim, 4), "probability": round(prob, 4)}
        shape = label_to_shape.get(label, label)
        shape_scores[shape] = max(shape_scores.get(shape, 0), prob)

    best_label = candidate_labels[probs.argmax().item()]
    best_shape = label_to_shape.get(best_label, best_label)

    return ShapeClassification(
        predicted_shape=best_shape,
        confidence=float(probs.max().item()),
        all_scores=shape_scores,
        method="clip_visual",
        clip_similarity=clip_scores,
    )


# ═══════════════════════════════════════════════════
# Approach 3: Mesh Feature Analysis
# ═══════════════════════════════════════════════════

def analyze_mesh_features(features: ShapeFeatures) -> dict:
    """Approach 3: 詳細なメッシュ特徴量レポート"""
    report = {
        "topology": {
            "vertices": features.vertex_count,
            "faces": features.face_count,
            "triangles": features.tri_count,
            "genus": features.genus_estimate,
            "is_closed": features.is_closed,
            "has_holes": features.has_holes,
            "euler_characteristic": (
                features.vertex_count -
                # approximate edges
                int(features.face_count * 1.5) +
                features.face_count
            ),
        },
        "dimensions": {
            "bbox_size": features.bbox_size.tolist(),
            "max_extent": features.max_extent,
            "aspect_ratio": features.bbox_aspect_ratio.tolist(),
            "centroid": features.centroid.tolist(),
        },
        "distribution": {
            "std_dev": features.std_dev.tolist(),
            "radial_mean": features.radial_mean,
            "radial_std": features.radial_std,
            "radial_coefficient_of_variation": (
                features.radial_std / features.radial_mean
                if features.radial_mean > 0 else 0
            ),
            "radial_skewness": features.radial_skewness,
        },
        "surface": {
            "normal_isotropy": features.normal_isotropy,
            "normal_variance": features.normal_variance,
            "convexity_ratio": features.convexity_ratio,
            "compactness": features.compactness,
            "surface_area": features.surface_area_estimate,
            "volume": features.mesh_volume_estimate,
        },
        "symmetry": {
            "x_mirror": features.symmetry_x,
            "y_mirror": features.symmetry_y,
            "z_mirror": features.symmetry_z,
            "average": (features.symmetry_x + features.symmetry_y + features.symmetry_z) / 3,
        },
        "shape_indicators": {},
    }

    # Derive shape indicators
    indicators = report["shape_indicators"]

    # Sphericity
    if features.radial_mean > 0:
        indicators["sphericity"] = round(1.0 - features.radial_std / features.radial_mean, 3)

    # Elongation
    sorted_dims = np.sort(features.bbox_size)[::-1]
    if sorted_dims[-1] > 0:
        indicators["elongation"] = round(float(sorted_dims[0] / sorted_dims[-1]), 3)
    if len(sorted_dims) >= 2 and sorted_dims[1] > 0:
        indicators["flatness"] = round(float(sorted_dims[-1] / sorted_dims[1]), 3)

    # Complexity
    if features.vertex_count > 0:
        indicators["face_vertex_ratio"] = round(features.face_count / features.vertex_count, 3)

    return report


# ═══════════════════════════════════════════════════
# Ensemble: All 3 Approaches Combined
# ═══════════════════════════════════════════════════

def classify_shape(positions: np.ndarray, normals: np.ndarray,
                   faces: list[list[int]],
                   rendered_image_path: str | None = None,
                   clip_labels: list[str] | None = None) -> dict:
    """
    3つのアプローチを統合した形状認識

    Returns dict with:
      - geometric: Approach 1 result
      - clip: Approach 2 result (if image provided)
      - features: Approach 3 detailed analysis
      - ensemble: Combined prediction
    """
    t0 = time.time()
    result = {}

    # Approach 3: Extract features (needed for 1 and 3)
    features = extract_features(positions, normals, faces)
    result["features"] = analyze_mesh_features(features)

    # Approach 1: Geometric classification
    geo_class = classify_by_geometry(features)
    result["geometric"] = {
        "predicted": geo_class.predicted_shape,
        "confidence": round(geo_class.confidence, 4),
        "scores": {k: round(v, 4) for k, v in geo_class.all_scores.items()},
    }

    # Approach 2: CLIP (if image available)
    clip_class = None
    if rendered_image_path and os.path.exists(rendered_image_path):
        try:
            clip_class = classify_by_clip(rendered_image_path, clip_labels)
            result["clip"] = {
                "predicted": clip_class.predicted_shape,
                "confidence": round(clip_class.confidence, 4),
                "scores": {k: round(v, 4) for k, v in clip_class.all_scores.items()},
                "similarities": clip_class.clip_similarity,
            }
        except Exception as e:
            result["clip"] = {"error": str(e)}

    # Ensemble
    shape_votes: dict[str, float] = {}

    # Weight: geometric 0.3, clip 0.5, features-derived 0.2
    for shape, score in geo_class.all_scores.items():
        shape_votes[shape] = shape_votes.get(shape, 0) + score * 0.3

    if clip_class:
        for shape, score in clip_class.all_scores.items():
            shape_votes[shape] = shape_votes.get(shape, 0) + score * 0.5

    # Features-derived boost
    fi = result["features"]["shape_indicators"]
    if fi.get("sphericity", 0) > 0.85 and features.convexity_ratio > 0.8:
        shape_votes["sphere"] = shape_votes.get("sphere", 0) + 0.15
    if features.genus_estimate >= 1 and features.compactness < 0.02:
        # Only boost ring if it's actually toroidal (low compactness)
        shape_votes["ring"] = shape_votes.get("ring", 0) + 0.1
    # Humanoid: tall + low convexity + multiple disconnected parts
    bbox_y = features.bbox_size[1] if len(features.bbox_size) > 1 else 0
    bbox_x = features.bbox_size[0] if len(features.bbox_size) > 0 else 1
    y_elongation = bbox_y / bbox_x if bbox_x > 0 else 1
    if y_elongation > 2.5 and features.convexity_ratio < 0.5:
        shape_votes["humanoid"] = shape_votes.get("humanoid", 0) + 0.2
    elif fi.get("elongation", 1) > 3.0 and features.vertex_count > 200:
        shape_votes["humanoid"] = shape_votes.get("humanoid", 0) + 0.15

    # Normalize
    total = sum(shape_votes.values())
    if total > 0:
        shape_votes = {k: v / total for k, v in shape_votes.items()}

    best_ensemble = max(shape_votes, key=shape_votes.get) if shape_votes else "unknown"

    result["ensemble"] = {
        "predicted": best_ensemble,
        "confidence": round(shape_votes.get(best_ensemble, 0), 4),
        "scores": {k: round(v, 4) for k, v in sorted(shape_votes.items(), key=lambda x: -x[1])},
        "methods_used": ["ks_geometric", "mesh_features"] + (["clip_visual"] if clip_class else []),
    }

    result["elapsed_sec"] = round(time.time() - t0, 3)

    return result


# ═══════════════════════════════════════════════════
# Mesh Adapter (for Katala Studio Mesh objects)
# ═══════════════════════════════════════════════════

def classify_mesh(mesh, rendered_image_path: str | None = None,
                  clip_labels: list[str] | None = None) -> dict:
    """Katala Studio Meshオブジェクトから直接分類"""
    positions = mesh.get_positions_array()
    normals = mesh.get_normals_array()
    faces = [f.indices for f in mesh.faces]

    result = classify_shape(positions, normals, faces, rendered_image_path, clip_labels)

    # Store KS verification
    ensemble = result.get("ensemble", {})
    mesh.ks_verify_operation(
        f"shape_recognition:{ensemble.get('predicted', 'unknown')}",
        ensemble.get("confidence", 0.0),
        0.95,
        0.05,
    )

    return result
