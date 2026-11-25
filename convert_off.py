#!/usr/bin/env python3
"""Convert 3D/4D .off files in-place into *_poly.off meshes for PolyMesh4D."""

from __future__ import annotations

import argparse
import glob
import math
import os
import time
from collections import defaultdict, deque

SKIP_SUFFIXES = ("_poly.off", "_tri.off", "_fixed.off")
MIN_CELL_FACES = 4
MAX_CELL_CHUNK_FACES = 16


def dot4(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3]


def sub4(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> tuple[float, float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2], a[3] - b[3])


def dist_sq4(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    d = sub4(a, b)
    return dot4(d, d)


def norm4(v: tuple[float, float, float, float]) -> tuple[float, float, float, float] | None:
    length = math.hypot(v[0], v[1], v[2], v[3])
    if length < 1e-12:
        return None
    inv = 1.0 / length
    return (v[0] * inv, v[1] * inv, v[2] * inv, v[3] * inv)


def hyperplane_normal_4d(
    u: tuple[float, float, float, float],
    v: tuple[float, float, float, float],
    w: tuple[float, float, float, float],
) -> tuple[float, float, float, float] | None:
    ux, uy, uz, uw = u
    vx, vy, vz, vw = v
    wx, wy, wz, ww = w

    def det3(
        a1: float, a2: float, a3: float,
        b1: float, b2: float, b3: float,
        c1: float, c2: float, c3: float,
    ) -> float:
        return (
            a1 * (b2 * c3 - b3 * c2)
            - a2 * (b1 * c3 - b3 * c1)
            + a3 * (b1 * c2 - b2 * c1)
        )

    nx = det3(uy, uz, uw, vy, vz, vw, wy, wz, ww)
    ny = -det3(ux, uz, uw, vx, vz, vw, wx, wz, ww)
    nz = det3(ux, uy, uw, vx, vy, vw, wx, wy, ww)
    nw = -det3(ux, uy, uz, vx, vy, vz, wx, wy, wz)
    return norm4((nx, ny, nz, nw))


def canonical_plane(
    normal: tuple[float, float, float, float],
    point: tuple[float, float, float, float],
) -> tuple[tuple[float, float, float, float], float]:
    nx, ny, nz, nw = normal
    d = dot4(normal, point)
    for c in (nx, ny, nz, nw, d):
        if abs(c) > 1e-9:
            if c < 0.0:
                return ((-nx, -ny, -nz, -nw), -d)
            return ((nx, ny, nz, nw), d)
    return ((nx, ny, nz, nw), d)


def face_edges(face: list[int]) -> list[tuple[int, int]]:
    m = len(face)
    out: list[tuple[int, int]] = []
    for i in range(m):
        a, b = face[i], face[(i + 1) % m]
        out.append((a, b) if a < b else (b, a))
    return out


def order_cell_faces_by_shared_edges(
    face_indices: list[int],
    faces: list[list[int]],
) -> list[int] | None:
    """Order >=4 faces via shared edges so cell[0] and cell[1] share an edge."""
    unique_f = list(dict.fromkeys(face_indices))
    if len(unique_f) < MIN_CELL_FACES:
        return None

    f_set = set(unique_f)
    edge_to_faces: dict[tuple[int, int], list[int]] = defaultdict(list)
    for f_idx in unique_f:
        for edge in face_edges(faces[f_idx]):
            edge_to_faces[edge].append(f_idx)

    adj: dict[int, list[int]] = {f_idx: [] for f_idx in unique_f}
    start_a: int | None = None
    start_b: int | None = None

    for owners in edge_to_faces.values():
        if len(owners) > 1:
            base = owners[0]
            if start_a is None:
                start_a = base
                start_b = owners[1]
            for other in owners[1:]:
                adj[base].append(other)
                adj[other].append(base)

    if start_a is None or start_b is None:
        return None

    ordered: list[int] = [start_a, start_b]
    visited: set[int] = {start_a, start_b}
    queue: deque[int] = deque([start_a, start_b])

    while queue:
        cur = queue.popleft()
        for nxt in adj[cur]:
            if nxt in f_set and nxt not in visited:
                visited.add(nxt)
                ordered.append(nxt)
                queue.append(nxt)

    for f_idx in unique_f:
        if f_idx not in visited:
            ordered.append(f_idx)

    if len(ordered) < MIN_CELL_FACES:
        return None

    return ordered


def is_valid_face(
    face: list[int],
    verts: list[tuple[float, float, float, float]],
    clean_degenerate: bool = True,
) -> bool:
    num_v = len(verts)
    if len(face) < 3 or any(idx < 0 or idx >= num_v for idx in face):
        return False
    if not clean_degenerate:
        return True
    if len(set(face)) < 3:
        return False
    p0 = verts[face[0]]
    p1 = verts[face[1]]
    p2 = verts[face[2]]
    if dist_sq4(p0, p1) < 1e-14 or dist_sq4(p0, p2) < 1e-14 or dist_sq4(p1, p2) < 1e-14:
        return False
    return True


def build_faces_from_shortest_edges(
    verts: list[tuple[float, float, float, float]],
) -> list[list[int]]:
    n = len(verts)
    if n < 3:
        return []

    min_d2 = float("inf")
    pairs: list[tuple[int, int, float]] = []

    for i in range(n):
        vi = verts[i]
        for j in range(i + 1, n):
            d2 = dist_sq4(vi, verts[j])
            if d2 > 1e-12:
                pairs.append((i, j, d2))
                if d2 < min_d2:
                    min_d2 = d2

    if not math.isfinite(min_d2):
        return []

    tol = max(1e-7, min_d2 * 1e-3)
    adj: list[set[int]] = [set() for _ in range(n)]
    for i, j, d2 in pairs:
        if abs(d2 - min_d2) <= tol:
            adj[i].add(j)
            adj[j].add(i)

    faces: list[list[int]] = []
    for i in range(n):
        adj_i = adj[i]
        for j in adj_i:
            if j <= i:
                continue
            for k in adj_i.intersection(adj[j]):
                if k > j:
                    faces.append([i, j, k])
    return faces


def partition_component_into_cells(
    comp: list[int],
    faces: list[list[int]],
    chunk_size: int = MAX_CELL_CHUNK_FACES,
) -> list[list[int]]:
    """Split a connected face component into edge-ordered cells of >=4 faces."""
    if len(comp) < MIN_CELL_FACES:
        return []

    if len(comp) <= chunk_size:
        ordered = order_cell_faces_by_shared_edges(comp, faces)
        return [ordered] if ordered is not None else []

    walked = order_cell_faces_by_shared_edges(comp, faces) or comp
    cells: list[list[int]] = []
    idx = 0
    total = len(walked)

    while idx < total:
        rem = total - idx
        if rem < MIN_CELL_FACES:
            if cells:
                merged = order_cell_faces_by_shared_edges(cells[-1] + walked[idx:], faces)
                if merged is not None:
                    cells[-1] = merged
            break

        take = chunk_size if rem > chunk_size + (MIN_CELL_FACES - 1) else rem
        chunk = walked[idx : idx + take]
        ordered = order_cell_faces_by_shared_edges(chunk, faces)
        if ordered is not None:
            cells.append(ordered)
        idx += take

    return cells


def connected_face_component_cells(faces: list[list[int]]) -> list[list[int]]:
    if len(faces) < MIN_CELL_FACES:
        return []

    edge_owners: dict[tuple[int, int], list[int]] = defaultdict(list)
    for f_idx, face in enumerate(faces):
        for edge in face_edges(face):
            edge_owners[edge].append(f_idx)

    adj: list[list[int]] = [[] for _ in range(len(faces))]
    for owners in edge_owners.values():
        if len(owners) > 1:
            base = owners[0]
            for other in owners[1:]:
                adj[base].append(other)
                adj[other].append(base)

    visited = [False] * len(faces)
    cells: list[list[int]] = []
    leftover_faces: list[int] = []

    for start in range(len(faces)):
        if visited[start]:
            continue
        comp: list[int] = []
        queue = deque([start])
        visited[start] = True
        while queue:
            cur = queue.popleft()
            comp.append(cur)
            for nxt in adj[cur]:
                if not visited[nxt]:
                    visited[nxt] = True
                    queue.append(nxt)

        if len(comp) >= MIN_CELL_FACES:
            cells.extend(partition_component_into_cells(comp, faces))
        else:
            leftover_faces.extend(comp)

    if len(leftover_faces) >= MIN_CELL_FACES:
        cells.extend(partition_component_into_cells(leftover_faces, faces))

    return cells


def find_3d_cells_for_convex_polytope(
    verts: list[tuple[float, float, float, float]],
    faces: list[list[int]],
    max_hyperplane_faces: int = 1500,
    max_plane_checks: int = 25000,
) -> list[list[int]]:
    """Fast 4D hyperplane cell detection via edge-incident faces."""
    num_faces = len(faces)
    num_verts = len(verts)
    if num_faces < MIN_CELL_FACES or num_verts < MIN_CELL_FACES:
        return []

    if num_faces > max_hyperplane_faces:
        return connected_face_component_cells(faces)

    edge_to_faces: dict[tuple[int, int], list[int]] = defaultdict(list)
    for f_idx, face in enumerate(faces):
        for edge in face_edges(face):
            edge_to_faces[edge].append(f_idx)

    seen_planes: set[tuple[float, float, float, float, float]] = set()
    seen_cell_sets: set[frozenset[int]] = set()
    ordered_cells: list[list[int]] = []
    plane_tol = 2e-3
    checks = 0
    stop = False

    for (va, vb), adj_faces in edge_to_faces.items():
        if len(adj_faces) < 2:
            continue

        p0 = verts[va]
        e_vec = sub4(verts[vb], p0)

        off_vecs: list[tuple[float, float, float, float]] = []
        for f_idx in adj_faces:
            cand = next((v for v in faces[f_idx] if v != va and v != vb), None)
            if cand is not None:
                off_vecs.append(sub4(verts[cand], p0))

        m_vecs = len(off_vecs)
        for i in range(m_vecs):
            u_vec = off_vecs[i]
            for j in range(i + 1, m_vecs):
                checks += 1
                if checks > max_plane_checks:
                    stop = True
                    break

                normal = hyperplane_normal_4d(e_vec, u_vec, off_vecs[j])
                if normal is None:
                    continue

                c_normal, d = canonical_plane(normal, p0)
                plane_key = (
                    round(c_normal[0], 5),
                    round(c_normal[1], 5),
                    round(c_normal[2], 5),
                    round(c_normal[3], 5),
                    round(d, 5),
                )
                if plane_key in seen_planes:
                    continue
                seen_planes.add(plane_key)

                on_plane = [abs(dot4(c_normal, v) - d) <= plane_tol for v in verts]
                coplanar_faces = [
                    check_idx
                    for check_idx, check_face in enumerate(faces)
                    if all(on_plane[v] for v in check_face)
                ]

                if len(coplanar_faces) >= MIN_CELL_FACES:
                    c_key = frozenset(coplanar_faces)
                    if c_key not in seen_cell_sets:
                        ordered = order_cell_faces_by_shared_edges(coplanar_faces, faces)
                        if ordered is not None:
                            seen_cell_sets.add(c_key)
                            ordered_cells.append(ordered)

            if stop:
                break
        if stop:
            break

    if not ordered_cells:
        return connected_face_component_cells(faces)

    return ordered_cells


def transform_vertices(
    verts: list[tuple[float, float, float, float]],
    scale: float = 1.0,
    center: bool = False,
) -> list[tuple[float, float, float, float]]:
    if not verts or (scale == 1.0 and not center):
        return verts

    if center:
        cx = sum(v[0] for v in verts) / len(verts)
        cy = sum(v[1] for v in verts) / len(verts)
        cz = sum(v[2] for v in verts) / len(verts)
        cw = sum(v[3] for v in verts) / len(verts)
    else:
        cx = cy = cz = cw = 0.0

    return [
        (
            (x - cx) * scale,
            (y - cy) * scale,
            (z - cz) * scale,
            (w - cw) * scale,
        )
        for x, y, z, w in verts
    ]


def convert_off_to_poly_off(
    input_path: str,
    default_w: float = 0.0,
    max_reconstruct_verts: int = 256,
    max_hyperplane_faces: int = 1500,
    max_plane_checks: int = 25000,
    fast_only: bool = False,
    clean_degenerate: bool = True,
    scale: float = 1.0,
    center: bool = False,
) -> None:
    if input_path.endswith(SKIP_SUFFIXES):
        return

    t0 = time.perf_counter()
    with open(input_path, "r", encoding="utf-8", errors="replace") as f:
        lines: list[str] = []
        for raw_line in f:
            before_comment, _, _ = raw_line.replace("\r", "").partition("#")
            clean = before_comment.strip()
            if clean:
                lines.append(clean)

    if len(lines) < 2:
        return

    it = iter(lines)
    header = next(it)
    first_parts = header.split()
    first_word, *rest_first = first_parts

    if first_word in ("OFF", "4OFF", "3OFF", "NOFF", "4NOFF"):
        counts_parts = rest_first if len(rest_first) >= 2 else next(it).split()
    else:
        counts_parts = first_parts

    if len(counts_parts) < 2:
        return

    vert_count = int(counts_parts[0])
    face_count = int(counts_parts[1])
    extra_counts = counts_parts[2:]
    existing_cell_count = int(extra_counts[1]) if len(extra_counts) >= 2 else 0

    verts: list[tuple[float, float, float, float]] = []
    for _ in range(vert_count):
        try:
            parts = next(it).split()
        except StopIteration:
            break
        if len(parts) < 3:
            continue
        x = float(parts[0])
        y = float(parts[1])
        z = float(parts[2])
        w = float(parts[3]) if len(parts) >= 4 else default_w
        verts.append((x, y, z, w))

    verts = transform_vertices(verts, scale=scale, center=center)

    faces: list[list[int]] = []
    for _ in range(face_count):
        try:
            parts = next(it).split()
        except StopIteration:
            break
        if not parts:
            continue
        n = int(parts[0])
        indices = parts[1:]
        if n < 3 or len(indices) < n:
            continue
        parsed = [int(idx) for idx in indices[:n]]
        if is_valid_face(parsed, verts, clean_degenerate=clean_degenerate):
            faces.append(parsed)

    if not faces and 3 <= len(verts) <= max_reconstruct_verts:
        faces = [
            f for f in build_faces_from_shortest_edges(verts)
            if is_valid_face(f, verts, clean_degenerate=clean_degenerate)
        ]

    num_f = len(faces)
    cells: list[list[int]] = []
    for _ in range(existing_cell_count):
        try:
            parts = next(it).split()
        except StopIteration:
            break
        if not parts:
            continue
        n = int(parts[0])
        f_indices = parts[1:]
        if n >= MIN_CELL_FACES and len(f_indices) >= n:
            parsed_cells = [int(idx) for idx in f_indices[:n]]
            if all(0 <= idx < num_f for idx in parsed_cells):
                ordered = order_cell_faces_by_shared_edges(parsed_cells, faces)
                if ordered is not None:
                    cells.append(ordered)

    if not cells and faces:
        if fast_only:
            cells = connected_face_component_cells(faces)
        else:
            cells = find_3d_cells_for_convex_polytope(
                verts,
                faces,
                max_hyperplane_faces=max_hyperplane_faces,
                max_plane_checks=max_plane_checks,
            )

    if not cells and faces:
        cells = connected_face_component_cells(faces)

    # Guarantee every output cell has >= MIN_CELL_FACES faces and valid shared-edge order
    cells = [c for c in cells if len(c) >= MIN_CELL_FACES]

    unique_edges: set[tuple[int, int]] = set()
    for face in faces:
        unique_edges.update(face_edges(face))

    base, _ = os.path.splitext(input_path)
    output_path = f"{base}_poly.off"

    with open(output_path, "w", encoding="utf-8", newline="\n") as out:
        out.write("4OFF\n")
        out.write(f"{len(verts)} {len(faces)} {len(unique_edges)} {len(cells)}\n")
        for x, y, z, w in verts:
            out.write(f"{x} {y} {z} {w}\n")
        for face in faces:
            out.write(f"{len(face)} " + " ".join(str(v) for v in face) + "\n")
        for cell in cells:
            out.write(f"{len(cell)} " + " ".join(str(f) for f in cell) + "\n")

    elapsed = time.perf_counter() - t0
    print(
        f"Created (overwrote): {os.path.basename(output_path)} "
        f"({len(verts)} verts, {len(faces)} faces, {len(unique_edges)} edges, {len(cells)} cells) [{elapsed:.2f}s]"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert *.off files in-place into *_poly.off meshes for PolyMesh4D."
    )
    parser.add_argument("--w", type=float, default=0.0, help="Default W coordinate for 3D vertices")
    parser.add_argument("--scale", type=float, default=1.0, help="Scale multiplier applied to vertices")
    parser.add_argument("--center", action="store_true", help="Center vertices around (0, 0, 0, 0)")
    parser.add_argument(
        "--max-reconstruct-verts",
        type=int,
        default=256,
        help="Max vertex count for shortest-edge face reconstruction",
    )
    parser.add_argument(
        "--max-hyperplane-faces",
        type=int,
        default=1500,
        help="Face threshold above which fast component cell grouping is used",
    )
    parser.add_argument(
        "--max-plane-checks",
        type=int,
        default=25000,
        help="Maximum candidate hyperplane checks per mesh",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Skip hyperplane search and build edge-ordered component cells immediately",
    )
    parser.add_argument(
        "--keep-degenerate",
        action="store_true",
        help="Keep faces with duplicate/zero-length vertices instead of filtering them",
    )
    parser.add_argument("-r", "--recursive", action="store_true", help="Include subdirectories")
    args = parser.parse_args()

    pattern = "**/*.off" if args.recursive else "*.off"
    for path in sorted(glob.glob(pattern, recursive=args.recursive)):
        if not os.path.isfile(path):
            continue
        try:
            convert_off_to_poly_off(
                path,
                default_w=args.w,
                max_reconstruct_verts=args.max_reconstruct_verts,
                max_hyperplane_faces=args.max_hyperplane_faces,
                max_plane_checks=args.max_plane_checks,
                fast_only=args.fast,
                clean_degenerate=not args.keep_degenerate,
                scale=args.scale,
                center=args.center,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"Skipped {path}: {exc}")


if __name__ == "__main__":
    main()