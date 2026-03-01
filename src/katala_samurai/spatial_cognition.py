"""
3D Spatial Cognition Engine — Foundation for 3D modeling capabilities.

Youta: "3Dモデリング技術のための下地作りをしたい。まずは3D空間認知能力を与えたい"

Provides:
  1. 3D vector/matrix operations (transforms, projections)
  2. Spatial reasoning (containment, intersection, proximity)
  3. Shape recognition and classification
  4. Scene graph representation
  5. Mesh analysis (normals, curvature, topology)
  6. Camera/viewport projection

Youta context: WAIS-IV block design scaled score 17 (top ~0.1%).
This engine aims to formalize that spatial intuition computationally.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

VERSION = "1.0.0"


# ═══════════════════════════════════════════════════════════════
# Core 3D Primitives
# ═══════════════════════════════════════════════════════════════

@dataclass
class Vec3:
    """3D vector with full operations."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __add__(self, other: 'Vec3') -> 'Vec3':
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: 'Vec3') -> 'Vec3':
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> 'Vec3':
        return Vec3(self.x * scalar, self.y * scalar, self.z * scalar)

    def __rmul__(self, scalar: float) -> 'Vec3':
        return self.__mul__(scalar)

    def __neg__(self) -> 'Vec3':
        return Vec3(-self.x, -self.y, -self.z)

    def dot(self, other: 'Vec3') -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: 'Vec3') -> 'Vec3':
        return Vec3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def length(self) -> float:
        return math.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2)

    def normalized(self) -> 'Vec3':
        l = self.length()
        if l < 1e-10:
            return Vec3(0, 0, 0)
        return Vec3(self.x / l, self.y / l, self.z / l)

    def distance_to(self, other: 'Vec3') -> float:
        return (self - other).length()

    def angle_to(self, other: 'Vec3') -> float:
        """Angle between vectors in radians."""
        d = self.dot(other)
        l = self.length() * other.length()
        if l < 1e-10:
            return 0.0
        return math.acos(max(-1, min(1, d / l)))

    def lerp(self, other: 'Vec3', t: float) -> 'Vec3':
        """Linear interpolation."""
        return self + (other - self) * t

    def to_array(self) -> np.ndarray:
        return np.array([self.x, self.y, self.z])

    @staticmethod
    def from_array(arr) -> 'Vec3':
        return Vec3(float(arr[0]), float(arr[1]), float(arr[2]))

    def __repr__(self):
        return f"Vec3({self.x:.3f}, {self.y:.3f}, {self.z:.3f})"


@dataclass
class Quaternion:
    """Quaternion for rotation representation."""
    w: float = 1.0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    @staticmethod
    def from_axis_angle(axis: Vec3, angle: float) -> 'Quaternion':
        """Create quaternion from axis and angle (radians)."""
        half = angle / 2
        s = math.sin(half)
        a = axis.normalized()
        return Quaternion(math.cos(half), a.x * s, a.y * s, a.z * s)

    @staticmethod
    def from_euler(pitch: float, yaw: float, roll: float) -> 'Quaternion':
        """Create from Euler angles (radians)."""
        cy, sy = math.cos(yaw * 0.5), math.sin(yaw * 0.5)
        cp, sp = math.cos(pitch * 0.5), math.sin(pitch * 0.5)
        cr, sr = math.cos(roll * 0.5), math.sin(roll * 0.5)
        return Quaternion(
            cr * cp * cy + sr * sp * sy,
            sr * cp * cy - cr * sp * sy,
            cr * sp * cy + sr * cp * sy,
            cr * cp * sy - sr * sp * cy,
        )

    def normalize(self) -> 'Quaternion':
        n = math.sqrt(self.w**2 + self.x**2 + self.y**2 + self.z**2)
        if n < 1e-10:
            return Quaternion()
        return Quaternion(self.w/n, self.x/n, self.y/n, self.z/n)

    def conjugate(self) -> 'Quaternion':
        return Quaternion(self.w, -self.x, -self.y, -self.z)

    def __mul__(self, other: 'Quaternion') -> 'Quaternion':
        return Quaternion(
            self.w*other.w - self.x*other.x - self.y*other.y - self.z*other.z,
            self.w*other.x + self.x*other.w + self.y*other.z - self.z*other.y,
            self.w*other.y - self.x*other.z + self.y*other.w + self.z*other.x,
            self.w*other.z + self.x*other.y - self.y*other.x + self.z*other.w,
        )

    def rotate(self, v: Vec3) -> Vec3:
        """Rotate a vector by this quaternion."""
        q = self.normalize()
        p = Quaternion(0, v.x, v.y, v.z)
        result = q * p * q.conjugate()
        return Vec3(result.x, result.y, result.z)

    def to_matrix(self) -> np.ndarray:
        """Convert to 3×3 rotation matrix."""
        q = self.normalize()
        return np.array([
            [1-2*(q.y**2+q.z**2), 2*(q.x*q.y-q.z*q.w), 2*(q.x*q.z+q.y*q.w)],
            [2*(q.x*q.y+q.z*q.w), 1-2*(q.x**2+q.z**2), 2*(q.y*q.z-q.x*q.w)],
            [2*(q.x*q.z-q.y*q.w), 2*(q.y*q.z+q.x*q.w), 1-2*(q.x**2+q.y**2)],
        ])

    def slerp(self, other: 'Quaternion', t: float) -> 'Quaternion':
        """Spherical linear interpolation."""
        dot = self.w*other.w + self.x*other.x + self.y*other.y + self.z*other.z
        if dot < 0:
            other = Quaternion(-other.w, -other.x, -other.y, -other.z)
            dot = -dot
        if dot > 0.9995:
            # Linear interpolation for very close quaternions
            result = Quaternion(
                self.w + t*(other.w - self.w),
                self.x + t*(other.x - self.x),
                self.y + t*(other.y - self.y),
                self.z + t*(other.z - self.z),
            )
            return result.normalize()
        theta = math.acos(dot)
        sin_theta = math.sin(theta)
        a = math.sin((1 - t) * theta) / sin_theta
        b = math.sin(t * theta) / sin_theta
        return Quaternion(
            a*self.w + b*other.w, a*self.x + b*other.x,
            a*self.y + b*other.y, a*self.z + b*other.z,
        )


@dataclass
class Transform:
    """3D transform: position + rotation + scale."""
    position: Vec3 = field(default_factory=Vec3)
    rotation: Quaternion = field(default_factory=Quaternion)
    scale: Vec3 = field(default_factory=lambda: Vec3(1, 1, 1))

    def to_matrix(self) -> np.ndarray:
        """4×4 transformation matrix."""
        rot = self.rotation.to_matrix()
        m = np.eye(4)
        m[:3, :3] = rot * np.array([
            [self.scale.x, self.scale.y, self.scale.z]
        ])
        m[:3, 3] = [self.position.x, self.position.y, self.position.z]
        return m

    def transform_point(self, point: Vec3) -> Vec3:
        """Apply transform to a point."""
        scaled = Vec3(point.x * self.scale.x, point.y * self.scale.y,
                      point.z * self.scale.z)
        rotated = self.rotation.rotate(scaled)
        return rotated + self.position


# ═══════════════════════════════════════════════════════════════
# Bounding Volumes
# ═══════════════════════════════════════════════════════════════

@dataclass
class AABB:
    """Axis-Aligned Bounding Box."""
    min_point: Vec3 = field(default_factory=Vec3)
    max_point: Vec3 = field(default_factory=Vec3)

    @property
    def center(self) -> Vec3:
        return self.min_point.lerp(self.max_point, 0.5)

    @property
    def size(self) -> Vec3:
        return self.max_point - self.min_point

    @property
    def volume(self) -> float:
        s = self.size
        return abs(s.x * s.y * s.z)

    def contains_point(self, p: Vec3) -> bool:
        return (self.min_point.x <= p.x <= self.max_point.x and
                self.min_point.y <= p.y <= self.max_point.y and
                self.min_point.z <= p.z <= self.max_point.z)

    def intersects(self, other: 'AABB') -> bool:
        return (self.min_point.x <= other.max_point.x and
                self.max_point.x >= other.min_point.x and
                self.min_point.y <= other.max_point.y and
                self.max_point.y >= other.min_point.y and
                self.min_point.z <= other.max_point.z and
                self.max_point.z >= other.min_point.z)

    def expand(self, point: Vec3) -> 'AABB':
        return AABB(
            Vec3(min(self.min_point.x, point.x),
                 min(self.min_point.y, point.y),
                 min(self.min_point.z, point.z)),
            Vec3(max(self.max_point.x, point.x),
                 max(self.max_point.y, point.y),
                 max(self.max_point.z, point.z)),
        )

    @staticmethod
    def from_points(points: List[Vec3]) -> 'AABB':
        if not points:
            return AABB()
        xs = [p.x for p in points]
        ys = [p.y for p in points]
        zs = [p.z for p in points]
        return AABB(
            Vec3(min(xs), min(ys), min(zs)),
            Vec3(max(xs), max(ys), max(zs)),
        )


@dataclass
class BoundingSphere:
    """Bounding sphere for quick proximity tests."""
    center: Vec3 = field(default_factory=Vec3)
    radius: float = 0.0

    def contains_point(self, p: Vec3) -> bool:
        return self.center.distance_to(p) <= self.radius

    def intersects(self, other: 'BoundingSphere') -> bool:
        dist = self.center.distance_to(other.center)
        return dist <= self.radius + other.radius


# ═══════════════════════════════════════════════════════════════
# Ray casting & intersection
# ═══════════════════════════════════════════════════════════════

@dataclass
class Ray:
    """A ray with origin and direction."""
    origin: Vec3 = field(default_factory=Vec3)
    direction: Vec3 = field(default_factory=lambda: Vec3(0, 0, -1))

    def point_at(self, t: float) -> Vec3:
        return self.origin + self.direction * t

    def intersect_aabb(self, aabb: AABB) -> Optional[float]:
        """Ray-AABB intersection. Returns distance or None."""
        d = self.direction
        o = self.origin
        tmin = -math.inf
        tmax = math.inf

        for axis in range(3):
            d_val = [d.x, d.y, d.z][axis]
            o_val = [o.x, o.y, o.z][axis]
            mn = [aabb.min_point.x, aabb.min_point.y, aabb.min_point.z][axis]
            mx = [aabb.max_point.x, aabb.max_point.y, aabb.max_point.z][axis]

            if abs(d_val) < 1e-10:
                if o_val < mn or o_val > mx:
                    return None
            else:
                t1 = (mn - o_val) / d_val
                t2 = (mx - o_val) / d_val
                if t1 > t2:
                    t1, t2 = t2, t1
                tmin = max(tmin, t1)
                tmax = min(tmax, t2)
                if tmin > tmax:
                    return None

        return tmin if tmin >= 0 else (tmax if tmax >= 0 else None)

    def intersect_sphere(self, center: Vec3, radius: float) -> Optional[float]:
        """Ray-sphere intersection."""
        oc = self.origin - center
        a = self.direction.dot(self.direction)
        b = 2 * oc.dot(self.direction)
        c = oc.dot(oc) - radius * radius
        disc = b * b - 4 * a * c
        if disc < 0:
            return None
        t = (-b - math.sqrt(disc)) / (2 * a)
        if t < 0:
            t = (-b + math.sqrt(disc)) / (2 * a)
        return t if t >= 0 else None

    def intersect_plane(self, normal: Vec3, d: float) -> Optional[float]:
        """Ray-plane intersection. Plane: normal · p + d = 0."""
        denom = normal.dot(self.direction)
        if abs(denom) < 1e-10:
            return None
        t = -(normal.dot(self.origin) + d) / denom
        return t if t >= 0 else None

    def intersect_triangle(self, v0: Vec3, v1: Vec3, v2: Vec3) -> Optional[float]:
        """Möller-Trumbore ray-triangle intersection."""
        edge1 = v1 - v0
        edge2 = v2 - v0
        h = self.direction.cross(edge2)
        a = edge1.dot(h)
        if abs(a) < 1e-10:
            return None
        f = 1.0 / a
        s = self.origin - v0
        u = f * s.dot(h)
        if u < 0.0 or u > 1.0:
            return None
        q = s.cross(edge1)
        v = f * self.direction.dot(q)
        if v < 0.0 or u + v > 1.0:
            return None
        t = f * edge2.dot(q)
        return t if t > 1e-10 else None


# ═══════════════════════════════════════════════════════════════
# Mesh representation & analysis
# ═══════════════════════════════════════════════════════════════

@dataclass
class Mesh:
    """Triangle mesh with vertices and face indices."""
    vertices: np.ndarray  # (N, 3) float
    faces: np.ndarray     # (M, 3) int — triangle indices

    @property
    def n_vertices(self) -> int:
        return len(self.vertices)

    @property
    def n_faces(self) -> int:
        return len(self.faces)

    def face_normals(self) -> np.ndarray:
        """Compute per-face normals."""
        v0 = self.vertices[self.faces[:, 0]]
        v1 = self.vertices[self.faces[:, 1]]
        v2 = self.vertices[self.faces[:, 2]]
        e1 = v1 - v0
        e2 = v2 - v0
        normals = np.cross(e1, e2)
        lengths = np.linalg.norm(normals, axis=1, keepdims=True)
        lengths[lengths < 1e-10] = 1.0
        return normals / lengths

    def vertex_normals(self) -> np.ndarray:
        """Compute per-vertex normals (averaged from faces)."""
        fn = self.face_normals()
        vn = np.zeros_like(self.vertices)
        for i, face in enumerate(self.faces):
            for vi in face:
                vn[vi] += fn[i]
        lengths = np.linalg.norm(vn, axis=1, keepdims=True)
        lengths[lengths < 1e-10] = 1.0
        return vn / lengths

    def face_areas(self) -> np.ndarray:
        """Compute per-face areas."""
        v0 = self.vertices[self.faces[:, 0]]
        v1 = self.vertices[self.faces[:, 1]]
        v2 = self.vertices[self.faces[:, 2]]
        return 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1)

    def total_surface_area(self) -> float:
        return float(np.sum(self.face_areas()))

    def bounding_box(self) -> AABB:
        mn = self.vertices.min(axis=0)
        mx = self.vertices.max(axis=0)
        return AABB(Vec3(*mn), Vec3(*mx))

    def edge_set(self) -> Set[Tuple[int, int]]:
        """Get all unique edges."""
        edges = set()
        for face in self.faces:
            for i in range(3):
                e = tuple(sorted([int(face[i]), int(face[(i+1)%3])]))
                edges.add(e)
        return edges

    def euler_characteristic(self) -> int:
        """V - E + F = χ (2 for closed manifold, sphere topology)."""
        return self.n_vertices - len(self.edge_set()) + self.n_faces

    def is_manifold(self) -> bool:
        """Check if mesh is manifold (each edge shared by exactly 2 faces)."""
        from collections import Counter
        edge_count = Counter()
        for face in self.faces:
            for i in range(3):
                e = tuple(sorted([int(face[i]), int(face[(i+1)%3])]))
                edge_count[e] += 1
        return all(c == 2 for c in edge_count.values())

    def center_of_mass(self) -> Vec3:
        """Approximate center of mass (assumes uniform density)."""
        c = self.vertices.mean(axis=0)
        return Vec3(*c)

    @staticmethod
    def create_box(width=1.0, height=1.0, depth=1.0) -> 'Mesh':
        """Create a box mesh."""
        w, h, d = width/2, height/2, depth/2
        verts = np.array([
            [-w,-h,-d], [w,-h,-d], [w,h,-d], [-w,h,-d],
            [-w,-h,d], [w,-h,d], [w,h,d], [-w,h,d],
        ], dtype=np.float64)
        faces = np.array([
            [0,1,2], [0,2,3], [4,6,5], [4,7,6],
            [0,4,5], [0,5,1], [2,6,7], [2,7,3],
            [0,3,7], [0,7,4], [1,5,6], [1,6,2],
        ], dtype=np.int32)
        return Mesh(verts, faces)

    @staticmethod
    def create_sphere(radius=1.0, segments=16, rings=12) -> 'Mesh':
        """Create a UV sphere mesh."""
        verts = []
        faces = []
        for i in range(rings + 1):
            phi = math.pi * i / rings
            for j in range(segments):
                theta = 2 * math.pi * j / segments
                x = radius * math.sin(phi) * math.cos(theta)
                y = radius * math.cos(phi)
                z = radius * math.sin(phi) * math.sin(theta)
                verts.append([x, y, z])
        verts = np.array(verts, dtype=np.float64)

        for i in range(rings):
            for j in range(segments):
                p1 = i * segments + j
                p2 = i * segments + (j + 1) % segments
                p3 = (i + 1) * segments + j
                p4 = (i + 1) * segments + (j + 1) % segments
                faces.append([p1, p3, p2])
                faces.append([p2, p3, p4])
        faces = np.array(faces, dtype=np.int32)
        return Mesh(verts, faces)


# ═══════════════════════════════════════════════════════════════
# Camera & Projection
# ═══════════════════════════════════════════════════════════════

@dataclass
class Camera:
    """Camera with view and projection."""
    position: Vec3 = field(default_factory=lambda: Vec3(0, 0, 5))
    target: Vec3 = field(default_factory=Vec3)
    up: Vec3 = field(default_factory=lambda: Vec3(0, 1, 0))
    fov: float = 60.0  # degrees
    aspect: float = 16 / 9
    near: float = 0.1
    far: float = 100.0

    def view_matrix(self) -> np.ndarray:
        """Compute 4×4 view matrix (look-at)."""
        f = (self.target - self.position).normalized()
        s = f.cross(self.up.normalized()).normalized()
        u = s.cross(f)

        m = np.eye(4)
        m[0, :3] = [s.x, s.y, s.z]
        m[1, :3] = [u.x, u.y, u.z]
        m[2, :3] = [-f.x, -f.y, -f.z]
        m[0, 3] = -s.dot(self.position)
        m[1, 3] = -u.dot(self.position)
        m[2, 3] = f.dot(self.position)
        return m

    def projection_matrix(self) -> np.ndarray:
        """Compute 4×4 perspective projection matrix."""
        fov_rad = math.radians(self.fov)
        f = 1.0 / math.tan(fov_rad / 2)
        m = np.zeros((4, 4))
        m[0, 0] = f / self.aspect
        m[1, 1] = f
        m[2, 2] = (self.far + self.near) / (self.near - self.far)
        m[2, 3] = (2 * self.far * self.near) / (self.near - self.far)
        m[3, 2] = -1
        return m

    def project_point(self, world_point: Vec3) -> Optional[Tuple[float, float, float]]:
        """Project 3D point to normalized screen coordinates.

        Returns (x, y, depth) in [-1, 1] range, or None if behind camera.
        """
        v = self.view_matrix()
        p = self.projection_matrix()
        mvp = p @ v

        point = np.array([world_point.x, world_point.y, world_point.z, 1.0])
        clip = mvp @ point

        if clip[3] <= 0:
            return None

        ndc = clip[:3] / clip[3]
        return (float(ndc[0]), float(ndc[1]), float(ndc[2]))

    def screen_ray(self, screen_x: float, screen_y: float) -> Ray:
        """Generate a ray from screen coordinates (normalized [-1, 1])."""
        inv_proj = np.linalg.inv(self.projection_matrix())
        inv_view = np.linalg.inv(self.view_matrix())

        near_point = inv_proj @ np.array([screen_x, screen_y, -1, 1])
        far_point = inv_proj @ np.array([screen_x, screen_y, 1, 1])

        near_point = near_point[:3] / near_point[3]
        far_point = far_point[:3] / far_point[3]

        near_world = (inv_view @ np.append(near_point, 1))[:3]
        far_world = (inv_view @ np.append(far_point, 1))[:3]

        direction = far_world - near_world
        length = np.linalg.norm(direction)
        if length > 0:
            direction /= length

        return Ray(Vec3(*near_world), Vec3(*direction))


# ═══════════════════════════════════════════════════════════════
# Scene Graph
# ═══════════════════════════════════════════════════════════════

@dataclass
class SceneNode:
    """Node in a scene graph hierarchy."""
    name: str
    transform: Transform = field(default_factory=Transform)
    mesh: Optional[Mesh] = None
    children: List['SceneNode'] = field(default_factory=list)
    visible: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_child(self, child: 'SceneNode') -> 'SceneNode':
        self.children.append(child)
        return child

    def find(self, name: str) -> Optional['SceneNode']:
        """Find node by name (depth-first)."""
        if self.name == name:
            return self
        for child in self.children:
            found = child.find(name)
            if found:
                return found
        return None

    def world_transform(self, parent_matrix: Optional[np.ndarray] = None) -> np.ndarray:
        """Compute world transform (accumulated from parent)."""
        local = self.transform.to_matrix()
        if parent_matrix is not None:
            return parent_matrix @ local
        return local

    def flatten(self) -> List['SceneNode']:
        """Flatten scene graph into list."""
        result = [self]
        for child in self.children:
            result.extend(child.flatten())
        return result

    def stats(self) -> Dict[str, int]:
        """Get scene statistics."""
        nodes = self.flatten()
        total_verts = sum(n.mesh.n_vertices for n in nodes if n.mesh)
        total_faces = sum(n.mesh.n_faces for n in nodes if n.mesh)
        return {
            'nodes': len(nodes),
            'meshes': sum(1 for n in nodes if n.mesh),
            'vertices': total_verts,
            'faces': total_faces,
        }


# ═══════════════════════════════════════════════════════════════
# Spatial reasoning
# ═══════════════════════════════════════════════════════════════

class SpatialReasoner:
    """High-level spatial reasoning operations."""

    @staticmethod
    def relative_position(a: Vec3, b: Vec3) -> Dict[str, Any]:
        """Describe relative position of b from a's perspective."""
        diff = b - a
        dist = diff.length()
        if dist < 1e-6:
            return {'relation': 'coincident', 'distance': 0}

        d = diff.normalized()
        relations = []
        if d.x > 0.3: relations.append('right')
        elif d.x < -0.3: relations.append('left')
        if d.y > 0.3: relations.append('above')
        elif d.y < -0.3: relations.append('below')
        if d.z > 0.3: relations.append('behind')
        elif d.z < -0.3: relations.append('in_front')

        return {
            'relations': relations,
            'distance': round(dist, 4),
            'direction': {'x': round(d.x, 3), 'y': round(d.y, 3), 'z': round(d.z, 3)},
        }

    @staticmethod
    def closest_pair(points: List[Vec3]) -> Tuple[int, int, float]:
        """Find closest pair of points."""
        min_dist = math.inf
        best = (0, 1)
        for i in range(len(points)):
            for j in range(i + 1, len(points)):
                d = points[i].distance_to(points[j])
                if d < min_dist:
                    min_dist = d
                    best = (i, j)
        return best[0], best[1], min_dist

    @staticmethod
    def convex_hull_2d(points: List[Vec3]) -> List[int]:
        """Compute 2D convex hull (XZ plane) using Graham scan.

        Returns indices of hull vertices in CCW order.
        """
        if len(points) < 3:
            return list(range(len(points)))

        # Find lowest-rightmost point
        start = 0
        for i in range(1, len(points)):
            if (points[i].z < points[start].z or
                (points[i].z == points[start].z and points[i].x > points[start].x)):
                start = i

        def polar_angle(i):
            dx = points[i].x - points[start].x
            dz = points[i].z - points[start].z
            return math.atan2(dz, dx)

        indices = list(range(len(points)))
        indices.remove(start)
        indices.sort(key=polar_angle)
        indices = [start] + indices

        hull = []
        for idx in indices:
            while len(hull) >= 2:
                a = points[hull[-2]]
                b = points[hull[-1]]
                c = points[idx]
                cross = (b.x - a.x) * (c.z - a.z) - (b.z - a.z) * (c.x - a.x)
                if cross <= 0:
                    hull.pop()
                else:
                    break
            hull.append(idx)
        return hull

    @staticmethod
    def point_in_triangle_3d(p: Vec3, v0: Vec3, v1: Vec3, v2: Vec3) -> bool:
        """Test if point lies within triangle (barycentric coordinates)."""
        e0 = v1 - v0
        e1 = v2 - v0
        ep = p - v0
        d00 = e0.dot(e0)
        d01 = e0.dot(e1)
        d11 = e1.dot(e1)
        d20 = ep.dot(e0)
        d21 = ep.dot(e1)
        denom = d00 * d11 - d01 * d01
        if abs(denom) < 1e-10:
            return False
        v = (d11 * d20 - d01 * d21) / denom
        w = (d00 * d21 - d01 * d20) / denom
        u = 1 - v - w
        return u >= 0 and v >= 0 and w >= 0


def get_status() -> Dict[str, Any]:
    return {
        'version': VERSION,
        'engine': 'SpatialCognition',
        'primitives': ['Vec3', 'Quaternion', 'Transform', 'AABB', 'BoundingSphere', 'Ray'],
        'mesh_ops': [
            'face_normals', 'vertex_normals', 'face_areas', 'surface_area',
            'bounding_box', 'edge_set', 'euler_characteristic', 'is_manifold',
            'center_of_mass',
        ],
        'camera': ['view_matrix', 'projection_matrix', 'project_point', 'screen_ray'],
        'intersection': ['ray-AABB', 'ray-sphere', 'ray-plane', 'ray-triangle'],
        'reasoning': ['relative_position', 'closest_pair', 'convex_hull_2d', 'point_in_triangle'],
        'generators': ['box', 'sphere'],
        'scene_graph': True,
    }
