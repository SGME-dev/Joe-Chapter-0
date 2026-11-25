import math
from collections import defaultdict, deque
from pathlib import Path

def decimate_mesh(verts, faces, target_faces=1000):
    xs, ys, zs, ws = zip(*verts)
    span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), max(ws) - min(ws), 1e-5)

    grid_res = 12
    best_verts, best_faces = verts, faces
    while grid_res >= 4:
        step = span / grid_res
        cluster_map = {}
        new_verts = []
        remap = []
        for vx, vy, vz, vw in verts:
            key = (round(vx / step), round(vy / step), round(vz / step), round(vw / step))
            idx = cluster_map.get(key)
            if idx is None:
                idx = len(new_verts)
                cluster_map[key] = idx
                new_verts.append((vx, vy, vz, vw))
            remap.append(idx)

        seen_faces = set()
        new_faces = []
        for face in faces:
            mapped = []
            for v in face:
                mv = remap[v]
                if not mapped or mapped[-1] != mv:
                    mapped.append(mv)
            if len(mapped) > 1 and mapped == mapped[-1]:
                mapped.pop()
            if len(set(mapped)) >= 3:
                f_key = tuple(sorted(mapped))
                if f_key not in seen_faces:
                    seen_faces.add(f_key)
                    new_faces.append(mapped)

        best_verts, best_faces = new_verts, new_faces
        if len(new_faces) <= target_faces:
            break
        grid_res -= 2

    return best_verts, best_faces

def build_face_adjacency(faces):
    edge_to_faces = defaultdict(list)
    for f_idx, face in enumerate(faces):
        m = len(face)
        for i in range(m):
            a, b = face[i], face[(i + 1) % m]
            key = (a, b) if a < b else (b, a)
            edge_to_faces[key].append(f_idx)

    adj = defaultdict(set)
    for f_list in edge_to_faces.values():
        for i in range(len(f_list)):
            for j in range(i + 1, len(f_list)):
                adj[f_list[i]].add(f_list[j])
                adj[f_list[j]].add(f_list[i])
    return edge_to_faces, adj

def build_verified_cells(faces, face_adj, patch_size=10):
    visited = set()
    cells = []
    for start in range(len(faces)):
        if start in visited:
            continue
        first_nb = next((nb for nb in face_adj[start] if nb not in visited and nb != start), None)
        if first_nb is None:
            continue

        patch = [start, first_nb]
        visited.add(start)
        visited.add(first_nb)
        queue = deque(patch)

        while queue and len(patch) < patch_size:
            curr = queue.popleft()
            for nb in face_adj[curr]:
                if nb not in visited:
                    visited.add(nb)
                    patch.append(nb)
                    queue.append(nb)
                    if len(patch) >= patch_size:
                        break

        if len(patch) < 4:
            continue

        f0, f1, *rest = patch
        cells.append([f0, f1] + rest)
        cells.append([f1, f0] + rest)
    return cells

def main():
    script_dir = Path(__file__).resolve().parent
    input_path = script_dir / "hypersphere.off"
    if not input_path.exists():
        print("hypersphere.off not found!")
        return

    with open(input_path, "r", encoding="utf-8", errors="replace") as f:
        lines = []
        for raw_line in f:
            before_comment, _, _ = raw_line.replace("\r", "").partition("#")
            clean = before_comment.strip()
            if clean:
                lines.append(clean)

    it = iter(lines)
    header = next(it)
    first_parts = header.split()
    first_word, *rest_first = first_parts

    if first_word in ("OFF", "4OFF", "3OFF", "NOFF", "4NOFF"):
        counts_parts = rest_first if len(rest_first) >= 2 else next(it).split()
    else:
        counts_parts = first_parts

    vert_str, face_str, *_ = counts_parts
    vert_count = int(vert_str)
    face_count = int(face_str)

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
        if n >= 3 and len(indices) >= n:
            faces.append([int(idx) for idx in indices[:n]])

    verts, faces = decimate_mesh(verts, faces, target_faces=1000)
    edge_to_faces, face_adj = build_face_adjacency(faces)
    cells = build_verified_cells(faces, face_adj, patch_size=10)
    unique_edges = sorted(edge_to_faces.keys())

    output_path = script_dir / "hypersphere_poly.off"
    with open(output_path, "w", encoding="utf-8", newline="\n") as out:
        out.write("4OFF\n")
        out.write(f"{len(verts)} {len(faces)} {len(unique_edges)} {len(cells)}\n")
        for x, y, z, w in verts:
            out.write(f"{x} {y} {z} {w}\n")
        for face in faces:
            out.write(f"{len(face)} " + " ".join(str(v) for v in face) + "\n")
        for cell in cells:
            out.write(f"{len(cell)} " + " ".join(str(f) for f in cell) + "\n")

    print(f"Created {output_path.name}: {len(verts)} verts, {len(faces)} faces, {len(unique_edges)} edges, {len(cells)} cells")

if __name__ == "__main__":
    main()
