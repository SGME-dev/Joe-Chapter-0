extends Node4D

@onready var final_wall: StaticBody4D = $StaticBody4D47


var passf := false
var pass2 := false
# We store all the rotatable bodies in a single list
var bodies = []
var hide = []

func _ready() -> void:
	# This list includes your original nodes + the new ones from 17 to 33
	bodies = [
		$StaticBody4D18, $StaticBody4D19, $StaticBody4D20, $StaticBody4D21, $StaticBody4D22,
		$Sphereinder, $Sphereinder2, $CubinderMoving, $StaticBody4D41, $StaticBody4D42, $StaticBody4D43, $StaticBody4D44
	]
	


func _process(delta: float) -> void:
	if passf == true or pass2 == true:
		if $StaticBody4D47 == null:
			return
		else:
			final_wall.queue_free()
	var rotate := 0.1
	
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
	if Input.is_action_just_pressed("wx"):
		apply_4d_rotation(AABB(Vector3(0, 0, 0), Vector3(rotate, 0, 0)))
		
	if Input.is_action_just_pressed("wy"):
		apply_4d_rotation(AABB(Vector3(0, 0, 0), Vector3(0, rotate, 0)))
		
	if Input.is_action_just_pressed("wz"):
		apply_4d_rotation(AABB(Vector3(0, 0, 0), Vector3(0, 0, rotate)))
		
	if Input.is_action_just_pressed("yz"):
		apply_4d_rotation(AABB(Vector3(rotate, 0, 0), Vector3(0, 0, 0)))
		
	if Input.is_action_just_pressed("xz"):
		apply_4d_rotation(AABB(Vector3(0, rotate, 0), Vector3(0, 0, 0)))
		
	if Input.is_action_just_pressed("xy"):
		apply_4d_rotation(AABB(Vector3(0, 0, rotate), Vector3(0, 0, 0)))
		
	
	# Your reset key
	if Input.is_action_just_pressed("x-z"):
		for body in bodies:
			body.rotation = AABB(Vector3(0, 0, 0), Vector3(0, 0, 0))
		$CubinderMoving.position = Vector4(-96.958, 5.543, -258.36, 0.0)

# A helper function so we don't have to repeat the 'for' loop everywhere
func apply_4d_rotation(rot_aabb: AABB):
	for body in bodies:
		body.rotate_euler(rot_aabb)


func _on_area_4d_body_entered_area(body: player) -> void:
	$Sphereinder.visible = true


func _on_area_4d_2_body_entered_area(body: player) -> void:
	$Sphereinder.visible = false


func _on_area_4d_3_body_entered_area(body: Physics4D) -> void:
	passf = true


func _on_area_4d_3_body_exited_area(body: Physics4D) -> void:
	passf = false


func _on_area_4d_4_body_entered_area(body: Physics4D) -> void:
	pass2 = true


func _on_area_4d_4_body_exited_area(body: Physics4D) -> void:
	pass2 = false
