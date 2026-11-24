@tool
extends EditorScript

func _run() -> void:
	var mesh := load_off_as_poly_mesh("res://120-cell.off")
	if mesh:
		var err := ResourceSaver.save(mesh, "res://120-cell_poly.tres")
		EditorInterface.get_resource_filesystem().scan()
		print("Save result: ", err, " | Vertices: ", mesh.poly_cell_vertices.size(), " | Faces: ", mesh.poly_cell_indices.size())

func load_off_as_poly_mesh(path: String) -> ArrayPolyMesh4D:
	var text := FileAccess.get_file_as_string(path)
	var clean_lines: Array[String] = []
	for raw in text.split("\n", false):
		var line: String = raw.get_slice("#", 0).strip_edges()
		if not line.is_empty():
			clean_lines.append(line)

	var counts_line: String = clean_lines.get(1)
	var vert_count := int(counts_line.get_slice(" ", 0))
	var face_count := int(counts_line.get_slice(" ", 1))

	var verts := PackedVector4Array()
	for i in range(2, 2 + vert_count):
		var v_line: String = clean_lines.get(i)
		var x := float(v_line.get_slice(" ", 0))
		var y := float(v_line.get_slice(" ", 1))
		var z := float(v_line.get_slice(" ", 2))
		var w := float(v_line.get_slice(" ", 3))
		verts.append(Vector4(x, y, z, w))

	var faces: Array[Array] = []
	for i in range(2 + vert_count, 2 + vert_count + face_count):
		var f_line: String = clean_lines.get(i)
		var n := int(f_line.get_slice(" ", 0))
		var face: Array = []
		for k in range(1, n + 1):
			face.append(int(f_line.get_slice(" ", k)))
		faces.append(face)

	var poly_mesh := ArrayPolyMesh4D.new()
	poly_mesh.poly_cell_vertices = verts
	poly_mesh.poly_cell_indices = faces
	return poly_mesh
