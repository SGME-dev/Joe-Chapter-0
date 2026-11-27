#!/usr/bin/env python3
"""Convert 4D .off files into the layout godot-4d imports as a PolyMesh4D.

Writes <name>_poly.off next to each input. The originals are never modified.

    python off_to_poly4d.py                      # the default shapes, current folder
    python off_to_poly4d.py path/to/folder       # the default shapes, another folder
    python off_to_poly4d.py a.off b.off          # specific files
    python off_to_poly4d.py --hull a.off         # ignore faces/cells, use vertices only

Target layout (see model/off/off_document_4d.cpp in godot-4d):
    4OFF
    V F E C
    V lines:  x y z w
    F lines:  n v1 .. vn   [r g b]    (polygon, vertices in loop order)
    C lines:  m f1 .. fm   [r g b]    (3D boundary cell, made of faces)
The order of the first two faces of a cell sets which way its normal points.

How the input is read:
    cells that reference faces   -> cleaned up, colours kept
    "faces" that are tetrahedra  -> split into triangles and cells
    anything else                -> rebuilt as the convex hull of the vertices
                                    (needs numpy and scipy; colours are lost)
The hull rebuild only works for convex shapes. Shapes with holes (hypertorus,
torisphere) need cells or tetrahedra in the file, otherwise they are reported
as FAIL rather than being filled in.

Normals are pointed out of the solid, worked out from how the cells connect, so
this works with or without holes. --keep-orientation keeps the file's own.
"""

import argparse
import math
import sys
from collections import Counter
from pathlib import Path

DEFAULT_NAMES = (
    "cubinder.off",
    "duocylinder.off",
    "hypersphere.off",
    "sphereinder.off",
    "spherinder.off",  # the more common spelling
    "hypertorus.off",
    "torisphere.off",
)
OPTIONAL_NAMES = {"sphereinder.off", "spherinder.off"}  # only one is expected
HOLED_NAME_PARTS = ("torus", "tori", "tiger")  # never replace these with a hull

EPS = 1e-6  # relative to the size of the shape


class OffError(Exception):
    pass


class Unusable(Exception):
    """The faces/cells in the file can't be used as they are."""


# --------------------------------------------------------------------------
# Small 4D vector helpers
# --------------------------------------------------------------------------
def sub(a, b):
    return [x - y for x, y in zip(a, b)]


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def centroid(points):
    return [sum(c) / len(points) for c in zip(*points)]


def perpendicular(a, b, c):
    """Same formula and sign as Vector4D::perpendicular in godot-4d."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    cx, cy, cz, cw = c
    return [
        -ay * (bz * cw - bw * cz) + az * (by * cw - bw * cy) - aw * (by * cz - bz * cy),
        ax * (bz * cw - bw * cz) - az * (bx * cw - bw * cx) + aw * (bx * cz - bz * cx),
        -ax * (by * cw - bw * cy) + ay * (bx * cw - bw * cx) - aw * (bx * cy - by * cx),
        ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx),
    ]


def affine_rank(points, tol, stop_at=4):
    """Dimension spanned by the points (Gram-Schmidt, farthest point first)."""
    residual = [sub(p, points[0]) for p in points[1:]]
    rank = 0
    while residual and rank < stop_at:
        best = max(residual, key=lambda v: dot(v, v))
        length = math.sqrt(dot(best, best))
        if length <= tol:
            break
        axis = [x / length for x in best]
        residual = [sub(v, [dot(v, axis) * x for x in axis]) for v in residual]
        rank += 1
    return rank


def shape_size(vertices):
    centre = centroid(vertices)
    return max(math.dist(v, centre) for v in vertices) or 1.0


def loop_edges(face):
    return [tuple(sorted((face[i], face[(i + 1) % len(face)]))) for i in range(len(face))]


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------
def read_off(path):
    """Return (vertices, counts, body_rows, rounding_step)."""
    rows = []
    for line in Path(path).read_text(encoding="utf-8-sig", errors="replace").splitlines():
        tokens = line.split("#", 1)[0].replace(",", " ").split()
        if tokens:
            rows.append(tokens)
    if not rows or not rows[0][0].upper().endswith("OFF"):
        raise OffError("not a text OFF file (the first line should be OFF / 4OFF / nOFF)")

    header = rows[0][0].upper()
    rest = rows[0][1:]
    rows = rows[1:]
    if rest:
        rows.insert(0, rest)
    try:
        if header.endswith("NOFF"):
            dim = int(rows[0][0])
            rows[0] = rows[0][1:]
            if not rows[0]:
                rows.pop(0)
            if dim != 4:
                raise OffError(f"file is {dim}-dimensional, expected 4")
        counts = [int(t) for t in rows[0]]
        n_vertices = counts[0]
        vertex_rows = rows[1 : 1 + n_vertices]
        if n_vertices < 5 or len(vertex_rows) < n_vertices:
            raise OffError("vertex list is missing, truncated or too small for a 4D shape")
        if any(len(r) < 4 for r in vertex_rows):
            raise OffError(
                "vertices have fewer than 4 coordinates, so this is a 3D file "
                "and there is no 4D shape to convert"
            )
        vertices = [[float(t) for t in r[:4]] for r in vertex_rows]
    except (ValueError, IndexError) as error:
        raise OffError(f"could not parse the file ({error})") from None
    if not all(math.isfinite(x) for v in vertices for x in v):
        raise OffError("a vertex coordinate is NaN or infinite")
    decimals = max(
        (len(t.lower().split("e")[0].partition(".")[2]) for r in vertex_rows for t in r[:4]),
        default=0,
    )
    rounding = 10.0**-decimals if decimals >= 3 else 0.0
    return vertices, counts, rows[1 + n_vertices :], rounding


def parse_element(row, limit):
    """'n i1 .. in [colour]' -> ([i1..in], [colour tokens])."""
    try:
        n = int(row[0])
        indices = [int(t) for t in row[1 : n + 1]]
    except ValueError:
        raise Unusable(f"bad face/cell line: {' '.join(row)}") from None
    if n < 1 or len(indices) != n or not all(0 <= i < limit for i in indices):
        raise Unusable(f"face/cell line has missing or out-of-range indices: {' '.join(row)}")
    return indices, row[n + 1 :]


def to_rgb(tokens):
    """OFF colour (0-255 ints or 0-1 floats) -> (r, g, b) in 0-255, or None."""
    if len(tokens) < 3:
        return None
    try:
        if any("." in t for t in tokens[:3]):
            values = [round(float(t) * 255) for t in tokens[:3]]
        else:
            values = [int(t) for t in tokens[:3]]
    except ValueError:
        return None
    return tuple(min(255, max(0, v)) for v in values)


def split_counts(counts, n_rows):
    """Work out (face count, cell count) from the size line."""
    candidates = []
    if len(counts) >= 4:
        candidates = [(counts[1], counts[3]), (counts[2], counts[3])]  # V F E C, V E F C
    elif len(counts) == 3:
        candidates = [(counts[1], counts[2]), (counts[1], 0)]  # V F C, V F E
    elif len(counts) == 2:
        candidates = [(counts[1], 0)]
    for faces, cells in candidates:
        if faces > 0 and faces + cells == n_rows:
            return faces, cells
    raise Unusable(f"the size line {counts} does not match the {n_rows} lines after the vertices")


# --------------------------------------------------------------------------
# Building the face/cell structure
# --------------------------------------------------------------------------
def from_file_structure(vertices, counts, body):
    """Return (faces, cells, face_colours, cell_colours, description)."""
    if not body:
        raise Unusable("the file only has vertices")
    n_faces, n_cells = split_counts(counts, len(body))
    parsed = [parse_element(r, len(vertices)) for r in body[:n_faces]]
    faces = [p[0] for p in parsed]

    if n_cells:
        cell_parsed = [parse_element(r, n_faces) for r in body[n_faces:]]
        return (
            faces,
            [p[0] for p in cell_parsed],
            [to_rgb(p[1]) for p in parsed],
            [to_rgb(p[1]) for p in cell_parsed],
            "kept the file's cells",
        )

    # No cells: maybe every "face" is really a tetrahedron. A few may be
    # collapsed (at poles); clean() removes those.
    tol = EPS * shape_size(vertices)
    if not all(len(f) == 4 for f in faces) or 2 * sum(
        affine_rank([vertices[i] for i in f], tol) == 3 for f in faces
    ) <= len(faces):
        raise Unusable("the file has no 3D cells")
    triangles, lookup, cells = [], {}, []
    for a, b, c, d in faces:
        cell = []
        for tri in ((a, b, c), (a, b, d), (a, c, d), (b, c, d)):
            key = frozenset(tri)
            if key not in lookup:
                lookup[key] = len(triangles)
                triangles.append(list(tri))
            cell.append(lookup[key])
        cells.append(cell)
    return (
        triangles,
        cells,
        [None] * len(triangles),
        [to_rgb(p[1]) for p in parsed],
        "split tetrahedra into triangles and cells",
    )


def clean(vertices, faces, cells, face_colours, cell_colours):
    """Weld duplicate points, drop collapsed faces/cells, check the result is closed."""
    tol = EPS * shape_size(vertices)

    # Weld vertices closer than tol (common at the poles of curved shapes).
    grid, points, remap = {}, [], []
    offsets = [(a, b, c, d) for a in (-1, 0, 1) for b in (-1, 0, 1)
               for c in (-1, 0, 1) for d in (-1, 0, 1)]
    for v in vertices:
        key = tuple(math.floor(x / tol) for x in v)
        found = next(
            (i for o in offsets
             for i in grid.get(tuple(k + j for k, j in zip(key, o)), ())
             if math.dist(points[i], v) <= tol),
            None,
        )
        if found is None:
            found = len(points)
            points.append(v)
            grid.setdefault(key, []).append(found)
        remap.append(found)

    new_faces, new_face_colours, face_map, seen = [], [], {}, {}
    for old, face in enumerate(faces):
        loop = []
        for i in face:
            if not loop or loop[-1] != remap[i]:
                loop.append(remap[i])
        while len(loop) > 1 and loop[0] == loop[-1]:
            loop.pop()
        if len(loop) < 3 or affine_rank([points[i] for i in loop], tol, 2) < 2:
            continue  # collapsed to a point or a line
        if len(set(loop)) != len(loop):
            raise Unusable("a face visits the same vertex twice")
        key = frozenset(loop)
        if key not in seen:
            seen[key] = len(new_faces)
            new_faces.append(loop)
            new_face_colours.append(face_colours[old])
        face_map[old] = seen[key]

    new_cells, new_cell_colours, seen_cells = [], [], set()
    for old, cell in enumerate(cells):
        ids = list(dict.fromkeys(face_map[f] for f in cell if f in face_map))
        used = {i for f in ids for i in new_faces[f]}
        if len(ids) < 4 or affine_rank([points[i] for i in used], tol, 3) < 3:
            continue  # collapsed cell
        if frozenset(ids) in seen_cells:
            continue
        edge_uses = Counter(e for f in ids for e in loop_edges(new_faces[f]))
        if any(n != 2 for n in edge_uses.values()):
            raise Unusable(
                f"cell {old} is not a closed polyhedron (cells may list vertices instead "
                "of faces, or face vertices may be out of loop order)"
            )
        seen_cells.add(frozenset(ids))
        new_cells.append(ids)
        new_cell_colours.append(cell_colours[old])

    face_uses = Counter(f for cell in new_cells for f in cell)
    if len(new_cells) < 5 or any(n != 2 for n in face_uses.values()):
        raise Unusable("the cells do not form a closed 4D surface")

    # Drop faces and vertices that nothing uses.
    keep_faces = sorted(face_uses)
    face_index = {old: new for new, old in enumerate(keep_faces)}
    keep_points = sorted({i for f in keep_faces for i in new_faces[f]})
    point_index = {old: new for new, old in enumerate(keep_points)}
    return (
        [points[i] for i in keep_points],
        [[point_index[i] for i in new_faces[f]] for f in keep_faces],
        [[face_index[f] for f in cell] for cell in new_cells],
        [new_face_colours[f] for f in keep_faces],
        new_cell_colours,
    )


def order_polygon(ids, pts, flat):
    """Boundary loop of a flat convex polygon in 4D (collinear points dropped)."""
    import numpy as np

    local = pts[ids] - pts[ids].mean(axis=0)
    plane = np.linalg.svd(local, full_matrices=False)[2][:2]
    xy = local @ plane.T
    order = sorted(range(len(ids)), key=lambda i: (xy[i, 0], xy[i, 1]))

    def half(sequence):
        chain = []
        for i in sequence:
            while len(chain) > 1:
                a, b = xy[chain[-1]] - xy[chain[-2]], xy[i] - xy[chain[-2]]
                # keep the corner only if it sticks out from the straight line
                if a[0] * b[1] - a[1] * b[0] > flat * np.linalg.norm(b):
                    break
                chain.pop()
            chain.append(i)
        return chain[:-1]

    return [ids[i] for i in half(order) + half(order[::-1])]


def from_convex_hull(vertices, rounding=0.0, forced=False):
    try:
        import numpy as np
        from scipy.spatial import ConvexHull
    except ImportError:
        raise OffError(
            "this file needs the convex hull rebuild: pip install numpy scipy"
        ) from None

    pts = np.array(vertices, dtype=float)
    size = shape_size(vertices)
    scaled = (pts - pts.mean(axis=0)) / size
    # How far off a hyperplane a point may be and still count as on it.
    flat = min(max(5e-6, 2 * rounding / size), 2e-3)
    try:
        hull = ConvexHull(scaled)
    except Exception as error:  # QhullError: flat or degenerate input
        first_line = (str(error).strip().splitlines() or [type(error).__name__])[0]
        raise OffError(f"could not build a 4D hull (is the shape flat?): {first_line}") from None

    # A convex surface keeps (almost) all of its points on the hull.
    normals, offsets = hull.equations[:, :4].T, hull.equations[:, 4]
    inner = sum(
        int(((scaled[i : i + 256] @ normals + offsets).max(axis=1) < -max(flat, 1e-3)).sum())
        for i in range(0, len(scaled), 256)
    )
    if not forced and inner > max(2, len(vertices) // 100):
        raise OffError(
            f"{inner} vertices are inside the convex hull, so the shape isn't convex and a "
            "hull would change it. The file needs 3D cells or tetrahedra "
            "(if the shape really is convex, run with --hull)"
        )

    # Qhull returns tetrahedra. Grow each cell outwards from its largest one,
    # taking in neighbours that lie in the same hyperplane.
    corners = scaled[hull.simplices]
    spans = corners[:, 1:] - corners[:, :1]
    volumes = np.linalg.det(spans @ spans.transpose(0, 2, 1))
    group = [-1] * len(hull.simplices)
    for seed in np.argsort(-volumes, kind="stable"):
        if group[seed] >= 0:
            continue
        group[seed] = int(seed)
        normal, offset = hull.equations[seed][:4], hull.equations[seed][4]
        stack = [int(seed)]
        while stack:
            for j in hull.neighbors[stack.pop()]:
                if group[j] < 0 and np.abs(corners[j] @ normal + offset).max() <= flat:
                    group[j] = int(seed)
                    stack.append(int(j))

    # The ridge between two different cells is (part of) a 2D face.
    ridges = {}
    for i, neighbours in enumerate(hull.neighbors):
        for k, j in enumerate(neighbours):
            a, b = group[i], group[int(j)]
            if a < b:
                shared = (int(v) for n, v in enumerate(hull.simplices[i]) if n != k)
                ridges.setdefault((a, b), set()).update(shared)

    faces, cell_map = [], {}
    for (a, b), ids in sorted(ridges.items()):
        ids = sorted(ids)
        if affine_rank([scaled[i].tolist() for i in ids], flat, 2) < 2:
            continue
        for cell in (a, b):
            cell_map.setdefault(cell, []).append(len(faces))
        faces.append(order_polygon(ids, scaled, flat))
    cells = [cell_map[c] for c in sorted(cell_map)]

    on_surface = {i for f in faces for i in f}
    note = "rebuilt as the convex hull of the vertices"
    if len(on_surface) < len(vertices):
        note += f" ({len(vertices) - len(on_surface)} inner or redundant vertices dropped)"
    return faces, cells, [None] * len(faces), [None] * len(cells), note


# --------------------------------------------------------------------------
# Orientation and writing
# --------------------------------------------------------------------------
def godot_normal(vertices, face_a, face_b):
    """Normal PolyMesh4D derives for a cell whose first two faces are a and b."""
    edges_a, edges_b = loop_edges(face_a), loop_edges(face_b)
    for i, edge in enumerate(edges_a):
        if edge in edges_b:
            j = edges_b.index(edge)
            p = vertices[face_a[(i + 2) % len(face_a)]]
            q = vertices[face_b[(j + 2) % len(face_b)]]
            lo, hi = vertices[edge[0]], vertices[edge[1]]
            return perpendicular(sub(lo, p), sub(hi, p), sub(q, p))
    return None  # the faces don't share an edge


def propagate(links):
    """Sign every node so that sign[b] == sign[a] * relation for each link.

    Returns (signs, connected groups)."""
    signs, groups = {}, []
    for start in links:
        if start in signs:
            continue
        signs[start] = 1
        group = [start]
        for node in group:  # the list grows while we walk it
            for other, relation in links[node]:
                if other not in signs:
                    signs[other] = signs[node] * relation
                    group.append(other)
                elif signs[other] != signs[node] * relation:
                    raise OffError("the surface can't be oriented (twisted or pinched cells)")
        groups.append(group)
    return signs, groups


def face_signs(faces, cell):
    """+1/-1 per face so neighbours run along their shared edge in opposite directions."""
    crossings = {}
    for f in cell:
        loop = faces[f]
        for a, b in zip(loop, loop[1:] + loop[:1]):
            crossings.setdefault((min(a, b), max(a, b)), []).append((f, 1 if a < b else -1))
    links = {f: [] for f in cell}
    for (f, way_f), (g, way_g) in crossings.values():
        links[f].append((g, -way_f * way_g))
        links[g].append((f, -way_f * way_g))
    signs, groups = propagate(links)
    if len(groups) != 1:
        raise OffError("a cell is made of separate pieces, which isn't supported")
    return signs


def outward_normals(vertices, faces, cells):
    """Return (outward normal per cell, number of separate surfaces).

    Neighbouring cells must induce opposite directions on their shared face; that
    fixes all cells relative to each other. The sign of the enclosed 4D volume
    then says which way is out. No convexity is assumed."""
    local = [face_signs(faces, cell) for cell in cells]
    owners = {}
    for c, cell in enumerate(cells):
        for f in cell:
            owners.setdefault(f, []).append(c)
    links = {c: [] for c in range(len(cells))}
    for f, (a, b) in owners.items():
        relation = -local[a][f] * local[b][f]
        links[a].append((b, relation))
        links[b].append((a, relation))
    cell_signs, groups = propagate(links)

    middle = centroid(vertices)
    normals, volumes = [], []
    for c, cell in enumerate(cells):
        apex = centroid([vertices[i] for i in {i for f in cell for i in faces[f]}])
        total = [0.0] * 4
        for f in cell:
            p = [sub(vertices[i], apex) for i in faces[f]]
            for k in range(1, len(p) - 1):
                n = perpendicular(p[0], p[k], p[k + 1])
                total = [t + cell_signs[c] * local[c][f] * x for t, x in zip(total, n)]
        normals.append(total)
        volumes.append(dot(sub(apex, middle), total))
    for group in groups:
        if sum(volumes[c] for c in group) < 0:
            for c in group:
                normals[c] = [-x for x in normals[c]]
    return normals, len(groups)


def orient(vertices, faces, cells, keep_orientation):
    """Put a well-shaped pair of adjacent faces first, in the order giving an outward normal.

    Returns the number of separate surfaces."""
    normals, pieces = outward_normals(vertices, faces, cells)
    for number, cell in enumerate(cells):
        outward = normals[number]
        if keep_orientation:
            original = godot_normal(vertices, faces[cell[0]], faces[cell[1]])
            if original and math.sqrt(dot(original, original)) > 0:
                outward = original

        # Take the pair with the strongest normal, so thin cells stay stable.
        best, best_score = None, 0.0
        owners = {}
        for f in cell:
            for edge in loop_edges(faces[f]):
                owners.setdefault(edge, []).append(f)
        for a, b in owners.values():
            normal = godot_normal(vertices, faces[a], faces[b])
            score = dot(normal, normal)
            if score > best_score:
                best, best_score = (a, b, normal), score
        if best is None:
            raise OffError(f"cell {number} is degenerate, cannot orient it")
        a, b, normal = best
        if dot(normal, outward) < 0:
            a, b = b, a
        cells[number] = [a, b] + [f for f in cell if f not in (a, b)]
    return pieces


def format_number(x):
    text = f"{x:.10f}".rstrip("0")
    if text.endswith("."):
        text += "0"
    return "0.0" if text == "-0.0" else text


def element_line(indices, colour):
    return " ".join(map(str, [len(indices), *indices, *(colour or ())]))


def write_off(path, vertices, faces, cells, face_colours, cell_colours):
    n_edges = len({e for f in faces for e in loop_edges(f)})
    lines = ["4OFF", "# Vertices, Faces, Edges, Cells",
             f"{len(vertices)} {len(faces)} {n_edges} {len(cells)}", "", "# Vertices"]
    lines += [" ".join(map(format_number, v)) for v in vertices]
    lines += ["", "# Faces"]
    lines += [element_line(f, c) for f, c in zip(faces, face_colours)]
    lines += ["", "# Cells"]
    lines += [element_line(f, c) for f, c in zip(cells, cell_colours)]
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
    return n_edges


def convert(source, force_hull=False, keep_orientation=False):
    vertices, counts, body, rounding = read_off(source)
    reason = "--hull was given" if force_hull else None
    if not force_hull:
        try:
            *structure, note = from_file_structure(vertices, counts, body)
            result = clean(vertices, *structure)
        except Unusable as error:
            reason = str(error)
    if reason:
        if any(part in source.stem.lower() for part in HOLED_NAME_PARTS):
            raise OffError(
                f"{reason}. This shape has a hole that a convex hull would fill in, "
                "so the file needs 3D cells or tetrahedra"
            )
        *structure, note = from_convex_hull(vertices, rounding, force_hull)
        note += f"\n      because {reason}"
        try:
            result = clean(vertices, *structure)
        except Unusable as error:
            raise OffError(
                f"the hull rebuild failed ({error}); try exporting with more decimal places"
            ) from None
        keep_orientation = False  # the hull has no original orientation

    vertices, faces, cells, face_colours, cell_colours = result
    pieces = orient(vertices, faces, cells, keep_orientation)
    target = source.with_name(source.stem + "_poly.off")
    n_edges = write_off(target, vertices, faces, cells, face_colours, cell_colours)
    print(f"OK    {source.name} -> {target.name}: {len(vertices)} vertices, "
          f"{len(faces)} faces, {n_edges} edges, {len(cells)} cells")
    print(f"      {note}")
    if len(vertices) - n_edges + len(faces) - len(cells) != 0:
        print("      WARNING: V - E + F - C is not 0, so the surface may be pinched "
              "or broken. Check this shape in Godot")
    if pieces > 1:
        print(f"      WARNING: {pieces} separate surfaces, each pointed outward on its own "
              "(wrong for an inner cavity; see --keep-orientation)")
    if n_edges > 20000:
        print("      note: godot-4d may be slow to import a mesh this large")


def main():
    parser = argparse.ArgumentParser(description="Make *_poly.off copies for godot-4d PolyMesh4D.")
    parser.add_argument("paths", nargs="*", type=Path, help="OFF files or folders (default: .)")
    parser.add_argument("--hull", action="store_true",
                        help="ignore faces/cells and take the convex hull of the vertices")
    parser.add_argument("--keep-orientation", action="store_true",
                        help="keep the file's cell orientation instead of working out outward normals")
    args = parser.parse_args()

    sources, failed = [], 0
    for path in args.paths or [Path(".")]:
        if path.is_dir():
            for name in DEFAULT_NAMES:
                if (path / name).is_file():
                    sources.append(path / name)
                elif name not in OPTIONAL_NAMES:
                    print(f"SKIP  {path / name}: not found")
                    failed += 1
            if not any((path / n).is_file() for n in OPTIONAL_NAMES):
                print(f"SKIP  {path / 'sphereinder.off'}: not found")
                failed += 1
        else:
            sources.append(path)

    for source in sources:
        if source.stem.endswith("_poly"):
            print(f"SKIP  {source.name}: already a _poly file")
            continue
        try:
            convert(source, args.hull, args.keep_orientation)
        except (OffError, Unusable, OSError) as error:
            print(f"FAIL  {source}: {error}")
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())