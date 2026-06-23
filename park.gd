extends Node4D

var bodies := []

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	bodies = [
		$MeshInstance4D, $MeshInstance4D6, $MeshInstance4D7, $MeshInstance4D8, $MeshInstance4D9, $MeshInstance4D10, $MeshInstance4D11, 
		$MeshInstance4D12, $MeshInstance4D3, $MeshInstance4D4, $MeshInstance4D5, $MeshInstance4D2
	]

# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	var rotate := 0.01
	
	var is_rotating = false
	# Check if any 4D rotation keys are held down
	if Input.is_action_pressed("wx") or Input.is_action_pressed("wy") or Input.is_action_pressed("wz") or Input.is_action_pressed("xz") or Input.is_action_pressed("xy") or Input.is_action_pressed("yz"): 
		is_rotating = true
	else:
		is_rotating = false
	
	for body in bodies:
		if is_rotating:
			body.set_process(true)  # Only do 4D math when moving
		else:
			body.set_process(false) # Freeze the projection when still
	# Update the label using the first body in the list
	if bodies.size() > 0:
		$Label.text = str(bodies[0].rotation_degrees)
	
	# Rotation Logic using .rotate_euler()
	if Input.is_action_pressed("wx"):
		apply_4d_rotation(AABB(Vector3(0, 0, 0), Vector3(rotate, 0, 0)))
		
	if Input.is_action_pressed("wy"):
		apply_4d_rotation(AABB(Vector3(0, 0, 0), Vector3(0, rotate, 0)))
		
	if Input.is_action_pressed("wz"):
		apply_4d_rotation(AABB(Vector3(0, 0, 0), Vector3(0, 0, rotate)))
		
	if Input.is_action_pressed("yz"):
		apply_4d_rotation(AABB(Vector3(rotate, 0, 0), Vector3(0, 0, 0)))
		
	if Input.is_action_pressed("xz"):
		apply_4d_rotation(AABB(Vector3(0, rotate, 0), Vector3(0, 0, 0)))
		
	if Input.is_action_pressed("xy"):
		apply_4d_rotation(AABB(Vector3(0, 0, rotate), Vector3(0, 0, 0)))
		
	
	# Your reset key
	if Input.is_action_just_pressed("x-z"):
		for body in bodies:
			body.rotation = AABB(Vector3(0, 0, 0), Vector3(0, 0, 0))

func apply_4d_rotation(rot_aabb: AABB):
	for body in bodies:
		body.rotate_euler(rot_aabb)


func _on_area_4d_body_entered_area(body: player) -> void:
	$"Text 4".visible = true


func _on_area_4d_body_exited_area(body: player) -> void:
	$"Text 4".visible = false

func _on_area_4d_2_body_entered_area(body: player) -> void:
	$"Text 6".visible = true


func _on_area_4d_2_body_exited_area(body: player) -> void:
	$"Text 6".visible = false

func _on_area_4d_3_body_entered_area(body: player) -> void:
	$"Text 9".visible = true


func _on_area_4d_3_body_exited_area(body: player) -> void:
	$"Text 9".visible = false

func _on_area_4d_4_body_entered_area(body: player) -> void:
	$"Text 10".visible = true


func _on_area_4d_4_body_exited_area(body: player) -> void:
	$"Text 10".visible = false

func _on_area_4d_5_body_entered_area(body: player) -> void:
	$"Text 11".visible = true


func _on_area_4d_5_body_exited_area(body: player) -> void:
	$"Text 11".visible = false

func _on_area_4d_6_body_entered_area(body: player) -> void:
	$"Text 14".visible = true


func _on_area_4d_6_body_exited_area(body: player) -> void:
	$"Text 14".visible = false

func _on_area_4d_7_body_entered_area(body: player) -> void:
	$"Text 15".visible = true


func _on_area_4d_7_body_exited_area(body: player) -> void:
	$"Text 15".visible = false

func _on_area_4d_8_body_entered_area(body: player) -> void:
	$"Text 5".visible = true


func _on_area_4d_8_body_exited_area(body: player) -> void:
	$"Text 5".visible = false

func _on_area_4d_9_body_entered_area(body: player) -> void:
	$"Text 7".visible = true


func _on_area_4d_9_body_exited_area(body: player) -> void:
	$"Text 7".visible = false

func _on_area_4d_10_body_entered_area(body: player) -> void:
	$"Text 8".visible = true


func _on_area_4d_10_body_exited_area(body: player) -> void:
	$"Text 8".visible = false

func _on_area_4d_11_body_entered_area(body: player) -> void:
	$"Text 12".visible = true


func _on_area_4d_11_body_exited_area(body: player) -> void:
	$"Text 12".visible = false

func _on_area_4d_12_body_entered_area(body: player) -> void:
	$"Text 13".visible = true


func _on_area_4d_12_body_exited_area(body: player) -> void:
	$"Text 13".visible = false


func _on_area_4de_body_entered_area(body: player) -> void:
	$Path.visible = true


func _on_area_4de_body_exited_area(body: player) -> void:
	$Path.visible = false


func _on_area_4de_2_body_entered_area(body: player) -> void:
	
	$"Text 16".visible = true


func _on_area_4de_2_body_exited_area(body: player) -> void:
	
	$"Text 16".visible = false


func _on_warn_body_entered_area(body: player) -> void:
	$"Text 17".visible = true


func _on_warn_body_exited_area(body: player) -> void:
	$"Text 17".visible = false
