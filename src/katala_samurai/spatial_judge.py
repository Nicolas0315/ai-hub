"""
Spatial Judge — 判断階層アーキテクチャの3D空間認知への応用.

Youta: "判断階層を導入したときのこと、3D空間認知に応用できない？考えて創造せよ。"

設計の系譜:
  ModalityJudge (マルチモーダル入力の判断階層)
    ⓪入力層: 各モダリティを統一表現に変換
    判断層:  クロスモーダル矛盾検出 + ルーティング + 信頼度調整

  → SpatialJudge (3D空間認知の判断階層)
    ⓪知覚層: 多元的3D入力を統一空間表現に変換
      - メッシュ → SpatialRepresentation
      - 点群 → SpatialRepresentation
      - テキスト記述 → SpatialRepresentation
      - 2D画像(深度推定) → SpatialRepresentation
    判断層:  空間的矛盾検出 + 構造推論 + 意味付け
      - 物理的矛盾: 貫通、浮遊、スケール異常
      - トポロジー判断: 接続性、内外、開閉
      - 意味的判断: 「椅子」は座面+脚+背、「テーブル」は天板+脚
      - 階層的分解: 全体→パーツ→ディテール

Youtaの認知モデルとの対応:
  言語入力 → 非言語的ヴェン図ネットワーク → 言語出力
  テキスト記述 → 3D空間構造(SpatialRepresentation) → メッシュ/記述出力
  ↑ これがまさに3Dモデリングの認知過程

CrossModalSolverEngineの横断接続と同構造:
  異なる入力モダリティが同じ空間表現に収束すべき
  → 不一致があれば矛盾 = 検証対象
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from katala_samurai.spatial_cognition import (
    Vec3, Quaternion, Transform, AABB, BoundingSphere,
    Ray, Mesh, Camera, SceneNode, SpatialReasoner,
)

VERSION = "1.0.0"


# ═══════════════════════════════════════════════════════════════
# ⓪ 知覚層 — 多元的入力を統一空間表現に変換
# ═══════════════════════════════════════════════════════════════

class SpatialModality(Enum):
    """Input modality types for spatial data."""
    MESH = "mesh"
    POINT_CLOUD = "point_cloud"
    TEXT_DESC = "text_description"
    DEPTH_MAP = "depth_map"
    VOXEL = "voxel"
    SDF = "signed_distance_field"
    SKELETON = "skeleton"


@dataclass
class SpatialFeature:
    """A spatial feature extracted from any modality."""
    name: str
    category: str  # 'geometric', 'topological', 'semantic', 'relational'
    value: Any
    confidence: float = 1.0
    source_modality: Optional[SpatialModality] = None


@dataclass
class SpatialRepresentation:
    """Unified spatial representation — the 'ヴェン図ネットワーク' of 3D space.

    This is the non-verbal spatial structure that all modalities converge into.
    Analogous to Youta's internal representation model.
    """
    # Geometric properties
    bounding_box: Optional[AABB] = None
    center: Optional[Vec3] = None
    extent: Optional[Vec3] = None  # size in each axis
    volume_estimate: float = 0.0
    surface_area: float = 0.0

    # Topological properties
    is_closed: bool = False
    is_manifold: bool = False
    euler_characteristic: int = 0
    genus: int = 0  # number of holes
    connected_components: int = 1

    # Structural decomposition
    parts: List['SpatialPart'] = field(default_factory=list)
    symmetry: Optional[Dict[str, Any]] = None

    # Semantic properties
    semantic_label: str = ""
    semantic_features: List[SpatialFeature] = field(default_factory=list)

    # Relational properties (relative to other objects)
    relations: List[Dict[str, Any]] = field(default_factory=list)

    # Source tracking
    source_modalities: List[SpatialModality] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class SpatialPart:
    """A structural part of a spatial object."""
    name: str
    role: str  # 'support', 'surface', 'connection', 'decoration', etc.
    bbox: Optional[AABB] = None
    center: Optional[Vec3] = None
    proportion: float = 0.0  # fraction of whole
    sub_parts: List['SpatialPart'] = field(default_factory=list)


class PerceptionLayer:
    """⓪知覚層 — Convert diverse inputs to SpatialRepresentation.

    Analogous to MultimodalInputLayer but for 3D data.
    Each modality processor extracts spatial features independently.
    """

    @staticmethod
    def from_mesh(mesh: Mesh) -> SpatialRepresentation:
        """Extract spatial representation from triangle mesh."""
        bbox = mesh.bounding_box()
        center = mesh.center_of_mass()
        extent = bbox.size
        euler = mesh.euler_characteristic()
        genus = max(0, (2 - euler) // 2) if euler <= 2 else 0

        rep = SpatialRepresentation(
            bounding_box=bbox,
            center=center,
            extent=extent,
            volume_estimate=bbox.volume,
            surface_area=mesh.total_surface_area(),
            is_manifold=mesh.is_manifold(),
            euler_characteristic=euler,
            genus=genus,
            is_closed=(euler == 2 and mesh.is_manifold()),
            source_modalities=[SpatialModality.MESH],
        )

        # Analyze symmetry
        rep.symmetry = PerceptionLayer._analyze_symmetry(mesh)

        # Structural decomposition by normal clustering
        rep.parts = PerceptionLayer._decompose_by_normals(mesh)

        return rep

    @staticmethod
    def from_point_cloud(points: np.ndarray) -> SpatialRepresentation:
        """Extract spatial representation from point cloud (N, 3)."""
        if len(points) == 0:
            return SpatialRepresentation(source_modalities=[SpatialModality.POINT_CLOUD])

        center = Vec3(*points.mean(axis=0))
        mn = points.min(axis=0)
        mx = points.max(axis=0)
        bbox = AABB(Vec3(*mn), Vec3(*mx))

        # Estimate density
        volume = bbox.volume
        density = len(points) / max(volume, 1e-10)

        rep = SpatialRepresentation(
            bounding_box=bbox,
            center=center,
            extent=bbox.size,
            volume_estimate=volume,
            source_modalities=[SpatialModality.POINT_CLOUD],
        )
        rep.semantic_features.append(
            SpatialFeature('point_density', 'geometric', density,
                          source_modality=SpatialModality.POINT_CLOUD))
        return rep

    @staticmethod
    def from_text(description: str) -> SpatialRepresentation:
        """Extract spatial representation from text description.

        This is the key insight: text → internal spatial model.
        Exactly parallels Youta's: language input → ヴェン図ネットワーク.
        """
        rep = SpatialRepresentation(
            source_modalities=[SpatialModality.TEXT_DESC],
            semantic_label=description,
        )

        desc_lower = description.lower()

        # Shape detection from text
        shape_keywords = {
            'sphere': ('sphere', Vec3(1, 1, 1)),
            'cube': ('cube', Vec3(1, 1, 1)),
            'box': ('box', Vec3(1, 1, 1)),
            'cylinder': ('cylinder', Vec3(1, 2, 1)),
            'cone': ('cone', Vec3(1, 2, 1)),
            'torus': ('torus', Vec3(2, 0.5, 2)),
            'plane': ('plane', Vec3(10, 0, 10)),
            'ring': ('ring', Vec3(1, 0.1, 1)),
        }
        for keyword, (shape, extent) in shape_keywords.items():
            if keyword in desc_lower:
                rep.extent = extent
                rep.semantic_features.append(
                    SpatialFeature('base_shape', 'semantic', shape, 0.8,
                                  SpatialModality.TEXT_DESC))
                break

        # Size modifiers
        size_map = {
            'tiny': 0.1, 'small': 0.5, 'medium': 1.0,
            'large': 2.0, 'huge': 5.0, 'massive': 10.0,
        }
        for word, scale in size_map.items():
            if word in desc_lower:
                rep.semantic_features.append(
                    SpatialFeature('size_modifier', 'semantic', scale, 0.7,
                                  SpatialModality.TEXT_DESC))
                if rep.extent:
                    rep.extent = rep.extent * scale
                break

        # Structural parts from text
        part_keywords = {
            'leg': ('leg', 'support'),
            'arm': ('arm', 'extension'),
            'head': ('head', 'top'),
            'body': ('body', 'core'),
            'base': ('base', 'support'),
            'top': ('top', 'surface'),
            'handle': ('handle', 'grip'),
            'seat': ('seat', 'surface'),
            'back': ('back', 'support'),
            'wheel': ('wheel', 'motion'),
            'door': ('door', 'opening'),
            'window': ('window', 'opening'),
            'roof': ('roof', 'cover'),
            'wall': ('wall', 'enclosure'),
            'floor': ('floor', 'surface'),
        }
        for keyword, (name, role) in part_keywords.items():
            if keyword in desc_lower:
                rep.parts.append(SpatialPart(name=name, role=role))

        # Semantic object recognition
        object_templates = {
            'chair': [
                SpatialPart('seat', 'surface', proportion=0.3),
                SpatialPart('backrest', 'support', proportion=0.2),
                SpatialPart('legs', 'support', proportion=0.4),
                SpatialPart('armrests', 'extension', proportion=0.1),
            ],
            'table': [
                SpatialPart('tabletop', 'surface', proportion=0.3),
                SpatialPart('legs', 'support', proportion=0.7),
            ],
            'house': [
                SpatialPart('walls', 'enclosure', proportion=0.4),
                SpatialPart('roof', 'cover', proportion=0.2),
                SpatialPart('floor', 'surface', proportion=0.15),
                SpatialPart('doors', 'opening', proportion=0.1),
                SpatialPart('windows', 'opening', proportion=0.15),
            ],
            'car': [
                SpatialPart('body', 'enclosure', proportion=0.5),
                SpatialPart('wheels', 'motion', proportion=0.2),
                SpatialPart('windshield', 'opening', proportion=0.1),
                SpatialPart('doors', 'opening', proportion=0.2),
            ],
        }
        for obj_name, template_parts in object_templates.items():
            if obj_name in desc_lower:
                rep.semantic_label = obj_name
                if not rep.parts:
                    rep.parts = template_parts
                rep.semantic_features.append(
                    SpatialFeature('object_type', 'semantic', obj_name, 0.9,
                                  SpatialModality.TEXT_DESC))
                break

        # Spatial relations from text
        relation_patterns = [
            ('on top of', 'above'), ('under', 'below'), ('beside', 'adjacent'),
            ('inside', 'contained'), ('around', 'surrounding'),
            ('in front of', 'front'), ('behind', 'back'),
            ('next to', 'adjacent'), ('above', 'above'), ('below', 'below'),
        ]
        for pattern, relation in relation_patterns:
            if pattern in desc_lower:
                rep.relations.append({'type': relation, 'source': 'text'})

        rep.confidence = 0.6  # Text is inherently less precise
        return rep

    @staticmethod
    def from_voxel_grid(grid: np.ndarray, voxel_size: float = 1.0) -> SpatialRepresentation:
        """Extract spatial representation from voxel grid (3D boolean array)."""
        occupied = np.argwhere(grid)
        if len(occupied) == 0:
            return SpatialRepresentation(source_modalities=[SpatialModality.VOXEL])

        mn = occupied.min(axis=0) * voxel_size
        mx = (occupied.max(axis=0) + 1) * voxel_size
        center = Vec3(*((mn + mx) / 2))

        volume = len(occupied) * (voxel_size ** 3)

        return SpatialRepresentation(
            bounding_box=AABB(Vec3(*mn), Vec3(*mx)),
            center=center,
            extent=Vec3(*(mx - mn)),
            volume_estimate=volume,
            source_modalities=[SpatialModality.VOXEL],
        )

    @staticmethod
    def _analyze_symmetry(mesh: Mesh) -> Dict[str, Any]:
        """Analyze mesh symmetry (reflective, rotational)."""
        verts = mesh.vertices
        center = verts.mean(axis=0)
        centered = verts - center

        # Test reflective symmetry along each axis
        symmetry = {}
        for axis, name in enumerate(['x', 'y', 'z']):
            reflected = centered.copy()
            reflected[:, axis] *= -1
            # For each reflected vertex, find nearest original
            from scipy.spatial import cKDTree
            try:
                tree = cKDTree(centered)
                dists, _ = tree.query(reflected)
                avg_dist = float(np.mean(dists))
                extent_axis = float(np.max(centered[:, axis]) - np.min(centered[:, axis]))
                if extent_axis > 0:
                    symmetry[f'reflect_{name}'] = round(
                        1.0 - min(avg_dist / (extent_axis * 0.1), 1.0), 3)
                else:
                    symmetry[f'reflect_{name}'] = 1.0
            except ImportError:
                # Fallback without scipy
                symmetry[f'reflect_{name}'] = 0.5  # Unknown

        return symmetry

    @staticmethod
    def _decompose_by_normals(mesh: Mesh) -> List[SpatialPart]:
        """Decompose mesh into parts by face normal clustering."""
        if mesh.n_faces == 0:
            return []

        normals = mesh.face_normals()

        # Simple 6-direction clustering (±X, ±Y, ±Z)
        directions = {
            'top': np.array([0, 1, 0]),
            'bottom': np.array([0, -1, 0]),
            'front': np.array([0, 0, 1]),
            'back': np.array([0, 0, -1]),
            'right': np.array([1, 0, 0]),
            'left': np.array([-1, 0, 0]),
        }

        parts = []
        for name, direction in directions.items():
            dots = normals @ direction
            mask = dots > 0.5  # Faces pointing in this direction
            if np.any(mask):
                face_count = int(np.sum(mask))
                area = float(np.sum(mesh.face_areas()[mask]))
                parts.append(SpatialPart(
                    name=name,
                    role='surface',
                    proportion=round(face_count / mesh.n_faces, 3),
                ))

        return parts


# ═══════════════════════════════════════════════════════════════
# 判断層 — 空間的矛盾検出 + 構造推論 + 意味付け
# ═══════════════════════════════════════════════════════════════

@dataclass
class SpatialContradiction:
    """A detected spatial contradiction."""
    type: str   # 'penetration', 'floating', 'scale', 'topology', 'semantic'
    severity: float  # 0.0 - 1.0
    description: str
    objects: List[str] = field(default_factory=list)
    suggestion: str = ""


class JudgmentLayer:
    """判断層 — Cross-spatial reasoning and contradiction detection.

    Analogous to ModalityJudge but for spatial data:
    - ModalityJudge: cross-modal contradiction detection
    - JudgmentLayer: cross-spatial contradiction detection

    Both use the same principle: when different sources describe the same
    thing differently, that's a signal worth investigating.
    """

    def __init__(self):
        self.reasoner = SpatialReasoner()

    def detect_contradictions(self,
                               representations: List[SpatialRepresentation]
                               ) -> List[SpatialContradiction]:
        """Detect contradictions between multiple spatial representations.

        Core insight: if mesh says "closed manifold" but text says "open box",
        that's a contradiction — same as image vs audio disagreement in ModalityJudge.
        """
        contradictions = []

        if len(representations) < 2:
            return contradictions

        for i in range(len(representations)):
            for j in range(i + 1, len(representations)):
                a, b = representations[i], representations[j]
                contradictions.extend(self._compare_pair(a, b))

        return contradictions

    def _compare_pair(self, a: SpatialRepresentation,
                       b: SpatialRepresentation) -> List[SpatialContradiction]:
        """Compare two representations for contradictions."""
        contradictions = []
        src_a = a.source_modalities[0].value if a.source_modalities else "?"
        src_b = b.source_modalities[0].value if b.source_modalities else "?"

        # Volume disagreement
        if a.volume_estimate > 0 and b.volume_estimate > 0:
            ratio = max(a.volume_estimate, b.volume_estimate) / \
                    min(a.volume_estimate, b.volume_estimate)
            if ratio > 10:
                contradictions.append(SpatialContradiction(
                    type='scale',
                    severity=min(1.0, math.log10(ratio) / 3),
                    description=f"Volume disagrees: {src_a}={a.volume_estimate:.2f} "
                               f"vs {src_b}={b.volume_estimate:.2f} (ratio {ratio:.1f}x)",
                    suggestion="Check scale normalization between modalities",
                ))

        # Topology disagreement
        if a.is_closed != b.is_closed and a.is_closed is not None and b.is_closed is not None:
            contradictions.append(SpatialContradiction(
                type='topology',
                severity=0.7,
                description=f"Topology disagrees: {src_a} closed={a.is_closed} "
                           f"vs {src_b} closed={b.is_closed}",
                suggestion="Verify if object should be watertight",
            ))

        # Part structure disagreement
        if a.parts and b.parts:
            a_parts = {p.name for p in a.parts}
            b_parts = {p.name for p in b.parts}
            only_a = a_parts - b_parts
            only_b = b_parts - a_parts
            if only_a or only_b:
                contradictions.append(SpatialContradiction(
                    type='semantic',
                    severity=0.5,
                    description=f"Part structure differs: "
                               f"{src_a} has {only_a or '∅'}, "
                               f"{src_b} has {only_b or '∅'}",
                    suggestion="Reconcile structural decompositions",
                ))

        return contradictions

    def verify_physical_plausibility(self,
                                      scene: SceneNode) -> List[SpatialContradiction]:
        """Check scene for physical plausibility issues.

        Analogous to ModalityJudge's reliability adjustment:
        physically implausible scenes get lower confidence.
        """
        contradictions = []
        nodes = scene.flatten()
        mesh_nodes = [n for n in nodes if n.mesh is not None]

        # Check for interpenetration
        for i in range(len(mesh_nodes)):
            for j in range(i + 1, len(mesh_nodes)):
                a_bb = mesh_nodes[i].mesh.bounding_box()
                b_bb = mesh_nodes[j].mesh.bounding_box()
                # Apply transforms
                a_pos = mesh_nodes[i].transform.position
                b_pos = mesh_nodes[j].transform.position
                a_bb_world = AABB(a_bb.min_point + a_pos, a_bb.max_point + a_pos)
                b_bb_world = AABB(b_bb.min_point + b_pos, b_bb.max_point + b_pos)

                if a_bb_world.intersects(b_bb_world):
                    contradictions.append(SpatialContradiction(
                        type='penetration',
                        severity=0.8,
                        description=f"'{mesh_nodes[i].name}' and '{mesh_nodes[j].name}' "
                                   f"bounding boxes overlap",
                        objects=[mesh_nodes[i].name, mesh_nodes[j].name],
                        suggestion="Check object placement or enable collision",
                    ))

        # Check for floating objects (not touching ground or other objects)
        ground_y = 0.0
        for node in mesh_nodes:
            if node.mesh:
                bb = node.mesh.bounding_box()
                min_y = bb.min_point.y + node.transform.position.y
                if min_y > ground_y + 0.5:  # More than 0.5 above ground
                    # Check if it's resting on another object
                    supported = False
                    for other in mesh_nodes:
                        if other is node and other.mesh:
                            continue
                        other_bb = other.mesh.bounding_box() if other.mesh else None
                        if other_bb:
                            other_max_y = other_bb.max_point.y + other.transform.position.y
                            if abs(min_y - other_max_y) < 0.2:
                                supported = True
                                break
                    if not supported:
                        contradictions.append(SpatialContradiction(
                            type='floating',
                            severity=0.6,
                            description=f"'{node.name}' appears to float "
                                       f"(min_y={min_y:.2f}, ground={ground_y})",
                            objects=[node.name],
                            suggestion="Add support or move to ground level",
                        ))

        # Check for extreme scale differences
        if len(mesh_nodes) >= 2:
            volumes = []
            for n in mesh_nodes:
                if n.mesh:
                    bb = n.mesh.bounding_box()
                    volumes.append((n.name, bb.volume))
            if volumes:
                max_vol = max(v for _, v in volumes)
                for name, vol in volumes:
                    if vol > 0 and max_vol / vol > 1000:
                        contradictions.append(SpatialContradiction(
                            type='scale',
                            severity=0.5,
                            description=f"'{name}' is extremely small relative to scene "
                                       f"(volume ratio: {max_vol/vol:.0f}x)",
                            objects=[name],
                            suggestion="Check scale of this object",
                        ))

        return contradictions

    def infer_spatial_relations(self,
                                 scene: SceneNode) -> List[Dict[str, Any]]:
        """Infer spatial relations between objects in scene.

        Analogous to CrossModalSolverEngine's cross-connection:
        relations between objects are like relations between modalities.
        """
        relations = []
        nodes = scene.flatten()
        mesh_nodes = [n for n in nodes if n.mesh is not None]

        for i in range(len(mesh_nodes)):
            for j in range(i + 1, len(mesh_nodes)):
                a = mesh_nodes[i]
                b = mesh_nodes[j]

                a_center = a.mesh.center_of_mass() + a.transform.position if a.mesh else a.transform.position
                b_center = b.mesh.center_of_mass() + b.transform.position if b.mesh else b.transform.position

                rel = self.reasoner.relative_position(a_center, b_center)

                # Proximity analysis
                distance = rel['distance']
                a_extent = a.mesh.bounding_box().size.length() if a.mesh else 1.0
                b_extent = b.mesh.bounding_box().size.length() if b.mesh else 1.0
                avg_size = (a_extent + b_extent) / 2

                proximity = 'touching' if distance < avg_size * 0.1 else \
                           'near' if distance < avg_size * 1.0 else \
                           'medium' if distance < avg_size * 3.0 else 'far'

                relations.append({
                    'object_a': a.name,
                    'object_b': b.name,
                    'spatial_relations': rel.get('relations', []),
                    'distance': round(distance, 3),
                    'proximity': proximity,
                })

        return relations


# ═══════════════════════════════════════════════════════════════
# SpatialJudge — 統合エンジン
# ═══════════════════════════════════════════════════════════════

class SpatialJudge:
    """3D空間認知の判断階層 — ModalityJudge の3D空間版.

    Architecture parallel:
      ModalityJudge            SpatialJudge
      ─────────────            ────────────
      ⓪ image processor    →  ⓪ mesh processor
      ⓪ audio processor    →  ⓪ point cloud processor
      ⓪ text processor     →  ⓪ text→3D processor
      判断層 cross-modal    →  判断層 cross-spatial
      矛盾検出              →  物理矛盾検出
      信頼度調整            →  構造信頼度調整
      ソルバー重みヒント    →  モデリング修正ヒント
    """

    def __init__(self):
        self.perception = PerceptionLayer()
        self.judgment = JudgmentLayer()

    def analyze(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Full analysis pipeline: perception → judgment.

        Args:
            inputs: dict with any of:
                'mesh': Mesh object
                'points': np.ndarray (N, 3)
                'text': str description
                'voxels': np.ndarray (3D bool)
                'scene': SceneNode
        """
        # ⓪ 知覚層: Convert all inputs to SpatialRepresentation
        representations = []

        if 'mesh' in inputs:
            rep = self.perception.from_mesh(inputs['mesh'])
            representations.append(rep)

        if 'points' in inputs:
            rep = self.perception.from_point_cloud(inputs['points'])
            representations.append(rep)

        if 'text' in inputs:
            rep = self.perception.from_text(inputs['text'])
            representations.append(rep)

        if 'voxels' in inputs:
            rep = self.perception.from_voxel_grid(inputs['voxels'])
            representations.append(rep)

        # 判断層: Cross-spatial analysis
        contradictions = self.judgment.detect_contradictions(representations)

        # Scene-level analysis
        scene_contradictions = []
        scene_relations = []
        if 'scene' in inputs:
            scene_contradictions = self.judgment.verify_physical_plausibility(
                inputs['scene'])
            scene_relations = self.judgment.infer_spatial_relations(
                inputs['scene'])

        all_contradictions = contradictions + scene_contradictions

        # Compute overall confidence (analogous to ModalityJudge reliability)
        base_confidence = sum(r.confidence for r in representations) / max(len(representations), 1)
        contradiction_penalty = sum(c.severity * 0.1 for c in all_contradictions)
        overall_confidence = max(0.0, min(1.0, base_confidence - contradiction_penalty))

        return {
            'representations': len(representations),
            'modalities': [r.source_modalities[0].value for r in representations
                          if r.source_modalities],
            'contradictions': [
                {'type': c.type, 'severity': c.severity,
                 'description': c.description, 'suggestion': c.suggestion}
                for c in all_contradictions
            ],
            'n_contradictions': len(all_contradictions),
            'scene_relations': scene_relations,
            'overall_confidence': round(overall_confidence, 4),
            'parts_detected': [
                {'name': p.name, 'role': p.role}
                for r in representations for p in r.parts
            ],
            'semantic_features': [
                {'name': f.name, 'value': f.value, 'confidence': f.confidence}
                for r in representations for f in r.semantic_features
            ],
            'symmetry': next(
                (r.symmetry for r in representations if r.symmetry), None),
        }


# ═══════════════════════════════════════════════════════════════
# 出力層 — 空間認知 → テキスト (逆方向翻訳)
# ═══════════════════════════════════════════════════════════════

class SpatialNarrator:
    """空間表現 → 自然言語テキスト変換.

    Youta: "空間認知からテクストは？"

    Youtaの認知モデルの逆方向:
      ⓪知覚層: テキスト → 空間表現 (言語→非言語)
      出力層:   空間表現 → テキスト (非言語→言語)

    HTLF的に重要:
      3D空間は連続・多次元 → テキストは離散・1次元
      この翻訳には必然的な情報損失(R_qualia)が発生する。
      角度の微妙なニュアンス、テクスチャの質感、空間的な「気配」は
      言語化すると失われる — これがまさにR_qualiaの本質。

    出力レベル:
      L1: 幾何記述 (寸法、形状、位置) — R_struct高, R_qualia低
      L2: 構造記述 (パーツ、関係性) — R_context高
      L3: 意味記述 (用途、印象) — R_qualia高, R_struct低
      L4: 詩的記述 (雰囲気、感情) — R_qualia最大, R_struct最小
    """

    def narrate(self, rep: SpatialRepresentation,
                level: str = "L2",
                scene: Optional[SceneNode] = None,
                analysis: Optional[Dict[str, Any]] = None) -> str:
        """Generate text from spatial representation.

        Args:
            rep: SpatialRepresentation to narrate
            level: L1 (geometric), L2 (structural), L3 (semantic), L4 (poetic)
            scene: Optional scene for relational context
            analysis: Optional SpatialJudge analysis result
        """
        if level == "L1":
            return self._narrate_geometric(rep)
        elif level == "L2":
            return self._narrate_structural(rep, analysis)
        elif level == "L3":
            return self._narrate_semantic(rep, analysis)
        elif level == "L4":
            return self._narrate_poetic(rep, scene, analysis)
        else:
            return self._narrate_structural(rep, analysis)

    def narrate_scene(self, scene: SceneNode,
                       analysis: Optional[Dict[str, Any]] = None,
                       level: str = "L2") -> str:
        """Generate text description of an entire scene."""
        nodes = scene.flatten()
        mesh_nodes = [n for n in nodes if n.mesh is not None]

        lines = []

        # Scene overview
        stats = scene.stats()
        lines.append(f"Scene with {stats['meshes']} objects "
                     f"({stats['vertices']} vertices, {stats['faces']} faces).")

        # Describe each object
        for node in mesh_nodes:
            if node.mesh:
                rep = PerceptionLayer.from_mesh(node.mesh)
                rep.semantic_label = node.name
                obj_desc = self._narrate_object_in_scene(node, rep, level)
                lines.append(obj_desc)

        # Relations
        if analysis and 'scene_relations' in analysis:
            rel_lines = []
            for rel in analysis['scene_relations']:
                spatial = ', '.join(rel['spatial_relations']) if rel['spatial_relations'] else 'near'
                rel_lines.append(
                    f"{rel['object_a']} is {spatial} {rel['object_b']} "
                    f"({rel['proximity']}, dist={rel['distance']})")
            if rel_lines:
                lines.append("Spatial relations: " + "; ".join(rel_lines) + ".")

        # Contradictions
        if analysis and analysis.get('contradictions'):
            issues = []
            for c in analysis['contradictions']:
                issues.append(f"{c['type']}: {c['description']}")
            lines.append("⚠️ Issues detected: " + "; ".join(issues))

        return "\n".join(lines)

    def _narrate_geometric(self, rep: SpatialRepresentation) -> str:
        """L1: Pure geometric description."""
        parts = []

        if rep.bounding_box:
            s = rep.extent or rep.bounding_box.size
            parts.append(f"Bounding box: {s.x:.2f} × {s.y:.2f} × {s.z:.2f}")

        if rep.center:
            parts.append(f"Center at ({rep.center.x:.2f}, {rep.center.y:.2f}, {rep.center.z:.2f})")

        if rep.volume_estimate > 0:
            parts.append(f"Volume: {rep.volume_estimate:.3f}")

        if rep.surface_area > 0:
            parts.append(f"Surface area: {rep.surface_area:.2f}")

        parts.append(f"Topology: {'closed' if rep.is_closed else 'open'} "
                     f"{'manifold' if rep.is_manifold else 'non-manifold'}, "
                     f"χ={rep.euler_characteristic}, genus={rep.genus}")

        if rep.symmetry:
            sym_axes = [axis.replace('reflect_', '')
                       for axis, val in rep.symmetry.items()
                       if val > 0.8]
            if sym_axes:
                parts.append(f"Symmetric along: {', '.join(sym_axes)}")

        return ". ".join(parts) + "."

    def _narrate_structural(self, rep: SpatialRepresentation,
                             analysis: Optional[Dict[str, Any]] = None) -> str:
        """L2: Structural description with parts and relations."""
        parts = []

        # Shape identification
        shape = self._identify_shape(rep)
        if rep.semantic_label:
            parts.append(f"A {shape} identified as '{rep.semantic_label}'")
        else:
            parts.append(f"A {shape}")

        # Size description
        if rep.extent:
            size_word = self._size_word(rep.extent.length())
            parts.append(f"{size_word} in size ({rep.extent.x:.1f} × {rep.extent.y:.1f} × {rep.extent.z:.1f})")

        # Structural parts
        if rep.parts:
            part_names = [f"{p.name} ({p.role})" for p in rep.parts[:6]]
            parts.append(f"Composed of: {', '.join(part_names)}")

        # Topology
        if rep.is_closed:
            parts.append("The form is closed and watertight")
        else:
            parts.append("The form has openings")

        if rep.genus > 0:
            parts.append(f"with {rep.genus} hole{'s' if rep.genus > 1 else ''}")

        # Symmetry
        if rep.symmetry:
            high_sym = [ax.replace('reflect_', '').upper()
                       for ax, v in rep.symmetry.items() if v > 0.9]
            if len(high_sym) == 3:
                parts.append("Highly symmetric (all three axes)")
            elif high_sym:
                parts.append(f"Symmetric along {', '.join(high_sym)}")

        return ". ".join(parts) + "."

    def _narrate_semantic(self, rep: SpatialRepresentation,
                           analysis: Optional[Dict[str, Any]] = None) -> str:
        """L3: Semantic/functional description."""
        parts = []

        if rep.semantic_label:
            parts.append(f"This is a {rep.semantic_label}")
        else:
            shape = self._identify_shape(rep)
            parts.append(f"This appears to be a {shape}")

        # Functional interpretation from parts
        roles = {}
        for p in rep.parts:
            roles.setdefault(p.role, []).append(p.name)

        if 'support' in roles:
            parts.append(f"It is supported by: {', '.join(roles['support'])}")
        if 'surface' in roles:
            parts.append(f"It has usable surfaces: {', '.join(roles['surface'])}")
        if 'opening' in roles:
            parts.append(f"It has openings: {', '.join(roles['opening'])}")
        if 'enclosure' in roles:
            parts.append(f"It encloses space via: {', '.join(roles['enclosure'])}")

        # Proportional analysis
        if rep.extent:
            ratio_hw = rep.extent.y / max(rep.extent.x, 0.001)
            if ratio_hw > 3:
                parts.append("It is tall and slender")
            elif ratio_hw > 1.5:
                parts.append("It is upright")
            elif ratio_hw < 0.3:
                parts.append("It is flat and spread out")
            elif ratio_hw < 0.7:
                parts.append("It is low and wide")

        # Semantic features
        for feat in rep.semantic_features:
            if feat.name == 'object_type':
                object_descriptions = {
                    'chair': "designed for sitting, combining comfort and support",
                    'table': "a horizontal surface for placing objects",
                    'house': "an enclosed dwelling space with rooms",
                    'car': "a mobile enclosed vehicle",
                }
                desc = object_descriptions.get(feat.value, "")
                if desc:
                    parts.append(desc)

        return ". ".join(parts) + "."

    def _narrate_poetic(self, rep: SpatialRepresentation,
                         scene: Optional[SceneNode] = None,
                         analysis: Optional[Dict[str, Any]] = None) -> str:
        """L4: Poetic/atmospheric description — maximum R_qualia."""
        parts = []

        shape = self._identify_shape(rep)

        # Proportional poetry
        if rep.extent:
            aspect = rep.extent.y / max(rep.extent.x, 0.001)
            if aspect > 2:
                parts.append(f"A {shape} reaching upward, aspiring toward height")
            elif aspect < 0.5:
                parts.append(f"A {shape} stretching across the ground, embracing the horizontal")
            else:
                parts.append(f"A {shape} in quiet balance, neither reaching nor resting")

        # Symmetry as aesthetic quality
        if rep.symmetry:
            high_count = sum(1 for v in rep.symmetry.values() if v > 0.9)
            if high_count == 3:
                parts.append("Perfect symmetry in every direction — "
                           "the form exists equally in all dimensions")
            elif high_count >= 1:
                parts.append("An asymmetry gives it character, a deliberate imperfection "
                           "that makes the eye linger")

        # Topology as metaphor
        if rep.is_closed:
            parts.append("The surface is unbroken — a world complete unto itself")
        else:
            parts.append("Openings invite the gaze inward, suggesting depth beyond surface")

        if rep.genus > 0:
            parts.append(f"{'A passage' if rep.genus == 1 else 'Passages'} "
                        f"through the form — space folded through itself")

        # Parts as narrative
        if rep.parts:
            role_groups = {}
            for p in rep.parts:
                role_groups.setdefault(p.role, []).append(p.name)
            if 'support' in role_groups:
                parts.append("Below, the structure grounds itself — "
                           "gravity answered with architecture")
            if 'surface' in role_groups:
                parts.append("Surfaces await contact, defining the boundary "
                           "between interior thought and exterior world")

        return ". ".join(parts) + "."

    def _narrate_object_in_scene(self, node: SceneNode,
                                  rep: SpatialRepresentation,
                                  level: str) -> str:
        """Describe a single object in scene context."""
        pos = node.transform.position
        name = node.name

        if level == "L1":
            return (f"'{name}' at ({pos.x:.1f}, {pos.y:.1f}, {pos.z:.1f}), "
                   f"{'closed' if rep.is_closed else 'open'} "
                   f"{'manifold' if rep.is_manifold else ''}")
        elif level == "L3" or level == "L4":
            shape = self._identify_shape(rep)
            return f"'{name}' — a {shape} positioned at height {pos.y:.1f}"
        else:
            shape = self._identify_shape(rep)
            bb = rep.bounding_box
            size_str = ""
            if bb:
                s = bb.size
                size_str = f" ({s.x:.1f}×{s.y:.1f}×{s.z:.1f})"
            return f"'{name}': {shape}{size_str} at ({pos.x:.1f}, {pos.y:.1f}, {pos.z:.1f})"

    def _identify_shape(self, rep: SpatialRepresentation) -> str:
        """Identify the basic shape from spatial properties."""
        if rep.semantic_label:
            return rep.semantic_label

        # From semantic features
        for f in rep.semantic_features:
            if f.name == 'base_shape':
                return f.value

        # From geometry
        if rep.extent:
            x, y, z = rep.extent.x, rep.extent.y, rep.extent.z
            if x > 0 and y > 0 and z > 0:
                ratios = sorted([x/max(y, 0.001), y/max(z, 0.001), z/max(x, 0.001)])
                if all(0.8 < r < 1.2 for r in ratios):
                    if rep.is_closed and rep.symmetry:
                        sym_vals = list(rep.symmetry.values())
                        if all(v > 0.9 for v in sym_vals):
                            return "sphere-like form"
                    return "cube-like form"
                elif ratios[0] < 0.3:
                    return "flat form"
                elif ratios[2] > 2.0:
                    return "elongated form"

        return "form"

    def _size_word(self, extent_length: float) -> str:
        """Convert absolute size to descriptive word."""
        if extent_length < 0.1:
            return "tiny"
        elif extent_length < 0.5:
            return "small"
        elif extent_length < 2.0:
            return "medium"
        elif extent_length < 5.0:
            return "large"
        elif extent_length < 20.0:
            return "very large"
        else:
            return "massive"


def get_status() -> Dict[str, Any]:
    return {
        'version': VERSION,
        'engine': 'SpatialJudge',
        'architecture': {
            'perception_layer': {
                'modalities': [m.value for m in SpatialModality],
                'output': 'SpatialRepresentation (unified)',
            },
            'judgment_layer': {
                'contradiction_types': [
                    'penetration', 'floating', 'scale',
                    'topology', 'semantic',
                ],
                'reasoning': [
                    'physical_plausibility', 'spatial_relations',
                    'cross-modality_contradiction', 'structural_decomposition',
                ],
            },
        },
        'analogy': {
            'ModalityJudge': 'SpatialJudge',
            'MultimodalInputLayer': 'PerceptionLayer',
            'cross-modal contradiction': 'cross-spatial contradiction',
            'reliability adjustment': 'confidence adjustment',
            'solver weight hints': 'modeling correction hints',
        },
    }
