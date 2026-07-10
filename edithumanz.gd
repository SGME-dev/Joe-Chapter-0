@tool
extends Node

@export var mesh_to_split: ArrayWireMesh4D # Drag your grey or brown .tres file here
@export var output_prefix: String = "grey_" # "grey_" or "brown_"
@export var run_split: bool = false:
	set(value):
		if value:
			split_by_x_and_z()
			run_split = false

func split_by_x_and_z():
	if not mesh_to_split:
		print("Please assign a 4D Wire Mesh resource!")
		return
		
	var old_verts = mesh_to_split.vertices
	var old_edges = mesh_to_split.edge_indices
	
	# Reference your markers. (Make sure these node names match your scene tree exactly!)
	# We will dynamically calculate the min/max values based on where you drag them.
	var groups = {
		"Left_Leg":   {"min_node": $Marker4D,  "max_node": $Marker4D2},
		"Right_Leg":  {"min_node": $Marker4D3, "max_node": $Marker4D2},
		"Left_Arm":   {"min_node": $Marker4D4, "max_node": $Marker4D7},
		"Right_Arm":  {"min_node": $Marker4D5, "max_node": $Marker4D6},
		"Left_Torso": {"min_node": $Marker4D4, "max_node": $Marker4D2},
		"Right_Torso":{"min_node": $Marker4D5, "max_node": $Marker4D2},
		"Left_Head":  {"min_node": $Marker4D8, "max_node": $Marker4D10},
		"Right_Head": {"min_node": $Marker4D8, "max_node": $Marker4D9}
	}
	
	for part_name in groups.keys():
		var min_marker = groups[part_name]["min_node"]
		var max_marker = groups[part_name]["max_node"]
		
		# Dynamically determine min/max so it doesn't matter which node is dragged where
		var x_min = min(min_marker.position.x, max_marker.position.x)
		var x_max = max(min_marker.position.x, max_marker.position.x)
		var z_min = min(min_marker.position.z, max_marker.position.z)
		var z_max = max(min_marker.position.z, max_marker.position.z)
		
		var part_verts = PackedVector4Array()
		var part_map = {}
		
		# 1. Filter vertices
		for i in range(old_verts.size()):
			var v = old_verts[i]
			
			if v.x < x_min or v.x > x_max: continue
			if v.z < z_min or v.z > z_max: continue
			
			part_map[i] = part_verts.size()
			part_verts.append(v)
			
		# 2. Rebuild edges
		var part_edges = PackedInt32Array()
		for i in range(0, old_edges.size(), 2):
			var a = old_edges[i]
			var b = old_edges[i+1]
			
			if part_map.has(a) and part_map.has(b):
				part_edges.append(part_map[a])
				part_edges.append(part_map[b])
				
		# 3. Save resources
		if part_verts.size() > 0 and part_edges.size() > 0:
			var new_mesh = mesh_to_split.duplicate()
			new_mesh.vertices = part_verts
			new_mesh.edge_indices = part_edges
			
			var save_path = "res://" + output_prefix + part_name.to_lower() + ".tres"
			ResourceSaver.save(new_mesh, save_path)
			print("Saved: ", save_path)
		else:
			print("Skipped empty group: ", part_name)
