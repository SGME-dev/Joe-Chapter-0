extends Node4D

var active_area = null

# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	var time = 0.01
	$MeshInstance4D.rotate_euler(AABB(Vector3(time ,time, time), Vector3(time ,time, time)))
	$MeshInstance4D2.rotate_euler(AABB(Vector3(time ,time, time), Vector3(time ,time, time)))
	$MeshInstance4D3.rotate_euler(AABB(Vector3(time ,time, time), Vector3(time ,time, time)))
	$MeshInstance4D4.rotate_euler(AABB(Vector3(time ,time, time), Vector3(time ,time, time)))
	
	


func _on_area_4d_body_entered_area(body: player) -> void:
	$"Text 1".visible = true
	$"Text 2".visible = true
	$"Text 3".visible = true
	$"Text 4".visible = true


func _on_area_4d_body_exited_area(body: player) -> void:
	$"Text 1".visible = false
	$"Text 2".visible = false
	$"Text 3".visible = false
	$"Text 4".visible = false

func _input(event: InputEvent) -> void:
	if event.is_action_pressed("Interact"):
		match active_area:
			"crimson":
				Dialogic.start("crimson")


func _on_area_4d_2_body_entered_area(body: player) -> void:
	active_area = "crimson"


func _on_area_4d_2_body_exited_area(body: player) -> void:
	if active_area == "crimson":
		active_area = null


func _on_area_4d_3_body_entered_area(body: player) -> void:
	get_tree().change_scene_to_file("res://exitschool.tscn")
