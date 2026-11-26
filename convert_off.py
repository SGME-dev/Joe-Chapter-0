#!/usr/bin/env python3
"""Convert only cubinder, duocylinder, torisphere, hypersphere, hypertorus, and sphereinder .off files."""

from __future__ import annotations

import argparse
import glob
import os
import re
import time
from collections import defaultdict, deque

TARGET_BASE_STEMS = (
    "cubinder",
    "duocylinder",
    "torisphere",
    "hypersphere",
    "hypertorus",
    "sphereinder",
)
SKIP_SUFFIXES = ("_poly.off", "_tri.off", "_fixed.off")
MIN_CELL_FACES = 4
DEFAULT_CHUNK_SIZE = 128


def is_target_off_file(path: str) -> bool:
    name = os.path.basename(path).lower()
    if not name.endswith(".off") or name.endswith(SKIP_SUFFIXES):
        return False
    stem = os.path.splitext(name)[0].strip()
    normalized = re.sub(r"\s*\(\d+\)$", "", stem)
    return normalized in TARGET_BASE_STEMS


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
    edges: list[tuple[int, int]] = []
    for i in range(m):
        u, v = face[i], face[(i + 1) % m]
        edges.append((u, v) if u < v else (v, u))
    return edges


def faces_share_edge(f1: list[int], f2: list[int]) -> bool:
    s1 = set(face_edges(f1))
    return any(e in s1 for e in face_edges(f2))


def build_cells_from_components(
    faces: list[list[int]],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> list[list[int]]:
    """Build >=4-face cells from edge-connected face components while preserving all faces."""
    n_faces = len(faces)
    if n_faces < MIN_CELL_FACES:
        return []

    edge_owners: dict[tuple[int, int], list[int]] = defaultdict(list)
    face_edge_sets: list[set[tuple[int, int]]] = []
    for idx, face in enumerate(faces):
        eset = set(face_edges(face))
        face_edge_sets.append(eset)
        for edge in eset:
            edge_owners[edge].append(idx)

    adj: list[list[int]] = [[] for _ in range(n_faces)]
    for owners in edge_owners.values():
        if len(owners) >= 2:
            anchor = owners[0]
            for other in owners[1:]:
                if anchor == other:
                    continue
                if other not in adj[anchor]:
                    adj[anchor].append(other)
                if anchor not in adj[other]:
                    adj[other].append(anchor)

    visited = [False] * n_faces
    large_components: list[list[int]] = []
    small_components: list[list[int]] = []

    for start in range(n_faces):
        if visited[start]:
            continue
        comp: list[int] = []
        queue: deque[int] = deque([start])
        visited[start] = True
        while queue:
            cur = queue.popleft()
            comp.append(cur)
            for nxt in adj[cur]:
                if not visited[nxt]:
                    visited[nxt] = True
                    queue.append(nxt)

        if len(comp) >= MIN_CELL_FACES:
            large_components.append(comp)
        else:
            small_components.append(comp)

    # Split large edge-connected components into ordered edge-walk chunks of >= MIN_CELL_FACES
    cells: list[list[int]] = []
    for comp in large_components:
        comp_set = set(comp)
        ordered: list[int] = []
        seen_in_comp: set[int] = set()

        for seed in comp:
            if seed in seen_in_comp:
                continue
            seen_in_comp.add(seed)
            ordered.append(seed)
            q: deque[int] = deque([seed])
            while q:
                cur = q.popleft()
                for nxt in adj[cur]:
                    if nxt in comp_set and nxt not in seen_in_comp:
                        seen_in_comp.add(nxt)
                        ordered.append(nxt)
                        q.append(nxt)

        for i in range(0, len(ordered), chunk_size):
            part = ordered[i : i + chunk_size]
            if len(part) >= MIN_CELL_FACES:
                cells.append(part)
            elif cells:
                cells[-1].extend(part)
            else:
                cells.append(part)

    # Attach small components (< MIN_CELL_FACES) to a cell with a shared edge
    for small in small_components:
        attached_idx: int | None = None
        for f_idx in small:
            for c_idx, cell in enumerate(cells):
                if any(face_edge_sets[f_idx] & face_edge_sets[c_f] for c_f in cell[:32]):
                    attached_idx = c_idx
                    break
            if attached_idx is not None:
                break

        if attached_idx is not None:
            cells[attached_idx].extend(small)
        elif cells:
            cells[-1].extend(small)
        else:
            cells.append(list(small))

    # Final safety pass: ensure every cell has >= MIN_CELL_FACES and every face is covered
    final_cells: list[list[int]] = []
    covered: set[int] = set()
    for cell in cells:
        deduped = [f_idx for f_idx in dict.fromkeys(cell) if 0 <= f_idx < n_faces]
        if len(deduped) >= MIN_CELL_FACES:
            final_cells.append(deduped)
            covered.update(deduped)
        elif final_cells:
            for f_idx in deduped:
                if f_idx not in final_cells[-1]:
                    final_cells[-1].append(f_idx)
                    covered.add(f_idx)

    uncovered = [i for i in range(n_faces) if i not in covered]
    if uncovered:
        if final_cells:
            for f_idx in uncovered:
                if f_idx not in final_cells[-1]:
                    final_cells[-1].append(f_idx)
        elif n_faces >= MIN_CELL_FACES:
            final_cells.append(list(range(n_faces)))

    return final_cells


def convert_target_off(
    input_path: str,
    default_w: float = 0.0,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
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

    cells = build_cells_from_components(faces, chunk_size=chunk_size)

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

    all_in_cells = {f_idx for c in cells for f_idx in c}
    missing_count = len(faces) - len(all_in_cells)
    min_c = min((len(c) for c in cells), default=0)
    elapsed = time.perf_counter() - t0
    print(
        f"Updated target only: {output_path} "
        f"({len(verts)} verts, {len(faces)} faces, missing={missing_count}, "
        f"{len(unique_edges)} edges, {len(cells)} cells, min_cell={min_c}) [{elapsed:.2f}s]"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Convert only cubinder, duocylinder, torisphere, hypersphere, hypertorus, "
            "and sphereinder .off files into *_poly.off without touching other *_poly.off files."
        )
    )
    parser.add_argument("--w", type=float, default=0.0, help="Default W coordinate for 3D vertices")
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help="Maximum faces per edge-ordered chunk within a component",
    )
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
                chunk_size=args.chunk_size,
                clean_degenerate=not args.keep_degenerate,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"Skipped {path}: {exc}")


if __name__ == "__main__":
    main()