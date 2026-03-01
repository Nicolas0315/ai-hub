"""
Katala Studio — Humanoid Rig System
VRChat/Unity Humanoid互換のボーン構造を生成し、メッシュにスキニングする

Bone hierarchy follows Unity Humanoid specification:
  Hips → Spine → Chest → UpperChest → Neck → Head
  Hips → LeftUpperLeg → LeftLowerLeg → LeftFoot → LeftToes
  Hips → RightUpperLeg → RightLowerLeg → RightFoot → RightToes
  UpperChest → LeftShoulder → LeftUpperArm → LeftLowerArm → LeftHand
  UpperChest → RightShoulder → RightUpperArm → RightLowerArm → RightHand

Design: Youta Hilono (architecture)
Implementation: Shirokuma (OpenClaw AI)
"""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Bone:
    """ボーン定義"""
    name: str
    head: np.ndarray  # ボーン始点 (world space)
    tail: np.ndarray  # ボーン終点 (world space)
    parent: Optional[str] = None
    humanoid_name: str = ""  # Unity Humanoidマッピング名
    children: list[str] = field(default_factory=list)

    @property
    def length(self) -> float:
        return float(np.linalg.norm(self.tail - self.head))

    @property
    def direction(self) -> np.ndarray:
        d = self.tail - self.head
        l = np.linalg.norm(d)
        return d / l if l > 1e-8 else np.array([0, 1, 0])

    @property
    def local_position(self) -> np.ndarray:
        """Position relative to parent (for FBX Lcl Translation)"""
        return self.head  # Simplified; proper impl needs parent transform


@dataclass
class SkinWeight:
    """頂点のスキンウェイト"""
    vertex_index: int
    bone_indices: list[int]  # Up to 4 bones
    weights: list[float]  # Corresponding weights (sum to 1.0)


class HumanoidRig:
    """VRChat/Unity Humanoid互換リグ"""

    def __init__(self, height_cm: float = 179.0):
        self.height = height_cm
        self.scale = 1.0 / 100.0  # cm → meters
        self.bones: dict[str, Bone] = {}
        self.bone_order: list[str] = []  # Insertion order for export
        self.skin_weights: list[SkinWeight] = []

        self._build_skeleton()

    def _add_bone(self, name: str, head_cm: np.ndarray, tail_cm: np.ndarray,
                  parent: str | None = None, humanoid_name: str = ""):
        """ボーン追加 (cm座標)"""
        bone = Bone(
            name=name,
            head=head_cm * self.scale,
            tail=tail_cm * self.scale,
            parent=parent,
            humanoid_name=humanoid_name or name,
        )
        self.bones[name] = bone
        self.bone_order.append(name)
        if parent and parent in self.bones:
            self.bones[parent].children.append(name)

    def _build_skeleton(self):
        """VRChat Humanoid互換のボーン構造を構築"""
        h = self.height

        # ── Spine Chain ──
        self._add_bone("Hips",
                        np.array([0, 85, 0]), np.array([0, 95, 0]),
                        None, "Hips")
        self._add_bone("Spine",
                        np.array([0, 95, 0]), np.array([0, 108, 0]),
                        "Hips", "Spine")
        self._add_bone("Chest",
                        np.array([0, 108, 0]), np.array([0, 120, 0]),
                        "Spine", "Chest")
        self._add_bone("UpperChest",
                        np.array([0, 120, 0]), np.array([0, 140, 0]),
                        "Chest", "UpperChest")
        self._add_bone("Neck",
                        np.array([0, 140, 0]), np.array([0, 152, 0]),
                        "UpperChest", "Neck")
        self._add_bone("Head",
                        np.array([0, 152, 0]), np.array([0, h, 0]),
                        "Neck", "Head")

        # ── Left Leg ──
        self._add_bone("LeftUpperLeg",
                        np.array([-8, 85, 0]), np.array([-8, 46, 0]),
                        "Hips", "LeftUpperLeg")
        self._add_bone("LeftLowerLeg",
                        np.array([-8, 46, 0]), np.array([-8, 8, 0]),
                        "LeftUpperLeg", "LeftLowerLeg")
        self._add_bone("LeftFoot",
                        np.array([-8, 8, 0]), np.array([-8, 0, 5]),
                        "LeftLowerLeg", "LeftFoot")
        self._add_bone("LeftToes",
                        np.array([-8, 0, 5]), np.array([-8, 0, 12]),
                        "LeftFoot", "LeftToes")

        # ── Right Leg ──
        self._add_bone("RightUpperLeg",
                        np.array([8, 85, 0]), np.array([8, 46, 0]),
                        "Hips", "RightUpperLeg")
        self._add_bone("RightLowerLeg",
                        np.array([8, 46, 0]), np.array([8, 8, 0]),
                        "RightUpperLeg", "RightLowerLeg")
        self._add_bone("RightFoot",
                        np.array([8, 8, 0]), np.array([8, 0, 5]),
                        "RightLowerLeg", "RightFoot")
        self._add_bone("RightToes",
                        np.array([8, 0, 5]), np.array([8, 0, 12]),
                        "RightFoot", "RightToes")

        # ── Left Arm ──
        self._add_bone("LeftShoulder",
                        np.array([-5, 140, 0]), np.array([-15, 143, 0]),
                        "UpperChest", "LeftShoulder")
        self._add_bone("LeftUpperArm",
                        np.array([-18, 143, 0]), np.array([-18, 120, 0]),
                        "LeftShoulder", "LeftUpperArm")
        self._add_bone("LeftLowerArm",
                        np.array([-18, 120, 0]), np.array([-18, 95, 0]),
                        "LeftUpperArm", "LeftLowerArm")
        self._add_bone("LeftHand",
                        np.array([-18, 95, 0]), np.array([-18, 83, 0]),
                        "LeftLowerArm", "LeftHand")

        # ── Right Arm ──
        self._add_bone("RightShoulder",
                        np.array([5, 140, 0]), np.array([15, 143, 0]),
                        "UpperChest", "RightShoulder")
        self._add_bone("RightUpperArm",
                        np.array([18, 143, 0]), np.array([18, 120, 0]),
                        "RightShoulder", "RightUpperArm")
        self._add_bone("RightLowerArm",
                        np.array([18, 120, 0]), np.array([18, 95, 0]),
                        "RightUpperArm", "RightLowerArm")
        self._add_bone("RightHand",
                        np.array([18, 95, 0]), np.array([18, 83, 0]),
                        "RightLowerArm", "RightHand")

    def compute_skin_weights(self, positions: np.ndarray, max_influences: int = 4):
        """各頂点に最も近いボーンのウェイトを計算（距離ベース）"""
        self.skin_weights = []
        bone_list = list(self.bones.values())

        for vi in range(len(positions)):
            pos = positions[vi]

            # 各ボーンとの距離を計算（ボーンの線分との最短距離）
            distances = []
            for bi, bone in enumerate(bone_list):
                d = self._point_to_segment_distance(pos, bone.head, bone.tail)
                distances.append((bi, d))

            # 近い順にソート
            distances.sort(key=lambda x: x[1])

            # Top N influences
            top = distances[:max_influences]

            # 距離の逆数でウェイト計算
            inv_dists = []
            for bi, d in top:
                inv_dists.append(1.0 / (d + 0.001))

            total = sum(inv_dists)
            if total > 0:
                weights = [w / total for w in inv_dists]
            else:
                weights = [1.0 / max_influences] * max_influences

            self.skin_weights.append(SkinWeight(
                vertex_index=vi,
                bone_indices=[t[0] for t in top],
                weights=weights,
            ))

    @staticmethod
    def _point_to_segment_distance(point: np.ndarray,
                                    seg_start: np.ndarray,
                                    seg_end: np.ndarray) -> float:
        """点と線分の最短距離"""
        seg = seg_end - seg_start
        seg_len_sq = np.dot(seg, seg)
        if seg_len_sq < 1e-12:
            return float(np.linalg.norm(point - seg_start))
        t = np.clip(np.dot(point - seg_start, seg) / seg_len_sq, 0, 1)
        projection = seg_start + t * seg
        return float(np.linalg.norm(point - projection))

    def get_bone_list(self) -> list[Bone]:
        """Export順でボーンのリストを返す"""
        return [self.bones[name] for name in self.bone_order]

    @property
    def bone_count(self) -> int:
        return len(self.bones)


def export_fbx_with_rig(mesh, rig: HumanoidRig, filepath: str):
    """リグ付きFBX ASCII 7.4出力

    FBX structure:
    - Root (Model, Null)
      - Armature (Model, Null)
        - Bone1 (Model, LimbNode)
        - Bone2 (Model, LimbNode)
        - ...
      - Mesh (Model, Mesh)
        - Geometry
        - Skin Deformer
          - Cluster per bone (weights + indices)
    """
    positions = mesh.get_positions_array().flatten()
    normals = mesh.get_normals_array().flatten()
    indices = mesh.get_index_array()
    ks_score = mesh.ks_quality_score()

    bones = rig.get_bone_list()
    bone_names = [b.name for b in bones]

    # Compute skin weights
    pos_array = mesh.get_positions_array()
    rig.compute_skin_weights(pos_array)

    # ID allocation
    root_id = 100000
    armature_id = 100001
    mesh_model_id = 100002
    geom_id = 200000
    mat_id = 300000
    skin_id = 400000
    bone_id_start = 500000
    cluster_id_start = 600000
    pose_id = 700000

    with open(filepath, 'w') as f:
        # ── Header ──
        f.write('; FBX 7.4.0 project file\n')
        f.write('; Katala Studio — Rigged Humanoid Export\n')
        f.write(f'; KS Quality Score: {ks_score:.3f}\n')
        f.write(f'; Bones: {len(bones)}\n')
        f.write(f'; Vertices: {len(pos_array)}\n')
        f.write('; ---\n\n')

        f.write('FBXHeaderExtension:  {\n')
        f.write('    FBXHeaderVersion: 1003\n')
        f.write('    FBXVersion: 7400\n')
        f.write('    Creator: "Katala Studio v0.2 — Humanoid Rig"\n')
        f.write('}\n\n')

        f.write('GlobalSettings:  {\n')
        f.write('    Version: 1000\n')
        f.write('    Properties70:  {\n')
        f.write('        P: "UpAxis", "int", "Integer", "",1\n')
        f.write('        P: "UpAxisSign", "int", "Integer", "",1\n')
        f.write('        P: "FrontAxis", "int", "Integer", "",2\n')
        f.write('        P: "FrontAxisSign", "int", "Integer", "",1\n')
        f.write('        P: "CoordAxis", "int", "Integer", "",0\n')
        f.write('        P: "CoordAxisSign", "int", "Integer", "",1\n')
        f.write('        P: "UnitScaleFactor", "double", "Number", "",1\n')
        f.write('    }\n')
        f.write('}\n\n')

        # ── Objects ──
        f.write('Objects:  {\n\n')

        # Geometry
        f.write(f'    Geometry: {geom_id}, "Geometry::{mesh.name}", "Mesh" {{\n')
        f.write(f'        Vertices: *{len(positions)} {{\n')
        f.write('            a: ')
        f.write(','.join(f'{v:.6f}' for v in positions))
        f.write('\n        }\n')

        # Indices
        f.write(f'        PolygonVertexIndex: *{len(indices)} {{\n')
        f.write('            a: ')
        tri_idx = []
        for i in range(0, len(indices), 3):
            tri_idx.append(str(indices[i]))
            tri_idx.append(str(indices[i + 1]))
            tri_idx.append(str(-(int(indices[i + 2]) + 1)))
        f.write(','.join(tri_idx))
        f.write('\n        }\n')

        # Normals
        f.write('        LayerElementNormal: 0 {\n')
        f.write('            Version: 101\n')
        f.write('            Name: ""\n')
        f.write('            MappingInformationType: "ByVertice"\n')
        f.write('            ReferenceInformationType: "Direct"\n')
        f.write(f'            Normals: *{len(normals)} {{\n')
        f.write('                a: ')
        f.write(','.join(f'{n:.6f}' for n in normals))
        f.write('\n            }\n')
        f.write('        }\n')

        f.write('        Layer: 0 {\n')
        f.write('            Version: 100\n')
        f.write('            LayerElement:  {\n')
        f.write('                Type: "LayerElementNormal"\n')
        f.write('                TypedIndex: 0\n')
        f.write('            }\n')
        f.write('        }\n')
        f.write('    }\n\n')

        # Armature (Null node)
        f.write(f'    Model: {armature_id}, "Model::Armature", "Null" {{\n')
        f.write('        Version: 232\n')
        f.write('        Properties70:  {\n')
        f.write('            P: "Lcl Translation", "Lcl Translation", "", "A",0,0,0\n')
        f.write('            P: "Lcl Rotation", "Lcl Rotation", "", "A",0,0,0\n')
        f.write('            P: "Lcl Scaling", "Lcl Scaling", "", "A",1,1,1\n')
        f.write('        }\n')
        f.write('    }\n\n')

        # Bones (LimbNode)
        for bi, bone in enumerate(bones):
            bid = bone_id_start + bi
            # Local translation relative to parent
            if bone.parent and bone.parent in rig.bones:
                parent_bone = rig.bones[bone.parent]
                local_pos = bone.head - parent_bone.head
            else:
                local_pos = bone.head

            f.write(f'    Model: {bid}, "Model::{bone.name}", "LimbNode" {{\n')
            f.write('        Version: 232\n')
            f.write('        Properties70:  {\n')
            f.write(f'            P: "Lcl Translation", "Lcl Translation", "", "A",{local_pos[0]:.6f},{local_pos[1]:.6f},{local_pos[2]:.6f}\n')
            f.write('            P: "Lcl Rotation", "Lcl Rotation", "", "A",0,0,0\n')
            f.write('            P: "Lcl Scaling", "Lcl Scaling", "", "A",1,1,1\n')
            f.write(f'            P: "Size", "double", "Number", "",{bone.length:.6f}\n')
            f.write('        }\n')
            f.write('    }\n\n')

        # Mesh model
        f.write(f'    Model: {mesh_model_id}, "Model::{mesh.name}", "Mesh" {{\n')
        f.write('        Version: 232\n')
        f.write('        Properties70:  {\n')
        f.write('            P: "Lcl Translation", "Lcl Translation", "", "A",0,0,0\n')
        f.write('            P: "Lcl Rotation", "Lcl Rotation", "", "A",0,0,0\n')
        f.write('            P: "Lcl Scaling", "Lcl Scaling", "", "A",1,1,1\n')
        f.write('        }\n')
        f.write('    }\n\n')

        # Material
        mat = mesh.materials[0] if mesh.materials else None
        if mat:
            f.write(f'    Material: {mat_id}, "Material::{mat.name}", "" {{\n')
            f.write('        Version: 102\n')
            f.write('        Properties70:  {\n')
            f.write(f'            P: "DiffuseColor", "Color", "", "A",{mat.diffuse[0]},{mat.diffuse[1]},{mat.diffuse[2]}\n')
            f.write(f'            P: "Shininess", "double", "Number", "",{mat.shininess}\n')
            f.write('        }\n')
            f.write('    }\n\n')

        # Skin Deformer
        f.write(f'    Deformer: {skin_id}, "Deformer::Skin", "Skin" {{\n')
        f.write('        Version: 101\n')
        f.write('        Link_DeformAcuracy: 50\n')
        f.write('    }\n\n')

        # Clusters (one per bone — contains vertex weights)
        for bi, bone in enumerate(bones):
            cid = cluster_id_start + bi

            # Collect vertices influenced by this bone
            vert_indices = []
            vert_weights = []
            for sw in rig.skin_weights:
                for j, bone_idx in enumerate(sw.bone_indices):
                    if bone_idx == bi and sw.weights[j] > 0.001:
                        vert_indices.append(sw.vertex_index)
                        vert_weights.append(sw.weights[j])
                        break

            f.write(f'    Deformer: {cid}, "SubDeformer::{bone.name}", "Cluster" {{\n')
            f.write('        Version: 100\n')

            if vert_indices:
                f.write(f'        Indexes: *{len(vert_indices)} {{\n')
                f.write('            a: ')
                f.write(','.join(str(i) for i in vert_indices))
                f.write('\n        }\n')

                f.write(f'        Weights: *{len(vert_weights)} {{\n')
                f.write('            a: ')
                f.write(','.join(f'{w:.6f}' for w in vert_weights))
                f.write('\n        }\n')

            # Transform (identity for bind pose)
            f.write('        Transform: *16 {\n')
            f.write('            a: 1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1\n')
            f.write('        }\n')
            f.write('        TransformLink: *16 {\n')
            # Bone world transform
            bx, by, bz = bone.head
            f.write(f'            a: 1,0,0,0,0,1,0,0,0,0,1,0,{bx:.6f},{by:.6f},{bz:.6f},1\n')
            f.write('        }\n')
            f.write('    }\n\n')

        # Bind Pose
        f.write(f'    Pose: {pose_id}, "Pose::BindPose", "BindPose" {{\n')
        f.write('        Type: "BindPose"\n')
        f.write('        Version: 100\n')
        f.write(f'        NbPoseNodes: {len(bones) + 1}\n')

        # Mesh in bind pose
        f.write(f'        PoseNode:  {{\n')
        f.write(f'            Node: {mesh_model_id}\n')
        f.write('            Matrix: *16 {\n')
        f.write('                a: 1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1\n')
        f.write('            }\n')
        f.write('        }\n')

        # Each bone in bind pose
        for bi, bone in enumerate(bones):
            bid = bone_id_start + bi
            bx, by, bz = bone.head
            f.write(f'        PoseNode:  {{\n')
            f.write(f'            Node: {bid}\n')
            f.write('            Matrix: *16 {\n')
            f.write(f'                a: 1,0,0,0,0,1,0,0,0,0,1,0,{bx:.6f},{by:.6f},{bz:.6f},1\n')
            f.write('            }\n')
            f.write('        }\n')

        f.write('    }\n\n')

        f.write('}\n\n')  # End Objects

        # ── Connections ──
        f.write('Connections:  {\n')

        # Armature → Root
        f.write(f'    C: "OO",{armature_id},0\n')

        # Bones → parent
        for bi, bone in enumerate(bones):
            bid = bone_id_start + bi
            if bone.parent and bone.parent in rig.bones:
                parent_idx = bone_names.index(bone.parent)
                parent_id = bone_id_start + parent_idx
                f.write(f'    C: "OO",{bid},{parent_id}\n')
            else:
                f.write(f'    C: "OO",{bid},{armature_id}\n')

        # Mesh → Root
        f.write(f'    C: "OO",{mesh_model_id},0\n')
        # Geometry → Mesh
        f.write(f'    C: "OO",{geom_id},{mesh_model_id}\n')
        # Material → Mesh
        if mat:
            f.write(f'    C: "OO",{mat_id},{mesh_model_id}\n')
        # Skin → Geometry
        f.write(f'    C: "OO",{skin_id},{geom_id}\n')

        # Clusters → Skin, Bones → Clusters
        for bi, bone in enumerate(bones):
            cid = cluster_id_start + bi
            bid = bone_id_start + bi
            f.write(f'    C: "OO",{cid},{skin_id}\n')
            f.write(f'    C: "OO",{bid},{cid}\n')

        f.write('}\n')

    mesh.ks_verify_operation("export_fbx_rigged", 0.88, 0.95, 0.08)
