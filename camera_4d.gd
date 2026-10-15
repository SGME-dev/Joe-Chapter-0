extends Camera4D

var time := 0.01
var sens := 0.0025
var cam_yaw: float = 0.0
var cam_pitch: float = 0.0
@export var use_ground_view: = true
@onready var pivot: Camera4D = $"."

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	pass # Replace with function body.


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	if Input.is_action_pressed("ui_right"):
		$".".global_position.x += time
	if Input.is_action_pressed("ui_left"):
		$".".global_position.x -= time
	if Input.is_action_pressed("ui_up"):
		$".".global_position.z += time
	if Input.is_action_pressed("ui_down"):
		$".".global_position.z -= time
	if Input.is_action_pressed("move_ana"):
		$".".global_position.w += time
	if Input.is_action_pressed("move_kata"):
		$".".global_position.w -= time
	if Input.is_action_pressed("ui_accept"):
		$".".global_position.y += time
	if Input.is_action_pressed("crouch"):
		$".".global_position.y -= time

func _input(event: InputEvent) -> void:
	
	
	
	if event.is_action_pressed("show_mouse"):
		if Input.get_mouse_mode() == Input.MOUSE_MODE_CAPTURED:
			Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)
		else:
			Input.set_mouse_mode(Input.MOUSE_MODE_CAPTURED)
	
	
	
	
	
	var is_valid_motion = event is InputEventMouseMotion and Input.get_mouse_mode() == Input.MOUSE_MODE_CAPTURED
	var is_valid_drag = event is InputEventScreenDrag and event.index == 0
	
	if is_valid_motion or is_valid_drag:
		_rotate_cam_yaw(-event.relative.x * sens)
		_apply_camera_pitch(-event.relative.y * sens)



func _rotate_cam_yaw(amount: float) -> void:
	cam_yaw += amount
	_update_camera_basis()

func _apply_camera_pitch(delta_pitch: float) -> void:
	cam_pitch = clamp(cam_pitch + delta_pitch, deg_to_rad(-30), deg_to_rad(60))
	_update_camera_basis()




func _update_camera_basis() -> void:
	
	pivot.basis.x = Vector4(1, 0, 0, 0)
	pivot.basis.y = Vector4(0, 1, 0, 0)
	pivot.basis.z = Vector4(0, 0, 1, 0)
	pivot.basis.w = Vector4(0, 0, 0, 1)
	
	
	var cy = cos(cam_yaw)
	var sy = sin(cam_yaw)
	
	# 3. Apply Yaw to Pivot (Camera)
	pivot.basis.x = Vector4(cy, 0, sy, 0)
	pivot.basis.z = Vector4(-sy, 0, cy, 0)
	
	
	
	
	
	
	

func _set_camera_basis_from_angle() -> void :
	if use_ground_view:
		pivot.rotation = AABB(Vector3.ZERO, Vector3(0, PI * -0.5, 0))
		pivot.scale = Vector4(1, 1, 1, 1)
	else:
		pivot.rotation = AABB(Vector3.ZERO, Vector3.ZERO)
		pivot.scale = Vector4(2.494, 1, 2.494, 1)
