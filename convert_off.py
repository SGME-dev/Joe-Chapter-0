import glob
import math
import os
from collections import defaultdict

def dot4(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return ax * bx + ay * by + az * bz + aw * bw

def sub4(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (ax - bx, ay - by, az - bz, aw - bw)

def norm4(v):
    vx, vy, vz, vw = v
    length = math.sqrt(vx * vx + vy * vy + vz * vz + vw * vw)
    if length < 1e-9:
        return None
    return (vx / length, vy / length, vz / length, vw / length)

def hyperplane_normal_4d(u, v, w):
    ux, uy, uz, uw = u
    vx, vy, vz, vw = v
    wx, wy, wz, ww = w

    def det3(a1, a2, a3, b1, b2, b3, c1, c2, c3):
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

def find_3d_cells_for_convex_polytope(verts, faces):
    edge_to_faces = defaultdict(list)
    for f_idx, face in enumerate(faces):
        m = len(face)
        for i in range(m):
            a, b = face[i], face[(i + 1) % m]
            key = (a, b) if a < b else (b, a)
            edge_to_faces[key].append(f_idx)

    cell_hyperplanes = {}
    for (va, vb), adj_faces in edge_to_faces.items():
        if len(adj_faces) < 2:
            continue
        p0 = verts[va]
        e_vec = sub4(verts[vb], p0)
        for i in range(len(adj_faces)):
            f1 = faces[adj_faces[i]]
            v1_cand = next((v for v in f1 if v != va and v != vb), None)
            if v1_cand is None:
                continue
            u_vec = sub4(verts[v1_cand], p0)

            for j in range(i + 1, len(adj_faces)):
                f2 = faces[adj_faces[j]]
                v2_cand = next((v for v in f2 if v != va and v != vb), None)
                if v2_cand is None:
                    continue
                w_vec = sub4(verts[v2_cand], p0)

                normal = hyperplane_normal_4d(e_vec, u_vec, w_vec)
                if normal is None:
                    continue

                d = dot4(normal, p0)
                nx, ny, nz, nw = normal
                if d < 0:
                    nx, ny, nz, nw = -nx, -ny, -nz, -nw
                    normal = (nx, ny, nz, nw)
                    d = -d

                key = (round(nx, 3), round(ny, 3), round(nz, 3), round(nw, 3), round(d, 3))
                if key not in cell_hyperplanes:
                    coplanar_faces = []
                    for check_idx, check_face in enumerate(faces):
                        if all(abs(dot4(normal, verts[v]) - d) < 1e-3 for v in check_face):
                            coplanar_faces.append(check_idx)
                    if len(coplanar_faces) >= 4:
                        cell_hyperplanes[key] = tuple(sorted(coplanar_faces))

    unique_cells = sorted(set(cell_hyperplanes.values()))
    return [list(c) for c in unique_cells]

def convert_off_to_poly_off(input_path: str) -> None:
    if input_path.endswith("_poly.off") or input_path.endswith("_tri.off") or input_path.endswith("_fixed.off"):
        return

    with open(input_path, "r", encoding="utf-8", errors="replace") as f:
        lines = []
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

    vert_str, face_str, *extra_counts = counts_parts
    vert_count = int(vert_str)
    face_count = int(face_str)
    cell_count_rest = extra_counts[1:]
    existing_cell_count = int(next(iter(cell_count_rest), 0))

    if face_count == 0:
        print(f"Skipped (0 faces): {os.path.basename(input_path)}")
        return
    if face_count > 5000:
        print(f"Skipped (too large for real-time poly mesh: {face_count} faces): {os.path.basename(input_path)}")
        return

    verts = []
    for _ in range(vert_count):
        x_s, y_s, z_s, *w_rest = next(it).split()
        verts.append((
            float(x_s),
            float(y_s),
            float(z_s),
            float(next(iter(w_rest), 0.0)),
        ))

    faces = []
    for _ in range(face_count):
        parts = next(it).split()
        if not parts:
            continue
        n_str, *indices = parts
        n = int(n_str)
        if n < 3 or len(indices) < n:
            continue
        faces.append([int(idx) for idx in indices[:n]])

    cells = []
    for _ in range(existing_cell_count):
        try:
            parts = next(it).split()
        except StopIteration:
            break
        if not parts:
            continue
        n_str, *f_indices = parts
        n = int(n_str)
        if n >= 4 and len(f_indices) >= n:
            cells.append([int(idx) for idx in f_indices[:n]])

    if not cells:
        cells = find_3d_cells_for_convex_polytope(verts, faces)

    if not cells:
        print(f"Skipped (could not find closed >=4-face 3D cells): {os.path.basename(input_path)}")
        return

    unique_edges = set()
    for face in faces:
        m = len(face)
        for i in range(m):
            a, b = face[i], face[(i + 1) % m]
            unique_edges.add((a, b) if a < b else (b, a))

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

    print(f"Created (overwrote): {os.path.basename(output_path)} ({len(verts)} verts, {len(faces)} faces, {len(unique_edges)} edges, {len(cells)} cells)")

if __name__ == "__main__":
    for path in sorted(glob.glob("*.off")):
        try:
            convert_off_to_poly_off(path)
        except Exception as e:
            print(f"Skipped {path}: {e}")
