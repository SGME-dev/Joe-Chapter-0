import argparse
import glob
import math
import os
from collections import defaultdict, deque
from dataclasses import dataclass

SKIP_SUFFIXES = ("_poly.off", "_tri.off", "_fixed.off", "_small.off")
HEADER_4D = {"4OFF", "4NOFF"}
HEADER_3D = {"OFF", "3OFF", "NOFF"}


@dataclass(frozen=True)
class Hyperplane4D:
    nx: float
    ny: float
    nz: float
    nw: float
    d: float

    def signed_distance(self, p: tuple[float, float, float, float]) -> float:
        return self.nx * p[0] + self.ny * p[1] + self.nz * p[2] + self.nw * p[3] - self.d


def dot4(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3]


def sub4(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> tuple[float, float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2], a[3] - b[3])


def norm4(
    v: tuple[float, float, float, float], eps: float = 1e-9
) -> tuple[float, float, float, float] | None:
    length = math.hypot(v[0], v[1], v[2], v[3])
    if length < eps:
        return None
    inv = 1.0 / length
    return (v[0] * inv, v[1] * inv, v[2] * inv, v[3] * inv)


def hyperplane_from_three_vectors(
    u: tuple[float, float, float, float],
    v: tuple[float, float, float, float],
    w: tuple[float, float, float, float],
) -> tuple[float, float, float, float] | None:
    ux, uy, uz, uw = u
    vx, vy, vz, vw = v
    wx, wy, wz, ww = w

    def det3(
        a1: float,
        a2: float,
        a3: float,
        b1: float,
        b2: float,
        b3: float,
        c1: float,
        c2: float,
        c3: float,
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


def canonical_hyperplane(
    normal: tuple[float, float, float, float],
    point: tuple[float, float, float, float],
) -> Hyperplane4D:
    nx, ny, nz, nw = normal
    d = dot4(normal, point)

    if d < -1e-6 or (
        abs(d) <= 1e-6
        and (
            nx < -1e-6
            or (abs(nx) <= 1e-6 and (ny < -1e-6 or (abs(ny) <= 1e-6 and nz < -1e-6)))
        )
    ):
        nx, ny, nz, nw = -nx, -ny, -nz, -nw
        d = -d

    clean = [0.0 if abs(c) < 1e-12 else c for c in (nx, ny, nz, nw, d)]
    return Hyperplane4D(clean[0], clean[1], clean[2], clean[3], clean[4])


def face_edges(face: list[int]) -> set[tuple[int, int]]:
    edges: set[tuple[int, int]] = set()
    m = len(face)
    for i in range(m):
        a, b = face[i], face[(i + 1) % m]
        if a != b:
            edges.add((a, b) if a < b else (b, a))
    return edges


def _build_adjacency(
    face_indices: list[int],
    all_faces: list[list[int]],
) -> tuple[dict[int, set[tuple[int, int]]], dict[int, list[int]]]:
    face_edge_map: dict[int, set[tuple[int, int]]] = {
        f_idx: face_edges(all_faces[f_idx]) for f_idx in face_indices
    }
    edge_to_faces: dict[tuple[int, int], list[int]] = defaultdict(list)
    for f_idx, edges in face_edge_map.items():
        for e in edges:
            edge_to_faces[e].append(f_idx)

    neighbors: dict[int, list[int]] = {f_idx: [] for f_idx in face_indices}
    for f_idx, edges in face_edge_map.items():
        seen_nbrs: set[int] = set()
        for e in edges:
            for other in edge_to_faces[e]:
                if other != f_idx and other not in seen_nbrs:
                    seen_nbrs.add(other)
                    neighbors[f_idx].append(other)

    return face_edge_map, neighbors


def split_into_connected_components(
    face_indices: list[int],
    all_faces: list[list[int]],
) -> list[list[int]]:
    _, neighbors = _build_adjacency(face_indices, all_faces)
    visited: set[int] = set()
    components: list[list[int]] = []

    for start in face_indices:
        if start in visited:
            continue
        comp: list[int] = []
        q: deque[int] = deque([start])
        visited.add(start)
        while q:
            curr = q.popleft()
            comp.append(curr)
            for nxt in neighbors[curr]:
                if nxt not in visited:
                    visited.add(nxt)
                    q.append(nxt)
        components.append(comp)

    return components


def order_and_validate_cell(
    cell_face_indices: list[int],
    all_faces: list[list[int]],
) -> list[int] | None:
    """Order faces in a cell via shared edges and drop if cell[0] and cell[1] don't share an edge."""
    unique_indices: list[int] = []
    seen_idx: set[int] = set()
    for fi in cell_face_indices:
        if 0 <= fi < len(all_faces) and fi not in seen_idx:
            seen_idx.add(fi)
            unique_indices.append(fi)

    if len(unique_indices) < 4:
        return None

    face_edge_map, neighbors = _build_adjacency(unique_indices, all_faces)

    start = next((f_idx for f_idx in unique_indices if neighbors[f_idx]), None)
    if start is None:
        return None

    ordered: list[int] = []
    visited: set[int] = set()
    queue: deque[int] = deque([start])
    visited.add(start)

    while queue:
        curr = queue.popleft()
        ordered.append(curr)
        for nxt in neighbors[curr]:
            if nxt not in visited:
                visited.add(nxt)
                queue.append(nxt)

    if len(ordered) < 4 or not (face_edge_map[ordered[0]] & face_edge_map[ordered[1]]):
        return None

    return ordered


def find_3d_cells_for_convex_polytope(
    verts: list[tuple[float, float, float, float]],
    faces: list[list[int]],
    dist_tol: float = 1e-3,
    plane_tol: float = 1e-2,
) -> list[list[int]]:
    edge_to_faces: dict[tuple[int, int], list[int]] = defaultdict(list)
    for f_idx, face in enumerate(faces):
        for edge in face_edges(face):
            edge_to_faces[edge].append(f_idx)

    face_vert_sets = [set(f) for f in faces]
    accepted_planes: list[Hyperplane4D] = []
    valid_cells: list[list[int]] = []
    seen_cell_sets: set[frozenset[int]] = set()

    for (va, vb), adj_faces in edge_to_faces.items():
        if len(adj_faces) < 2:
            continue
        p0 = verts[va]
        e_vec = sub4(verts[vb], p0)

        for i in range(len(adj_faces)):
            f1_idx = adj_faces[i]
            f1_cands = [v for v in faces[f1_idx] if v != va and v != vb]
            if not f1_cands:
                continue

            for j in range(i + 1, len(adj_faces)):
                f2_idx = adj_faces[j]
                f2_cands = [v for v in faces[f2_idx] if v != va and v != vb]
                if not f2_cands:
                    continue

                normal: tuple[float, float, float, float] | None = None
                for v1_cand in f1_cands:
                    u_vec = sub4(verts[v1_cand], p0)
                    for v2_cand in f2_cands:
                        if v2_cand == v1_cand:
                            continue
                        w_vec = sub4(verts[v2_cand], p0)
                        normal = hyperplane_from_three_vectors(e_vec, u_vec, w_vec)
                        if normal is not None:
                            break
                    if normal is not None:
                        break

                if normal is None:
                    continue

                plane = canonical_hyperplane(normal, p0)

                if any(
                    abs(existing.nx - plane.nx) < plane_tol
                    and abs(existing.ny - plane.ny) < plane_tol
                    and abs(existing.nz - plane.nz) < plane_tol
                    and abs(existing.nw - plane.nw) < plane_tol
                    and abs(existing.d - plane.d) < plane_tol
                    for existing in accepted_planes
                ):
                    continue

                coplanar_faces = [
                    check_idx
                    for check_idx, vset in enumerate(face_vert_sets)
                    if all(abs(plane.signed_distance(verts[v])) < dist_tol for v in vset)
                ]

                if len(coplanar_faces) >= 4:
                    accepted_planes.append(plane)
                    for comp in split_into_connected_components(coplanar_faces, faces):
                        ordered = order_and_validate_cell(comp, faces)
                        if ordered is not None:
                            fset = frozenset(ordered)
                            if fset not in seen_cell_sets:
                                seen_cell_sets.add(fset)
                                valid_cells.append(ordered)

    return valid_cells


def tokenize_off(raw_text: str) -> list[str]:
    tokens: list[str] = []
    for raw_line in raw_text.splitlines():
        before_comment, _, _ = raw_line.partition("#")
        tokens.extend(before_comment.strip().split())
    return tokens


def _try_int(tok: str) -> int | None:
    try:
        return int(tok)
    except ValueError:
        return None


def _try_float(tok: str) -> float | None:
    try:
        return float(tok)
    except ValueError:
        return None


def parse_off_with_coord_width(
    tokens: list[str],
    start_idx: int,
    vert_count: int,
    face_count: int,
    coords_per_vert: int,
) -> tuple[list[tuple[float, float, float, float]], list[list[int]], list[list[int]]]:
    idx = start_idx
    existing_cell_count = 0

    if idx + 2 < len(tokens):
        e_cand = _try_int(tokens[idx])
        c_cand = _try_int(tokens[idx + 1])
        v0_cand = _try_float(tokens[idx + 2])
        if e_cand is not None and c_cand is not None and v0_cand is not None:
            idx += 1
            existing_cell_count = c_cand

    verts: list[tuple[float, float, float, float]] = []
    for _ in range(vert_count):
        if idx + coords_per_vert > len(tokens):
            raise ValueError("Unexpected EOF while reading vertices")
        x = float(tokens[idx])
        y = float(tokens[idx + 1])
        z = float(tokens[idx + 2])
        w = float(tokens[idx + 3]) if coords_per_vert == 4 else 0.0
        idx += coords_per_vert
        verts.append((x, y, z, w))

    while idx < len(tokens):
        n_cand = _try_int(tokens[idx])
        if n_cand is not None and 3 <= n_cand <= 32 and idx + n_cand < len(tokens):
            if all(_try_int(tokens[idx + 1 + k]) is not None for k in range(n_cand)):
                break
        if _try_float(tokens[idx]) is None:
            break
        idx += 1

    raw_faces: list[list[int]] = []
    for _ in range(face_count):
        if idx >= len(tokens):
            break
        n_val = _try_int(tokens[idx])
        if n_val is None or n_val < 3 or idx + n_val >= len(tokens):
            idx += 1
            continue
        idx += 1
        f_indices: list[int] = []
        valid_group = True
        for k in range(n_val):
            iv = _try_int(tokens[idx + k])
            if iv is None:
                valid_group = False
                break
            f_indices.append(iv)
        idx += n_val
        if valid_group:
            raw_faces.append(f_indices)
        while idx < len(tokens) and _try_int(tokens[idx]) is None and _try_float(tokens[idx]) is not None:
            idx += 1

    if not raw_faces:
        raise ValueError("No valid face records parsed")

    v_total = len(verts)
    all_indices = [vi for face in raw_faces for vi in face]
    uses_one_based = (
        bool(all_indices)
        and min(all_indices) >= 1
        and max(all_indices) == v_total
    )
    shift = -1 if uses_one_based else 0

    faces: list[list[int]] = []
    for raw_face in raw_faces:
        cleaned_face: list[int] = []
        for raw_vi in raw_face:
            vi = raw_vi + shift
            if 0 <= vi < v_total and (not cleaned_face or cleaned_face[-1] != vi):
                cleaned_face.append(vi)
        if len(cleaned_face) > 1 and cleaned_face[0] == cleaned_face[-1]:
            cleaned_face.pop()
        if len(cleaned_face) >= 3:
            faces.append(cleaned_face)

    cells: list[list[int]] = []
    for _ in range(existing_cell_count):
        if idx >= len(tokens):
            break
        n_val = _try_int(tokens[idx])
        if n_val is None or n_val < 4 or idx + n_val >= len(tokens):
            break
        idx += 1
        raw_c = [_try_int(tokens[idx + k]) for k in range(n_val)]
        idx += n_val
        c_indices = [ci for ci in raw_c if ci is not None]
        for comp in split_into_connected_components(c_indices, faces):
            ordered = order_and_validate_cell(comp, faces)
            if ordered is not None:
                cells.append(ordered)

    return verts, faces, cells


def parse_off(
    tokens: list[str],
) -> tuple[list[tuple[float, float, float, float]], list[list[int]], list[list[int]]]:
    idx = 0
    header = tokens[idx]
    preferred_coords = 4
    if header in HEADER_4D:
        preferred_coords = 4
        idx += 1
    elif header in HEADER_3D or header.endswith("OFF"):
        preferred_coords = 3 if header in HEADER_3D else 4
        idx += 1

    if len(tokens) - idx < 2:
        raise ValueError("Missing vertex and face counts")

    vert_count = int(tokens[idx])
    face_count = int(tokens[idx + 1])
    idx += 2

    best_result: tuple[list[tuple[float, float, float, float]], list[list[int]], list[list[int]]] | None = None
    last_err: Exception | None = None

    for coords in (preferred_coords, 3 if preferred_coords == 4 else 4):
        try:
            res = parse_off_with_coord_width(tokens, idx, vert_count, face_count, coords)
            if res[1]:
                return res
            best_result = res
        except ValueError as err:
            last_err = err

    if best_result is not None:
        return best_result
    raise last_err if last_err else ValueError("Failed to parse OFF geometry")


def shrink_mesh_to_budget(
    verts: list[tuple[float, float, float, float]],
    faces: list[list[int]],
    max_faces: int,
) -> tuple[list[tuple[float, float, float, float]], list[list[int]]]:
    if len(faces) <= max_faces:
        return verts, faces

    mins = [min(v[d] for v in verts) for d in range(4)]
    maxs = [max(v[d] for v in verts) for d in range(4)]
    span = max((maxs[d] - mins[d] for d in range(4)), default=1.0)
    if span <= 1e-9:
        span = 1.0

    cell_size = span / 64.0
    best_verts, best_faces = verts, faces

    for _ in range(24):
        grid_to_new_idx: dict[tuple[int, int, int, int], int] = {}
        bucket_sums: list[list[float]] = []
        bucket_counts: list[int] = []
        old_to_new: list[int] = []

        for v in verts:
            key = (
                int(math.floor((v[0] - mins[0]) / cell_size)),
                int(math.floor((v[1] - mins[1]) / cell_size)),
                int(math.floor((v[2] - mins[2]) / cell_size)),
                int(math.floor((v[3] - mins[3]) / cell_size)),
            )
            new_idx = grid_to_new_idx.get(key)
            if new_idx is None:
                new_idx = len(bucket_sums)
                grid_to_new_idx[key] = new_idx
                bucket_sums.append([v[0], v[1], v[2], v[3]])
                bucket_counts.append(1)
            else:
                acc = bucket_sums[new_idx]
                acc[0] += v[0]
                acc[1] += v[1]
                acc[2] += v[2]
                acc[3] += v[3]
                bucket_counts[new_idx] += 1
            old_to_new.append(new_idx)

        new_verts = [
            (
                bucket_sums[i][0] / bucket_counts[i],
                bucket_sums[i][1] / bucket_counts[i],
                bucket_sums[i][2] / bucket_counts[i],
                bucket_sums[i][3] / bucket_counts[i],
            )
            for i in range(len(bucket_sums))
        ]

        seen_face_sets: set[frozenset[int]] = set()
        new_faces: list[list[int]] = []
        for face in faces:
            mapped: list[int] = []
            for vi in face:
                ni = old_to_new[vi]
                if not mapped or mapped[-1] != ni:
                    mapped.append(ni)
            if len(mapped) > 1 and mapped[0] == mapped[-1]:
                mapped.pop()
            if len(mapped) >= 3:
                fset = frozenset(mapped)
                if len(fset) >= 3 and fset not in seen_face_sets:
                    seen_face_sets.add(fset)
                    new_faces.append(mapped)

        best_verts, best_faces = new_verts, new_faces
        if len(new_faces) <= max_faces:
            return best_verts, best_faces

        cell_size *= 1.35

    return best_verts, best_faces


def extract_unique_edges(faces: list[list[int]]) -> set[tuple[int, int]]:
    edges: set[tuple[int, int]] = set()
    for face in faces:
        for edge in face_edges(face):
            edges.add(edge)
    return edges


def write_4off(
    path: str,
    verts: list[tuple[float, float, float, float]],
    faces: list[list[int]],
    cells: list[list[int]],
) -> None:
    edges = extract_unique_edges(faces)
    with open(path, "w", encoding="utf-8", newline="\n") as out:
        out.write("4OFF\n")
        out.write(f"{len(verts)} {len(faces)} {len(edges)} {len(cells)}\n")
        for x, y, z, w in verts:
            out.write(f"{x:g} {y:g} {z:g} {w:g}\n")
        for face in faces:
            out.write(f"{len(face)} " + " ".join(str(v) for v in face) + "\n")
        for cell in cells:
            out.write(f"{len(cell)} " + " ".join(str(f) for f in cell) + "\n")


def process_off_file(
    input_path: str,
    max_faces: int = 5000,
    fix_files: bool = False,
    dry_run: bool = False,
) -> None:
    basename = os.path.basename(input_path)
    if basename.endswith(SKIP_SUFFIXES):
        return

    with open(input_path, "r", encoding="utf-8", errors="replace") as f:
        tokens = tokenize_off(f.read())

    if not tokens:
        print(f"Skipped (empty): {basename}")
        return

    verts, faces, cells = parse_off(tokens)
    if not faces:
        print(f"Skipped (0 valid faces): {basename}")
        return

    base, _ = os.path.splitext(input_path)
    was_shrunk = False

    if len(faces) > max_faces:
        orig_faces = len(faces)
        verts, faces = shrink_mesh_to_budget(verts, faces, max_faces=max_faces)
        was_shrunk = True
        cells = []
        print(f"Shrunk {basename}: {orig_faces} -> {len(faces)} faces, {len(verts)} verts")
        if fix_files and not dry_run:
            write_4off(f"{base}_small.off", verts, faces, [])

    if not cells:
        cells = find_3d_cells_for_convex_polytope(verts, faces)
    else:
        validated: list[list[int]] = []
        for c in cells:
            for comp in split_into_connected_components(c, faces):
                ordered = order_and_validate_cell(comp, faces)
                if ordered is not None:
                    validated.append(ordered)
        cells = validated

    if not cells:
        print(f"Skipped (could not find valid >=4-face 3D cells): {basename}")
        return

    if fix_files and not dry_run:
        write_4off(f"{base}_fixed.off", verts, faces, cells)

    unique_edges = extract_unique_edges(faces)
    output_path = f"{base}_poly.off"

    if dry_run:
        print(
            f"[Dry run] {basename} -> {os.path.basename(output_path)} "
            f"({len(verts)}v, {len(faces)}f, {len(unique_edges)}e, {len(cells)}c)"
        )
        return

    write_4off(output_path, verts, faces, cells)
    tag = " (simplified)" if was_shrunk else ""
    print(
        f"Wrote {os.path.basename(output_path)}{tag} "
        f"({len(verts)} verts, {len(faces)} faces, {len(unique_edges)} edges, {len(cells)} cells)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Repair, simplify, and convert OFF files to 4OFF for godot-4d."
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        help="Input .off files or glob patterns (defaults to *.off).",
    )
    parser.add_argument(
        "--max-faces",
        type=int,
        default=5000,
        help="Target maximum face count; larger meshes are simplified (default: 5000).",
    )
    parser.add_argument(
        "--fix-files",
        action="store_true",
        help="Also emit *_fixed.off (and *_small.off when shrunk).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without writing output files.",
    )
    args = parser.parse_args()

    patterns = args.inputs if args.inputs else ["*.off"]
    files: list[str] = []
    for pat in patterns:
        matched = glob.glob(pat)
        files.extend(matched if matched else [pat])

    for path in sorted(set(files)):
        if not os.path.isfile(path):
            print(f"Skipped (not a file): {path}")
            continue
        try:
            process_off_file(
                path,
                max_faces=args.max_faces,
                fix_files=args.fix_files,
                dry_run=args.dry_run,
            )
        except Exception as exc:
            print(f"Skipped {path}: {exc}")


if __name__ == "__main__":
    main()