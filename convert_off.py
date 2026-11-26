#!/usr/bin/env python3
"""Convert only cubinder, duocylinder, torisphere, hypersphere, and hypertorus .off files into *_poly.off."""

from __future__ import annotations

import argparse
import glob
import os
import time
from collections import defaultdict, deque

TARGET_STEMS = (
    "cubinder",
    "duocylinder",
    "duocylinder (1)",
    "torisphere",
    "hypersphere",
    "hypertorus",
)
SKIP_SUFFIXES = ("_poly.off", "_tri.off", "_fixed.off")
MIN_CELL_FACES = 4


def is_target_off_file(path: str) -> bool:
    name = os.path.basename(path)
    if not name.lower().endswith(".off") or name.lower().endswith(SKIP_SUFFIXES):
        return False
    stem = os.path.splitext(name)[0].lower()
    return stem in TARGET_STEMS


def dist_sq4(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    dz = a[2] - b[2]
    dw = a[3] - b[3]
    return dx * dx + dy * dy + dz * dz + dw * dw


def face_edges(face: list[int]) -> list[tuple[int, int]]:
    m = len(face)
    out: list[tuple[int, int]] = []
    for i in range(m):
        a, b = face[i], face[(i + 1) % m]
        out.append((a, b) if a < b else (b, a))
    return out


def faces_share_edge(f1: list[int], f2: list[int]) -> bool:
    e1 = set(face_edges(f1))
    for edge in face_edges(f2):
        if edge in e1:
            return True
    return False


def order_shared_edge_walk(
    face_indices: list[int],
    faces: list[list[int]],
) -> list[int] | None:
    """Order >=4 unique faces starting from two faces that share an edge."""
    unique_f = list(dict.fromkeys(face_indices))
    if len(unique_f) < MIN_CELL_FACES:
        return None

    f_set = set(unique_f)
    edge_owners: dict[tuple[int, int], list[int]] = defaultdict(list)
    for f_idx in unique_f:
        for edge in face_edges(faces[f_idx]):
            edge_owners[edge].append(f_idx)

    adj: dict[int, list[int]] = {f_idx: [] for f_idx in unique_f}
    start_a: int | None = None
    start_b: int | None = None

    for owners in edge_owners.values():
        if len(owners) >= 2:
            a, b = owners[0], owners[1]
            if start_a is None and faces_share_edge(faces[a], faces[b]):
                start_a, start_b = a, b
            base = owners[0]
            for other in owners[1:]:
                adj[base].append(other)
                adj[other].append(base)

    if start_a is None or start_b is None:
        for i, f1 in enumerate(unique_f):
            for f2 in unique_f[i + 1 :]:
                if faces_share_edge(faces[f1], faces[f2]):
                    start_a, start_b = f1, f2
                    break
            if start_a is not None:
                break

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

    deduped = list(dict.fromkeys(ordered))
    if len(deduped) < MIN_CELL_FACES or not faces_share_edge(faces[deduped[0]], faces[deduped[1]]):
        return None

    return deduped


def build_shell_cells(faces: list[list[int]]) -> list[list[int]]:
    """Build valid >=4-face cells from edge-connected face components."""
    num_faces = len(faces)
    if num_faces < MIN_CELL_FACES:
        return []

    edge_owners: dict[tuple[int, int], list[int]] = defaultdict(list)
    for f_idx, face in enumerate(faces):
        for edge in face_edges(face):
            edge_owners[edge].append(f_idx)

    adj: dict[int, list[int]] = {i: [] for i in range(num_faces)}
    for owners in edge_owners.values():
        if len(owners) > 1:
            base = owners[0]
            for other in owners[1:]:
                adj[base].append(other)
                adj[other].append(base)

    visited = [False] * num_faces
    components: list[list[int]] = []
    small_faces: list[int] = []

    for start in range(num_faces):
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
            components.append(comp)
        else:
            small_faces.extend(comp)

    for f_idx in small_faces:
        attached = False
        for comp in components:
            comp_set = set(comp)
            if any(nb in comp_set and faces_share_edge(faces[f_idx], faces[nb]) for nb in adj[f_idx]):
                comp.append(f_idx)
                attached = True
                break
        if not attached and components:
            components[0].append(f_idx)

    cells: list[list[int]] = []
    for comp in components:
        ordered = order_shared_edge_walk(comp, faces)
        if ordered is not None and len(ordered) >= MIN_CELL_FACES:
            cells.append(ordered)

    # If no connected component reached MIN_CELL_FACES but >= MIN_CELL_FACES faces exist,
    # group all valid faces into edge-ordered cells of at least MIN_CELL_FACES faces.
    if not cells and num_faces >= MIN_CELL_FACES:
        all_indices = list(range(num_faces))
        ordered = order_shared_edge_walk(all_indices, faces)
        if ordered is not None and len(ordered) >= MIN_CELL_FACES:
            cells.append(ordered)
        else:
            cells.append(all_indices)

    return [c for c in cells if len(c) >= MIN_CELL_FACES]


def convert_target_off(
    input_path: str,
    default_w: float = 0.0,
    clean_degenerate: bool = True,
) -> None:
    if not is_target_off_file(input_path):
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
        if len(set(parsed)) >= 3 and all(0 <= idx < len(verts) for idx in parsed):
            if clean_degenerate:
                p0, p1, p2 = verts[parsed[0]], verts[parsed[1]], verts[parsed[2]]
                if dist_sq4(p0, p1) < 1e-14 or dist_sq4(p0, p2) < 1e-14 or dist_sq4(p1, p2) < 1e-14:
                    continue
            faces.append(parsed)

    cells = [c for c in build_shell_cells(faces) if len(c) >= MIN_CELL_FACES]

    unique_edges: set[tuple[int, int]] = set()
    for face in faces:
        unique_edges.update(face_edges(face))

    base, _ = os.path.splitext(input_path)
    output_path = f"{base}_poly.off"

    cell_lines: list[str] = []
    for cell in cells:
        unique_cell_faces = [f_idx for f_idx in dict.fromkeys(cell) if 0 <= f_idx < len(faces)]
        if len(unique_cell_faces) >= MIN_CELL_FACES:
            cell_lines.append(f"{len(unique_cell_faces)} " + " ".join(str(f) for f in unique_cell_faces) + "\n")

    with open(output_path, "w", encoding="utf-8", newline="\n") as out:
        out.write("4OFF\n")
        out.write(f"{len(verts)} {len(faces)} {len(unique_edges)} {len(cell_lines)}\n")
        for x, y, z, w in verts:
            out.write(f"{x} {y} {z} {w}\n")
        for face in faces:
            out.write(f"{len(face)} " + " ".join(str(v) for v in face) + "\n")
        for line in cell_lines:
            out.write(line)

    elapsed = time.perf_counter() - t0
    print(
        f"Updated target only: {os.path.basename(output_path)} "
        f"({len(verts)} verts, {len(faces)} faces, {len(unique_edges)} edges, {len(cell_lines)} cells) [{elapsed:.2f}s]"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Convert only cubinder, duocylinder, torisphere, hypersphere, and hypertorus "
            ".off files into *_poly.off without overwriting other *_poly.off files."
        )
    )
    parser.add_argument("--w", type=float, default=0.0, help="Default W coordinate for 3D vertices")
    parser.add_argument(
        "--keep-degenerate",
        action="store_true",
        help="Keep faces with zero-length edges instead of filtering them",
    )
    parser.add_argument("-r", "--recursive", action="store_true", help="Include subdirectories")
    args = parser.parse_args()

    pattern = "**/*.off" if args.recursive else "*.off"
    matched = [p for p in sorted(glob.glob(pattern, recursive=args.recursive)) if is_target_off_file(p)]

    if not matched:
        print("No matching target .off files found.")
        return

    for path in matched:
        try:
            convert_target_off(
                path,
                default_w=args.w,
                clean_degenerate=not args.keep_degenerate,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"Skipped {path}: {exc}")


if __name__ == "__main__":
    main()