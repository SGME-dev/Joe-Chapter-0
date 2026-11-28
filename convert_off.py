#!/usr/bin/env python3
"""Convert 4D .off files into the layout godot-4d imports as a PolyMesh4D.

Writes <name>_poly.off next to each input. The originals are never modified.

    python convert_off.py                      # the default shapes, current folder
    python convert_off.py path/to/folder       # the default shapes, another folder
    python convert_off.py a.off b.off          # specific files
    python convert_off.py --hull a.off         # ignore faces/cells, use vertices only
    python convert_off.py --max-cells 800      # fewer cells (default 2000, 0 = no limit)
    python convert_off.py --standard           # see "Tori" below

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
The hull rebuild only works for convex shapes.

Tori (file names containing torus, tori or tiger) are never hulled, which would
fill the hole. If their cells can't be used, the points are matched against a
torisphere, spheritorus, ditorus or tiger, and new cells are built on the shape
that matches, with its radii. If none match, nothing is written unless you add
--standard, which writes a standard torus of the same size instead.

Too many cells: meshes over --max-cells are rebuilt more coarsely (hyperspheres
and tori on a regular grid, other convex shapes from a subset of their points).
Rebuilt meshes don't keep the file's colours.

Normals are pointed out of the solid, worked out from how the cells connect, so
this works with or without holes. --keep-orientation keeps the file's own.
"""

import argparse
import itertools
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
DEFAULT_MAX_CELLS = 2000
TORUS_KINDS = ("torisphere", "spheritorus", "ditorus", "tiger")
# name: (cells along each grid direction, fewest allowed, direction wraps around?)
GRIDS = {
    "hypersphere": ((10, 10, 20), (3, 3, 4), (False, False, True)),
    "torisphere": ((10, 16, 12), (3, 4, 4), (False, True, True)),
    "spheritorus": ((24, 7, 12), (4, 3, 4), (True, False, True)),
    "ditorus": ((16, 12, 10), (4, 4, 4), (True, True, True)),
    "tiger": ((14, 14, 10), (4, 4, 4), (True, True, True)),
}
STANDARD_RADII = {  # (core radii..., tube radius), used by --standard
    "torisphere": (1.0, 0.4),
    "spheritorus": (1.0, 0.35),
    "ditorus": (2.0, 0.8, 0.3),
    "tiger": (1.0, 1.0, 0.4),
}

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
# Recognising shapes, rebuilding them and reducing cell counts
# --------------------------------------------------------------------------
def import_numeric():
    try:
        import numpy as np
        from scipy.optimize import least_squares
        from scipy.spatial import ConvexHull
    except ImportError:
        raise OffError("this file needs numpy and scipy: pip install numpy scipy") from None
    return np, least_squares, ConvexHull


def surface_point(kind, u, v, w, radii):
    """Point on a shape for grid coordinates u, v, w in 0..1."""
    wraps = GRIDS[kind][2]
    a, b, c = (t * (2 if wrap else 1) * math.pi for t, wrap in zip((u, v, w), wraps))
    sin, cos = math.sin, math.cos
    r = radii[-1]
    if kind == "hypersphere":
        return (r * sin(a) * sin(b) * cos(c), r * sin(a) * sin(b) * sin(c),
                r * sin(a) * cos(b), r * cos(a))
    if kind == "torisphere":  # a 2-sphere, thickened by a circle
        s = radii[0] + r * cos(c)
        return (s * sin(a) * cos(b), s * sin(a) * sin(b), s * cos(a), r * sin(c))
    if kind == "spheritorus":  # a circle, thickened by a 2-sphere
        s = radii[0] + r * sin(b) * cos(c)
        return (s * cos(a), s * sin(a), r * sin(b) * sin(c), r * cos(b))
    if kind == "ditorus":  # a torus, thickened by a circle
        t = radii[1] + r * cos(c)
        s = radii[0] + t * cos(b)
        return (s * cos(a), s * sin(a), t * sin(b), r * sin(c))
    s, t = radii[0] + r * cos(c), radii[1] + r * sin(c)  # tiger
    return (s * cos(a), s * sin(a), t * cos(b), t * sin(b))


def tube_offsets(np, kind, q, core):
    """Offsets from a torus's core circle/sphere; their length is the tube radius."""
    a, b, c, d = q.T
    if kind == "torisphere":
        return np.stack([np.sqrt(a * a + b * b + c * c) - core[0], d], axis=1)
    if kind == "spheritorus":
        return np.stack([np.hypot(a, b) - core[0], c, d], axis=1)
    if kind == "ditorus":
        t = np.hypot(np.hypot(a, b) - core[0], c)
        return np.stack([t - core[1], d], axis=1)
    return np.stack([np.hypot(a, b) - core[0], np.hypot(c, d) - core[1]], axis=1)


def axis_orders(kind):
    """The distinct ways the file's x y z w can map onto the shape's own axes."""
    key = {
        "torisphere": lambda p: p[3],
        "spheritorus": lambda p: frozenset(p[:2]),
        "ditorus": lambda p: (frozenset(p[:2]), p[2]),
        "tiger": lambda p: frozenset((frozenset(p[:2]), frozenset(p[2:]))),
    }[kind]
    return list({key(p): p for p in itertools.permutations(range(4))}.values())


def fit_torus(points, rounding):
    """Find the torus the points lie on (or fill). Returns (kind, radii, axes, centre)."""
    np, least_squares, _ = import_numeric()
    pts = np.array(points, dtype=float)
    centre = (pts.max(axis=0) + pts.min(axis=0)) / 2
    size = np.linalg.norm(pts - centre, axis=1).max()
    if np.abs(centre).max() < 0.03 * size:
        centre = np.zeros(4)

    def middle(x):
        return (x.max() + x.min()) / 2

    best, best_score = None, None
    for kind in TORUS_KINDS:
        for order in axis_orders(kind):
            q = (pts - centre)[:, order]
            first = np.hypot(q[:, 0], q[:, 1])
            if kind == "torisphere":
                core = [middle(np.linalg.norm(q[:, :3], axis=1))]
            elif kind == "spheritorus":
                core = [middle(first)]
            elif kind == "ditorus":
                core = [middle(first)]
                core.append(middle(np.hypot(first - core[0], q[:, 2])))
            else:
                core = [middle(first), middle(np.hypot(q[:, 2], q[:, 3]))]
            offsets = tube_offsets(np, kind, q, core)
            r = np.linalg.norm(offsets, axis=1).max()
            spread = (offsets.max(axis=0) - offsets.min(axis=0)) / 2
            if r < 0.01 * size or spread.min() < 0.8 * r or spread.max() > 1.2 * r:
                continue  # the tube isn't round, or has no thickness

            outer = q[np.linalg.norm(offsets, axis=1) >= 0.9 * r]

            def error(p):  # p = centre shift, core radii, tube radius
                return np.linalg.norm(
                    tube_offsets(np, kind, outer - p[:4], p[4:-1]), axis=1
                ) - p[-1]

            # The centre guessed from the bounding box can be slightly off for
            # coarse files, so fit it too: once tightly, once starting loosely.
            start = [0.0] * 4 + [*core, r]
            for scales in ((0.002,), (0.05, 0.002)):
                fit = np.array(start, dtype=float)
                for scale in scales:
                    fit = least_squares(error, fit, loss="cauchy", f_scale=scale * start[-1]).x
                shift, core, radius = fit[:4], fit[4:-1], fit[-1]
                offsets = tube_offsets(np, kind, q - shift, core)
                miss = np.linalg.norm(offsets, axis=1) - radius
                tolerance = max(0.004 * radius, 3 * rounding)
                on = np.abs(miss) <= tolerance
                # Nothing may stick out, and enough points must lie right on the
                # surface, going all the way round the tube.
                if radius <= 0 or miss.max() > max(0.01 * radius, 3 * rounding):
                    continue
                if on.sum() < max(30, 0.02 * len(pts)):
                    continue
                around = offsets[on]
                if (around.max(axis=0) < 0.7 * radius).any() or (
                    around.min(axis=0) > -0.7 * radius
                ).any():
                    continue
                if kind in ("torisphere", "spheritorus"):
                    holed = core[0] > 1.02 * radius
                elif kind == "ditorus":
                    holed = core[1] > 1.02 * radius and core[0] > core[1] + 1.02 * radius
                else:
                    holed = min(core) > 1.02 * radius
                if not holed:
                    continue
                # The points must reach out along all four axes, both ways. This
                # rejects flat surfaces that only trace part of the shape.
                if kind == "torisphere":
                    reach = [core[0] + radius] * 3 + [radius]
                elif kind == "spheritorus":
                    reach = [core[0] + radius] * 2 + [radius] * 2
                elif kind == "ditorus":
                    outer_reach = core[0] + core[1] + radius
                    reach = [outer_reach] * 2 + [core[1] + radius, radius]
                else:
                    reach = [core[0] + radius] * 2 + [core[1] + radius] * 2
                used = q[on] - shift
                limit = 0.6 * np.array(reach)
                if (used.max(axis=0) < limit).any() or (used.min(axis=0) > -limit).any():
                    continue
                score = (int(on.sum()), -float(np.sqrt(np.mean(miss[on] ** 2))))
                if best_score is None or score > best_score:
                    best_score = score
                    middle_point = centre.copy()
                    middle_point[list(order)] += shift
                    best = (kind, [float(x) for x in (*core, radius)], order,
                            middle_point.tolist())
    return best


def fit_hypersphere(points):
    """Like fit_torus, for points spread all over one 3-sphere."""
    np, _, ConvexHull = import_numeric()
    pts = np.array(points, dtype=float)
    system = np.hstack([2 * pts, np.ones((len(pts), 1))])
    solution = np.linalg.lstsq(system, (pts**2).sum(axis=1), rcond=None)[0]
    centre = solution[:4]
    radius = math.sqrt(max(0.0, solution[4] + centre @ centre))
    if radius <= 0 or np.abs(np.linalg.norm(pts - centre, axis=1) - radius).max() > 0.01 * radius:
        return None
    # Duocylinders and spherinders also have all corners on a sphere, so make
    # sure the flat cells between the points stay close to it.
    try:
        equations = ConvexHull((pts - centre) / radius).equations
    except Exception:
        return None
    if (-equations[:, 4]).min() < 0.85:
        return None
    if np.abs(centre).max() < 0.01 * radius:
        centre = np.zeros(4)
    return "hypersphere", [radius], (0, 1, 2, 3), centre.tolist()


def grid_counts(kind, max_cells):
    base, fewest, _ = GRIDS[kind]
    scale = (max_cells / math.prod(base)) ** (1 / 3) if max_cells else 1.0
    counts = [max(low, round(n * scale)) for n, low in zip(base, fewest)]
    while max_cells and math.prod(counts) > max_cells:
        spare = [i for i in range(3) if counts[i] > fewest[i]]
        if not spare:
            break
        counts[max(spare, key=lambda i: counts[i] / base[i])] -= 1
    return counts


def build_shape(shape, max_cells):
    """Closed mesh with hexahedral cells (collapsed ones at poles) on a recognised shape."""
    kind, radii, order, centre = shape
    counts = grid_counts(kind, max_cells)
    ids, vertices = {}, []
    for spot in itertools.product(*(range(n + 1) for n in counts)):
        local = surface_point(kind, *(i / n for i, n in zip(spot, counts)), radii)
        point = list(centre)
        for axis, value in zip(order, local):
            point[axis] += value
        ids[spot] = len(vertices)
        vertices.append(point)

    faces, cells, seen = [], [], {}
    for base in itertools.product(*(range(n) for n in counts)):
        cell = []
        for axis in range(3):
            i, j = (a for a in range(3) if a != axis)
            for side in (0, 1):
                loop = []
                for di, dj in ((0, 0), (1, 0), (1, 1), (0, 1)):
                    spot = list(base)
                    spot[axis] += side
                    spot[i] += di
                    spot[j] += dj
                    loop.append(ids[tuple(spot)])
                if tuple(loop) not in seen:
                    seen[tuple(loop)] = len(faces)
                    faces.append(loop)
                cell.append(seen[tuple(loop)])
        cells.append(cell)
    # clean() welds the seams and poles and removes the collapsed faces.
    return clean(vertices, faces, cells, [None] * len(faces), [None] * len(cells))


def describe(shape):
    kind, radii, _, _ = shape
    return f"{kind} (radii {', '.join(f'{r:.4g}' for r in radii)})"


def rebuild_torus(source, vertices, counts, body, rounding, max_cells, standard, reason):
    """Mesh for a torus file whose own cells can't be used. Returns (mesh, note)."""
    shape = fit_torus(vertices, rounding)
    if shape:
        note = f"built new cells on the shape the points match: a {describe(shape)}"
        return build_shape(shape, max_cells), note + f"\n      because {reason}"

    name = source.stem.lower()
    kind = next((k for k in TORUS_KINDS if k in name), "ditorus")
    if not standard:
        sizes = dict(Counter(row[0] for row in body))
        raise OffError(
            f"{reason}, and the points don't match a torus this script knows, so nothing "
            f"was written.\n      File details: {len(vertices)} vertices, size line {counts}, "
            f"later lines by first number {sizes}.\n      Add --standard to write a standard "
            f"{kind} of the same size instead, or share the file so it can be supported."
        )
    centre = [(max(c) + min(c)) / 2 for c in zip(*vertices)]
    reach = max(math.dist(v, centre) for v in vertices)
    radii = STANDARD_RADII[kind]
    unit = build_shape((kind, list(radii), (0, 1, 2, 3), [0.0] * 4), max_cells)[0]
    scale = reach / max(math.hypot(*v) for v in unit)
    shape = (kind, [r * scale for r in radii], (0, 1, 2, 3), centre)
    note = (f"STANDARD SHAPE, not your geometry: a {describe(shape)} sized like the file"
            f"\n      because {reason} and the points don't match a known torus")
    return build_shape(shape, max_cells), note


def thin_convex(vertices, max_cells, rounding):
    """Hull of an evenly spread subset of the points, as large as max_cells allows."""
    np, _, _ = import_numeric()
    pts = np.array(vertices, dtype=float)
    order = [0]  # farthest point sampling
    distance = ((pts - pts[0]) ** 2).sum(axis=1)
    while len(order) < len(pts):
        order.append(int(distance.argmax()))
        distance = np.minimum(distance, ((pts - pts[order[-1]]) ** 2).sum(axis=1))

    low, high, best = 5, len(pts), None
    while low <= high:
        count = (low + high) // 2
        subset = [vertices[i] for i in order[:count]]
        try:
            *structure, _ = from_convex_hull(subset, rounding, forced=True)
            mesh = clean(subset, *structure)
        except (OffError, Unusable):
            low = count + 1  # too few points to make a solid
            continue
        if len(mesh[2]) <= max_cells:
            best, low = mesh, count + 1
        else:
            high = count - 1
    return best


def reduce_cells(mesh, max_cells, holed, rounding):
    """Return (smaller mesh, note), or None if it can't be done safely."""
    vertices = mesh[0]
    shape = fit_torus(vertices, rounding) if holed else fit_hypersphere(vertices)
    if shape:
        return build_shape(shape, max_cells), f"rebuilt on a grid as a {describe(shape)}"
    if holed:
        return None
    try:
        from_convex_hull(vertices, rounding)  # raises if the shape isn't convex
    except OffError:
        return None
    smaller = thin_convex(vertices, max_cells, rounding)
    return (smaller, "convex hull of an evenly spread subset of the points") if smaller else None


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


def convert(source, force_hull=False, keep_orientation=False,
            max_cells=DEFAULT_MAX_CELLS, standard=False):
    vertices, counts, body, rounding = read_off(source)
    holed = any(part in source.stem.lower() for part in HOLED_NAME_PARTS)
    reason = "--hull was given" if force_hull else None
    if not force_hull:
        try:
            *structure, note = from_file_structure(vertices, counts, body)
            result = clean(vertices, *structure)
            if holed:
                outward_normals(*result[:3])  # make sure it can be oriented
        except (Unusable, OffError) as error:
            if isinstance(error, OffError) and not holed:
                raise
            reason = str(error)
    if reason and holed:
        result, note = rebuild_torus(
            source, vertices, counts, body, rounding, max_cells, standard, reason
        )
        keep_orientation = False
    elif reason:
        *structure, note = from_convex_hull(vertices, rounding, force_hull)
        note += f"\n      because {reason}"
        try:
            result = clean(vertices, *structure)
        except Unusable as error:
            raise OffError(
                f"the hull rebuild failed ({error}); try exporting with more decimal places"
            ) from None
        keep_orientation = False  # the hull has no original orientation

    too_many = None
    if max_cells and len(result[2]) > max_cells:
        before = len(result[2])
        reduced = reduce_cells(result, max_cells, holed, rounding)
        if reduced:
            result, how = reduced
            note += f"\n      reduced from {before} cells: {how}"
            keep_orientation = False
        if len(result[2]) > max_cells:
            too_many = f"      WARNING: could not get down to {max_cells} cells"

    vertices, faces, cells, face_colours, cell_colours = result
    pieces = orient(vertices, faces, cells, keep_orientation)
    target = source.with_name(source.stem + "_poly.off")
    n_edges = write_off(target, vertices, faces, cells, face_colours, cell_colours)
    print(f"OK    {source.name} -> {target.name}: {len(vertices)} vertices, "
          f"{len(faces)} faces, {n_edges} edges, {len(cells)} cells")
    print(f"      {note}")
    if too_many:
        print(too_many)
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
    parser.add_argument("--max-cells", type=int, default=DEFAULT_MAX_CELLS, metavar="N",
                        help=f"reduce meshes with more cells than this (default {DEFAULT_MAX_CELLS}, "
                             "0 = no limit)")
    parser.add_argument("--standard", action="store_true",
                        help="if a torus file can't be matched, write a standard torus of its size")
    args = parser.parse_args()
    if args.max_cells < 0:
        parser.error("--max-cells can't be negative")

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
            convert(source, args.hull, args.keep_orientation, args.max_cells, args.standard)
        except (OffError, Unusable, OSError) as error:
            print(f"FAIL  {source}: {error}")
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())