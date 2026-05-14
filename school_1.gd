extends Node4D



# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	var time = 0.01
	$MeshInstance4D.rotate_euler(AABB(Vector3(time ,time, time), Vector3(time ,time, time)))
	$MeshInstance4D2.rotate_euler(AABB(Vector3(time ,time, time), Vector3(time ,time, time)))
	$MeshInstance4D3.rotate_euler(AABB(Vector3(time ,time, time), Vector3(time ,time, time)))
	$MeshInstance4D4.rotate_euler(AABB(Vector3(time ,time, time), Vector3(time ,time, time)))
	
	
