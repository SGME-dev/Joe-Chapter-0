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
DEFAULT_MAX_CELL_FACES = 64


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


def build_edge_connected_cells(
    faces: list[list[int]],
    max_cell_faces: int = DEFAULT_MAX_CELL_FACES,
) -> list[list[int]]:
    """Build cells of >=4 unique faces where each cell starts with two edge-sharing faces."""
    num_faces = len(faces)
    if num_faces < MIN_CELL_FACES:
        return []

    edge_to_faces: dict[tuple[int, int], list[int]] = defaultdict(list)
    for f_idx, face in enumerate(faces):
        for edge in face_edges(face):
            edge_to_faces[edge].append(f_idx)

    adj: dict[int, list[int]] = {i: [] for i in range(num_faces)}
    shared_edges: list[tuple[int, int]] = []
    for owners in edge_to_faces.values():
        if len(owners) >= 2:
            base = owners[0]
            for other in owners[1:]:
                if other not in adj[base]:
                    adj[base].append(other)
                if base not in adj[other]:
                    adj[other].append(base)
                if faces_share_edge(faces[base], faces[other]):
                    shared_edges.append((base, other))

    used: set[int] = set()
    cells: list[list[int]] = []

    # Grow cells starting from explicit edge-sharing face pairs
    for a, b in shared_edges:
        if a in used or b in used:
            continue
        if not faces_share_edge(faces[a], faces[b]):
            continue

        cell: list[int] = [a, b]
        used.add(a)
        used.add(b)
        q: deque[int] = deque([a, b])

        while q and len(cell) < max_cell_faces:
            cur = q.popleft()
            for nxt in adj[cur]:
                if nxt not in used and faces_share_edge(faces[cur], faces[nxt]):
                    used.add(nxt)
                    cell.append(nxt)
                    q.append(nxt)
                    if len(cell) >= max_cell_faces:
                        break

        if len(cell) >= MIN_CELL_FACES:
            cells.append(cell)
        else:
            # Release if under MIN_CELL_FACES so leftover faces can merge cleanly
            for idx in cell:
                used.discard(idx)

    # Fold remaining unused faces into an existing cell they share an edge with
    leftovers = [i for i in range(num_faces) if i not in used]
    for f_idx in leftovers:
        merged = False
        for cell in cells:
            if any(faces_share_edge(faces[f_idx], faces[c_idx]) for c_idx in cell[:8]):
                cell.append(f_idx)
                used.add(f_idx)
                merged = True
                break
        if not merged and cells:
            cells[-1].append(f_idx)
            used.add(f_idx)

    # Fallback if no shared-edge cells were formed at all
    if not cells and num_faces >= MIN_CELL_FACES:
        cells.append(list(range(num_faces)))

    return [c for c in cells if len(c) >= MIN_CELL_FACES]


def convert_target_off(
    input_path: str,
    default_w: float = 0.0,
    max_cell_faces: int = DEFAULT_MAX_CELL_FACES,
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

    raw_cells = build_edge_connected_cells(faces, max_cell_faces=max_cell_faces)
    valid_cells: list[list[int]] = []
    for cell in raw_cells:
        deduped = [idx for idx in dict.fromkeys(cell) if 0 <= idx < len(faces)]
        if len(deduped) >= MIN_CELL_FACES:
            valid_cells.append(deduped)

    unique_edges: set[tuple[int, int]] = set()
    for face in faces:
        unique_edges.update(face_edges(face))

    base, _ = os.path.splitext(input_path)
    output_path = f"{base}_poly.off"

    with open(output_path, "w", encoding="utf-8", newline="\n") as out:
        out.write("4OFF\n")
        out.write(f"{len(verts)} {len(faces)} {len(unique_edges)} {len(valid_cells)}\n")
        for x, y, z, w in verts:
            out.write(f"{x} {y} {z} {w}\n")
        for face in faces:
            out.write(f"{len(face)} " + " ".join(str(v) for v in face) + "\n")
        for c in valid_cells:
            out.write(f"{len(c)} " + " ".join(str(f) for f in c) + "\n")

    min_c = min((len(c) for c in valid_cells), default=0)
    elapsed = time.perf_counter() - t0
    print(
        f"Updated target only: {output_path} "
        f"({len(verts)} verts, {len(faces)} faces, {len(unique_edges)} edges, "
        f"{len(valid_cells)} cells, min_cell={min_c}) [{elapsed:.2f}s]"
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
        "--max-cell-faces",
        type=int,
        default=DEFAULT_MAX_CELL_FACES,
        help="Target maximum faces per edge-grown cell",
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
                max_cell_faces=args.max_cell_faces,
                clean_degenerate=not args.keep_degenerate,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"Skipped {path}: {exc}")


if __name__ == "__main__":
    main()