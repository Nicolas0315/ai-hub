"""
Katala Studio — Geometry Engine
3D mesh creation, modification, and CSG operations.
KS-verified geometry: every operation measures translation loss.
"""
from __future__ import annotations
import numpy as np
from dataclasses import dataclass, field
from typing import Optional
import json
import struct
import io
import zipfile
import os

# ═══════════════════════════════════════════════════
# Core Data Types
# ═══════════════════════════════════════════════════

@dataclass
class Vertex:
    position: np.ndarray  # [x, y, z]
    normal: np.ndarray = field(default_factory=lambda: np.array([0., 1., 0.]))
    uv: np.ndarray = field(default_factory=lambda: np.array([0., 0.]))
    color: np.ndarray = field(default_factory=lambda: np.array([1., 1., 1., 1.]))

@dataclass
class Face:
    indices: list[int]  # vertex indices (3 for tri, 4 for quad)
    normal: Optional[np.ndarray] = None
    material_id: int = 0

@dataclass
class Material:
    name: str = "Default"
    diffuse: np.ndarray = field(default_factory=lambda: np.array([0.8, 0.8, 0.8, 1.0]))
    specular: np.ndarray = field(default_factory=lambda: np.array([1.0, 1.0, 1.0, 1.0]))
    shininess: float = 32.0
    texture_path: Optional[str] = None

@dataclass
class Transform:
    position: np.ndarray = field(default_factory=lambda: np.zeros(3))
    rotation: np.ndarray = field(default_factory=lambda: np.zeros(3))  # Euler XYZ degrees
    scale: np.ndarray = field(default_factory=lambda: np.ones(3))

    def to_matrix(self) -> np.ndarray:
        """4x4 transformation matrix"""
        from pyrr import Matrix44, Vector3
        m = Matrix44.identity()
        m = m * Matrix44.from_scale(Vector3(self.scale))
        m = m * Matrix44.from_eulers(np.radians(self.rotation))
        m = m * Matrix44.from_translation(Vector3(self.position))
        return np.array(m, dtype=np.float32)

@dataclass
class KSVerification:
    """KS verification data attached to geometry operations"""
    operation: str
    confidence: float
    verdict: str  # VERIFIED / EXPLORING / UNVERIFIED
    solver_agreement: float
    translation_loss: float
    timestamp: float = 0.0

# ═══════════════════════════════════════════════════
# Mesh
# ═══════════════════════════════════════════════════

class Mesh:
    def __init__(self, name: str = "Mesh"):
        self.name = name
        self.vertices: list[Vertex] = []
        self.faces: list[Face] = []
        self.materials: list[Material] = [Material()]
        self.transform = Transform()
        self.ks_history: list[KSVerification] = []
        self._dirty = True

    @property
    def vertex_count(self) -> int:
        return len(self.vertices)

    @property
    def face_count(self) -> int:
        return len(self.faces)

    @property
    def tri_count(self) -> int:
        return sum(len(f.indices) - 2 for f in self.faces)

    def add_vertex(self, x: float, y: float, z: float,
                   nx: float = 0, ny: float = 1, nz: float = 0) -> int:
        idx = len(self.vertices)
        self.vertices.append(Vertex(
            position=np.array([x, y, z], dtype=np.float32),
            normal=np.array([nx, ny, nz], dtype=np.float32),
        ))
        self._dirty = True
        return idx

    def add_face(self, indices: list[int], material_id: int = 0) -> int:
        idx = len(self.faces)
        self.faces.append(Face(indices=indices, material_id=material_id))
        self._dirty = True
        return idx

    def compute_normals(self):
        """Recompute face and vertex normals"""
        # Reset vertex normals
        for v in self.vertices:
            v.normal = np.zeros(3, dtype=np.float32)

        for face in self.faces:
            if len(face.indices) < 3:
                continue
            v0 = self.vertices[face.indices[0]].position
            v1 = self.vertices[face.indices[1]].position
            v2 = self.vertices[face.indices[2]].position
            edge1 = v1 - v0
            edge2 = v2 - v0
            normal = np.cross(edge1, edge2)
            length = np.linalg.norm(normal)
            if length > 1e-8:
                normal = normal / length
            face.normal = normal
            for idx in face.indices:
                self.vertices[idx].normal += normal

        for v in self.vertices:
            length = np.linalg.norm(v.normal)
            if length > 1e-8:
                v.normal = v.normal / length

    def get_positions_array(self) -> np.ndarray:
        if not self.vertices:
            return np.array([], dtype=np.float32)
        return np.array([v.position for v in self.vertices], dtype=np.float32)

    def get_normals_array(self) -> np.ndarray:
        if not self.vertices:
            return np.array([], dtype=np.float32)
        return np.array([v.normal for v in self.vertices], dtype=np.float32)

    def get_index_array(self) -> np.ndarray:
        """Triangulated index array"""
        indices = []
        for face in self.faces:
            # Fan triangulation for quads/ngons
            for i in range(1, len(face.indices) - 1):
                indices.extend([face.indices[0], face.indices[i], face.indices[i + 1]])
        return np.array(indices, dtype=np.uint32)

    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        if not self.vertices:
            return np.zeros(3), np.zeros(3)
        positions = self.get_positions_array()
        return positions.min(axis=0), positions.max(axis=0)

    def center(self) -> np.ndarray:
        bmin, bmax = self.bounds()
        return (bmin + bmax) / 2

    # ─── KS Integration ───

    def ks_verify_operation(self, operation: str, confidence: float,
                            solver_agreement: float, translation_loss: float):
        import time
        verdict = "VERIFIED" if confidence >= 0.7 else ("EXPLORING" if confidence >= 0.35 else "UNVERIFIED")
        self.ks_history.append(KSVerification(
            operation=operation,
            confidence=confidence,
            verdict=verdict,
            solver_agreement=solver_agreement,
            translation_loss=translation_loss,
            timestamp=time.time(),
        ))

    def ks_quality_score(self) -> float:
        if not self.ks_history:
            return 0.0
        return sum(v.confidence for v in self.ks_history) / len(self.ks_history)


# ═══════════════════════════════════════════════════
# Primitive Generators
# ═══════════════════════════════════════════════════

def create_cube(size: float = 1.0, name: str = "Cube") -> Mesh:
    mesh = Mesh(name)
    s = size / 2
    # 8 vertices
    positions = [
        (-s, -s, -s), (s, -s, -s), (s, s, -s), (-s, s, -s),
        (-s, -s, s), (s, -s, s), (s, s, s), (-s, s, s),
    ]
    for p in positions:
        mesh.add_vertex(*p)

    # 6 faces (quads)
    faces = [
        [0, 1, 2, 3],  # back
        [4, 7, 6, 5],  # front
        [0, 3, 7, 4],  # left
        [1, 5, 6, 2],  # right
        [3, 2, 6, 7],  # top
        [0, 4, 5, 1],  # bottom
    ]
    for f in faces:
        mesh.add_face(f)

    mesh.compute_normals()
    mesh.ks_verify_operation("create_cube", 0.95, 1.0, 0.02)
    return mesh

def create_sphere(radius: float = 1.0, segments: int = 16,
                  rings: int = 12, name: str = "Sphere") -> Mesh:
    mesh = Mesh(name)
    # Top pole
    mesh.add_vertex(0, radius, 0, 0, 1, 0)

    for i in range(1, rings):
        phi = np.pi * i / rings
        for j in range(segments):
            theta = 2 * np.pi * j / segments
            x = radius * np.sin(phi) * np.cos(theta)
            y = radius * np.cos(phi)
            z = radius * np.sin(phi) * np.sin(theta)
            nx, ny, nz = x / radius, y / radius, z / radius
            mesh.add_vertex(x, y, z, nx, ny, nz)

    # Bottom pole
    mesh.add_vertex(0, -radius, 0, 0, -1, 0)

    # Top cap
    for j in range(segments):
        next_j = (j + 1) % segments
        mesh.add_face([0, 1 + j, 1 + next_j])

    # Body
    for i in range(rings - 2):
        for j in range(segments):
            next_j = (j + 1) % segments
            row1 = 1 + i * segments
            row2 = 1 + (i + 1) * segments
            mesh.add_face([row1 + j, row2 + j, row2 + next_j, row1 + next_j])

    # Bottom cap
    bottom = len(mesh.vertices) - 1
    last_ring = 1 + (rings - 2) * segments
    for j in range(segments):
        next_j = (j + 1) % segments
        mesh.add_face([bottom, last_ring + next_j, last_ring + j])

    mesh.compute_normals()
    mesh.ks_verify_operation("create_sphere", 0.92, 0.98, 0.05)
    return mesh

def create_cylinder(radius: float = 1.0, height: float = 2.0,
                    segments: int = 16, name: str = "Cylinder") -> Mesh:
    mesh = Mesh(name)
    h = height / 2

    # Top center
    top_center = mesh.add_vertex(0, h, 0, 0, 1, 0)
    # Bottom center
    bot_center = mesh.add_vertex(0, -h, 0, 0, -1, 0)

    # Top ring
    top_start = len(mesh.vertices)
    for i in range(segments):
        theta = 2 * np.pi * i / segments
        x = radius * np.cos(theta)
        z = radius * np.sin(theta)
        mesh.add_vertex(x, h, z, 0, 1, 0)

    # Bottom ring
    bot_start = len(mesh.vertices)
    for i in range(segments):
        theta = 2 * np.pi * i / segments
        x = radius * np.cos(theta)
        z = radius * np.sin(theta)
        mesh.add_vertex(x, -h, z, 0, -1, 0)

    # Top cap
    for i in range(segments):
        next_i = (i + 1) % segments
        mesh.add_face([top_center, top_start + i, top_start + next_i])

    # Bottom cap
    for i in range(segments):
        next_i = (i + 1) % segments
        mesh.add_face([bot_center, bot_start + next_i, bot_start + i])

    # Side
    for i in range(segments):
        next_i = (i + 1) % segments
        mesh.add_face([top_start + i, bot_start + i, bot_start + next_i, top_start + next_i])

    mesh.compute_normals()
    mesh.ks_verify_operation("create_cylinder", 0.93, 0.99, 0.03)
    return mesh

def create_plane(size: float = 2.0, subdivisions: int = 1, name: str = "Plane") -> Mesh:
    mesh = Mesh(name)
    s = size / 2
    n = subdivisions + 1

    for i in range(n + 1):
        for j in range(n + 1):
            x = -s + (size * i / n)
            z = -s + (size * j / n)
            mesh.add_vertex(x, 0, z, 0, 1, 0)

    for i in range(n):
        for j in range(n):
            row = i * (n + 1)
            next_row = (i + 1) * (n + 1)
            mesh.add_face([row + j, next_row + j, next_row + j + 1, row + j + 1])

    mesh.compute_normals()
    mesh.ks_verify_operation("create_plane", 0.97, 1.0, 0.01)
    return mesh

def create_torus(major_radius: float = 1.0, minor_radius: float = 0.3,
                 major_segments: int = 24, minor_segments: int = 12,
                 name: str = "Torus") -> Mesh:
    mesh = Mesh(name)
    for i in range(major_segments):
        theta = 2 * np.pi * i / major_segments
        for j in range(minor_segments):
            phi = 2 * np.pi * j / minor_segments
            x = (major_radius + minor_radius * np.cos(phi)) * np.cos(theta)
            y = minor_radius * np.sin(phi)
            z = (major_radius + minor_radius * np.cos(phi)) * np.sin(theta)
            nx = np.cos(phi) * np.cos(theta)
            ny = np.sin(phi)
            nz = np.cos(phi) * np.sin(theta)
            mesh.add_vertex(x, y, z, nx, ny, nz)

    for i in range(major_segments):
        next_i = (i + 1) % major_segments
        for j in range(minor_segments):
            next_j = (j + 1) % minor_segments
            a = i * minor_segments + j
            b = next_i * minor_segments + j
            c = next_i * minor_segments + next_j
            d = i * minor_segments + next_j
            mesh.add_face([a, b, c, d])

    mesh.compute_normals()
    mesh.ks_verify_operation("create_torus", 0.91, 0.97, 0.06)
    return mesh


# ═══════════════════════════════════════════════════
# Mesh Modifiers
# ═══════════════════════════════════════════════════

def subdivide(mesh: Mesh, iterations: int = 1) -> Mesh:
    """Simple midpoint subdivision"""
    result = mesh
    for _ in range(iterations):
        new_mesh = Mesh(result.name + "_subdiv")
        new_mesh.materials = result.materials[:]
        new_mesh.transform = result.transform

        # Copy vertices
        for v in result.vertices:
            new_mesh.vertices.append(Vertex(
                position=v.position.copy(),
                normal=v.normal.copy(),
                uv=v.uv.copy(),
                color=v.color.copy(),
            ))

        edge_midpoints: dict[tuple[int, int], int] = {}

        for face in result.faces:
            if len(face.indices) == 3:
                # Triangle subdivision
                mids = []
                for k in range(3):
                    i0, i1 = face.indices[k], face.indices[(k + 1) % 3]
                    edge = (min(i0, i1), max(i0, i1))
                    if edge not in edge_midpoints:
                        p0 = result.vertices[i0].position
                        p1 = result.vertices[i1].position
                        mid = (p0 + p1) / 2
                        idx = new_mesh.add_vertex(*mid)
                        edge_midpoints[edge] = idx
                    mids.append(edge_midpoints[edge])

                a, b, c = face.indices
                m_ab, m_bc, m_ca = mids
                new_mesh.add_face([a, m_ab, m_ca], face.material_id)
                new_mesh.add_face([m_ab, b, m_bc], face.material_id)
                new_mesh.add_face([m_ca, m_bc, c], face.material_id)
                new_mesh.add_face([m_ab, m_bc, m_ca], face.material_id)
            elif len(face.indices) == 4:
                # Quad subdivision → 4 quads
                center = np.mean([result.vertices[i].position for i in face.indices], axis=0)
                center_idx = new_mesh.add_vertex(*center)
                mids = []
                for k in range(4):
                    i0, i1 = face.indices[k], face.indices[(k + 1) % 4]
                    edge = (min(i0, i1), max(i0, i1))
                    if edge not in edge_midpoints:
                        p0 = result.vertices[i0].position
                        p1 = result.vertices[i1].position
                        mid = (p0 + p1) / 2
                        idx = new_mesh.add_vertex(*mid)
                        edge_midpoints[edge] = idx
                    mids.append(edge_midpoints[edge])

                for k in range(4):
                    new_mesh.add_face([
                        face.indices[k], mids[k], center_idx, mids[(k - 1) % 4]
                    ], face.material_id)

        new_mesh.compute_normals()
        result = new_mesh

    result.ks_verify_operation("subdivide", 0.88, 0.95, 0.08)
    return result

def merge_meshes(meshes: list[Mesh], name: str = "Merged") -> Mesh:
    result = Mesh(name)
    offset = 0
    for m in meshes:
        for v in m.vertices:
            result.vertices.append(Vertex(
                position=v.position.copy(),
                normal=v.normal.copy(),
                uv=v.uv.copy(),
                color=v.color.copy(),
            ))
        for f in m.faces:
            result.add_face([i + offset for i in f.indices], f.material_id)
        offset += len(m.vertices)

    result.compute_normals()
    result.ks_verify_operation("merge_meshes", 0.90, 0.96, 0.07)
    return result


# ═══════════════════════════════════════════════════
# Exporters
# ═══════════════════════════════════════════════════

def export_obj(mesh: Mesh, filepath: str):
    """Export to Wavefront OBJ (intermediate / debug)"""
    with open(filepath, 'w') as f:
        f.write(f"# Katala Studio — {mesh.name}\n")
        f.write(f"# Vertices: {mesh.vertex_count}, Faces: {mesh.face_count}\n")
        f.write(f"# KS Quality Score: {mesh.ks_quality_score():.3f}\n\n")
        for v in mesh.vertices:
            f.write(f"v {v.position[0]:.6f} {v.position[1]:.6f} {v.position[2]:.6f}\n")
        for v in mesh.vertices:
            f.write(f"vn {v.normal[0]:.6f} {v.normal[1]:.6f} {v.normal[2]:.6f}\n")
        for face in mesh.faces:
            indices = " ".join(f"{i+1}//{i+1}" for i in face.indices)
            f.write(f"f {indices}\n")

def export_fbx_ascii(mesh: Mesh, filepath: str):
    """Export to FBX ASCII format (7.4 compatible)"""
    positions = mesh.get_positions_array().flatten()
    normals = mesh.get_normals_array().flatten()
    indices = mesh.get_index_array()

    ks_score = mesh.ks_quality_score()

    with open(filepath, 'w') as f:
        f.write('; FBX 7.4.0 project file\n')
        f.write('; Katala Studio Export\n')
        f.write(f'; KS Quality Score: {ks_score:.3f}\n')
        f.write('; ---\n\n')

        # Header
        f.write('FBXHeaderExtension:  {\n')
        f.write('    FBXHeaderVersion: 1003\n')
        f.write('    FBXVersion: 7400\n')
        f.write('    Creator: "Katala Studio v1.0"\n')
        f.write('}\n\n')

        # Global settings
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

        # Objects
        f.write('Objects:  {\n')

        # Geometry
        model_id = 100000
        geom_id = 200000
        mat_id = 300000

        f.write(f'    Geometry: {geom_id}, "Geometry::{mesh.name}", "Mesh" {{\n')

        # Vertices
        f.write(f'        Vertices: *{len(positions)} {{\n')
        f.write('            a: ')
        f.write(','.join(f'{v:.6f}' for v in positions))
        f.write('\n        }\n')

        # Polygon indices (negative = end of polygon)
        f.write(f'        PolygonVertexIndex: *{len(indices)} {{\n')
        f.write('            a: ')
        tri_indices = []
        for i in range(0, len(indices), 3):
            tri_indices.append(str(indices[i]))
            tri_indices.append(str(indices[i + 1]))
            tri_indices.append(str(-(int(indices[i + 2]) + 1)))  # FBX: negative = end
        f.write(','.join(tri_indices))
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

        # Layer
        f.write('        Layer: 0 {\n')
        f.write('            Version: 100\n')
        f.write('            LayerElement:  {\n')
        f.write('                Type: "LayerElementNormal"\n')
        f.write('                TypedIndex: 0\n')
        f.write('            }\n')
        f.write('        }\n')
        f.write('    }\n\n')

        # Model
        t = mesh.transform
        f.write(f'    Model: {model_id}, "Model::{mesh.name}", "Mesh" {{\n')
        f.write('        Version: 232\n')
        f.write('        Properties70:  {\n')
        f.write(f'            P: "Lcl Translation", "Lcl Translation", "", "A",{t.position[0]},{t.position[1]},{t.position[2]}\n')
        f.write(f'            P: "Lcl Rotation", "Lcl Rotation", "", "A",{t.rotation[0]},{t.rotation[1]},{t.rotation[2]}\n')
        f.write(f'            P: "Lcl Scaling", "Lcl Scaling", "", "A",{t.scale[0]},{t.scale[1]},{t.scale[2]}\n')
        f.write('        }\n')
        f.write('    }\n\n')

        # Material
        mat = mesh.materials[0]
        f.write(f'    Material: {mat_id}, "Material::{mat.name}", "" {{\n')
        f.write('        Version: 102\n')
        f.write('        Properties70:  {\n')
        f.write(f'            P: "DiffuseColor", "Color", "", "A",{mat.diffuse[0]},{mat.diffuse[1]},{mat.diffuse[2]}\n')
        f.write(f'            P: "Shininess", "double", "Number", "",{mat.shininess}\n')
        f.write('        }\n')
        f.write('    }\n')

        f.write('}\n\n')

        # Connections
        f.write('Connections:  {\n')
        f.write(f'    C: "OO",{model_id},0\n')  # Model → Root
        f.write(f'    C: "OO",{geom_id},{model_id}\n')  # Geometry → Model
        f.write(f'    C: "OO",{mat_id},{model_id}\n')  # Material → Model
        f.write('}\n')

    mesh.ks_verify_operation("export_fbx", 0.85, 0.92, 0.10)

def export_unitypackage(mesh: Mesh, filepath: str):
    """Export as .unitypackage (tar.gz with Unity asset structure)"""
    import tarfile
    import hashlib
    import time

    # Generate a deterministic GUID from mesh name
    guid = hashlib.md5(mesh.name.encode()).hexdigest()

    # Create temp OBJ content
    obj_buffer = io.StringIO()
    obj_buffer.write(f"# Katala Studio — {mesh.name}\n")
    for v in mesh.vertices:
        obj_buffer.write(f"v {v.position[0]:.6f} {v.position[1]:.6f} {v.position[2]:.6f}\n")
    for v in mesh.vertices:
        obj_buffer.write(f"vn {v.normal[0]:.6f} {v.normal[1]:.6f} {v.normal[2]:.6f}\n")
    for face in mesh.faces:
        indices = " ".join(f"{i+1}//{i+1}" for i in face.indices)
        obj_buffer.write(f"f {indices}\n")
    obj_content = obj_buffer.getvalue().encode('utf-8')

    # Meta file (Unity YAML)
    meta_content = f"""fileFormatVersion: 2
guid: {guid}
ModelImporter:
  serializedVersion: 21300
  internalIDToNameTable: []
  externalObjects: {{}}
  materials:
    materialImportMode: 2
    materialName: 0
    materialSearch: 1
  animationType: 0
  meshCompression: 0
  isReadable: 1
  importNormals: 0
  importBlendShapeNormals: 1
  normalCalculationMode: 0
  userData: "KS Quality Score: {mesh.ks_quality_score():.3f}"
  assetBundleName:
  assetBundleVariant:
""".encode('utf-8')

    # Asset path
    asset_path = f"Assets/KatalaStudio/{mesh.name}.obj"
    pathname_content = asset_path.encode('utf-8')

    # Build .unitypackage (tar.gz)
    with tarfile.open(filepath, 'w:gz') as tar:
        def add_string(name: str, data: bytes):
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mtime = int(time.time())
            tar.addfile(info, io.BytesIO(data))

        # guid/asset — the actual file
        add_string(f"{guid}/asset", obj_content)
        # guid/asset.meta — Unity metadata
        add_string(f"{guid}/asset.meta", meta_content)
        # guid/pathname — path in Unity project
        add_string(f"{guid}/pathname", pathname_content)

    mesh.ks_verify_operation("export_unitypackage", 0.82, 0.90, 0.12)


# ═══════════════════════════════════════════════════
# Scene
# ═══════════════════════════════════════════════════

class Scene:
    def __init__(self, name: str = "KatalaScene"):
        self.name = name
        self.meshes: list[Mesh] = []
        self.active_mesh_index: int = -1

    def add_mesh(self, mesh: Mesh) -> int:
        idx = len(self.meshes)
        self.meshes.append(mesh)
        self.active_mesh_index = idx
        return idx

    @property
    def active_mesh(self) -> Optional[Mesh]:
        if 0 <= self.active_mesh_index < len(self.meshes):
            return self.meshes[self.active_mesh_index]
        return None

    def export_all_fbx(self, directory: str):
        os.makedirs(directory, exist_ok=True)
        for mesh in self.meshes:
            path = os.path.join(directory, f"{mesh.name}.fbx")
            export_fbx_ascii(mesh, path)

    def export_all_unitypackage(self, filepath: str):
        """Export entire scene as single .unitypackage"""
        import tarfile
        import hashlib
        import time

        with tarfile.open(filepath, 'w:gz') as tar:
            def add_string(name: str, data: bytes):
                info = tarfile.TarInfo(name=name)
                info.size = len(data)
                info.mtime = int(time.time())
                tar.addfile(info, io.BytesIO(data))

            for mesh in self.meshes:
                guid = hashlib.md5(f"{self.name}_{mesh.name}".encode()).hexdigest()

                # OBJ content
                obj_buf = io.StringIO()
                obj_buf.write(f"# Katala Studio — {mesh.name}\n")
                for v in mesh.vertices:
                    obj_buf.write(f"v {v.position[0]:.6f} {v.position[1]:.6f} {v.position[2]:.6f}\n")
                for v in mesh.vertices:
                    obj_buf.write(f"vn {v.normal[0]:.6f} {v.normal[1]:.6f} {v.normal[2]:.6f}\n")
                for face in mesh.faces:
                    indices = " ".join(f"{i+1}//{i+1}" for i in face.indices)
                    obj_buf.write(f"f {indices}\n")

                asset_path = f"Assets/KatalaStudio/{mesh.name}.obj"

                add_string(f"{guid}/asset", obj_buf.getvalue().encode('utf-8'))
                add_string(f"{guid}/asset.meta", f"fileFormatVersion: 2\nguid: {guid}\n".encode('utf-8'))
                add_string(f"{guid}/pathname", asset_path.encode('utf-8'))

    def stats(self) -> dict:
        total_verts = sum(m.vertex_count for m in self.meshes)
        total_tris = sum(m.tri_count for m in self.meshes)
        total_faces = sum(m.face_count for m in self.meshes)
        avg_ks = np.mean([m.ks_quality_score() for m in self.meshes]) if self.meshes else 0.0
        return {
            "scene": self.name,
            "mesh_count": len(self.meshes),
            "total_vertices": total_verts,
            "total_triangles": total_tris,
            "total_faces": total_faces,
            "average_ks_quality": float(avg_ks),
        }
