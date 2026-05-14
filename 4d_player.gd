extends CharacterBody4D

class_name player

const SPEED = 7.25
const JUMP_VELOCITY = 10
@export var vision_distance: float = 20.0
@export var max_health: int = 100
var health: int = 100
var sens: float = 0.0025

# Manual velocity declaration
var velocity: Vector4 = Vector4.ZERO

var cam_yaw: float = 0.0
var cam_pitch: float = 0.0
var tar: bool = true

@onready var pivot: Node4D = $Camera_Controller
# Ensure this matches your scene tree exactly
@onready var cam: Node4D = $Camera_Controller/Camera_Target
@onready var mesh: MeshInstance4D = $MeshInstance4D 
var direction: Vector4

static var gravity: float = ProjectSettings.get_setting("physics/3d/default_gravity") as float




func _physics_process(delta: float) -> void:
	if not tar:
		return
	
	
	
	# 1. Manual Ground Check (More reliable for 4D)
	
	var is_actually_on_floor = is_on_floor()
	
	
	if is_actually_on_floor:
		if velocity.y < 0:
			velocity.y = -0.1 
	else:
		velocity.y -= gravity * delta
	
	# 2. Jump Input
	if Input.is_action_just_pressed("ui_accept"):
		
		if is_actually_on_floor or abs(velocity.y) < 0.2:
			velocity.y = JUMP_VELOCITY
			
			position.y += 0.05 
			
	
	#3. Camera Switching
	if Input.is_action_just_pressed("First_Person"):
		if $Camera_Controller/Camera_Target/Camera4D.current == true:
			$Camera_Controller/Camera_Target/Camera4D.current = false
			$Camera_Controller/Camera_Target/Camera4D2.current = true
			return
		if $Camera_Controller/Camera_Target/Camera4D2.current == true:
			$Camera_Controller/Camera_Target/Camera4D2.current = false
			$Camera_Controller/Camera_Target/Camera4D.current = true
			return
	
	# 4. Movement Logic
	var input_dir: Vector2 = Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
	var input_w: float = Input.get_axis("move_kata", "move_ana")
	
	var move_vec = Vector3(input_dir.x, 0, input_dir.y).rotated(Vector3.UP, -cam_yaw)
	direction = Vector4(move_vec.x, 0.0, move_vec.z, input_w)
	
	if direction.length() > 0.001:
		direction = direction.normalized()
		velocity.x = direction.x * SPEED
		velocity.z = direction.z * SPEED
		velocity.w = direction.w * SPEED
	else:
		velocity.x = move_toward(velocity.x, 0, SPEED * delta * 10)
		velocity.z = move_toward(velocity.z, 0, SPEED * delta * 10)
		velocity.w = move_toward(velocity.w, 0, SPEED * delta * 10)
	
	# 5. EXECUTE MOVEMENT
	var motion = velocity * delta
	var collision = move_and_collide(motion)
	
	if collision == null:
		position += motion
	else:
		var travel = collision.get_travel() if collision.has_method("get_travel") else Vector4.ZERO
		var normal = collision.get_normal()
		
		
		position += travel
		
		
		
		var dot = velocity.x * normal.x + velocity.y * normal.y + velocity.z * normal.z + velocity.w * normal.w
		
		
		if dot < 0:
			velocity = velocity - (normal * dot)
			
			
			position += (normal * 0.001)
	
	

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
	
	
	mesh.basis = pivot.basis


func _on_area_4d_body_exited_area(body: PhysicsBody4D) -> void:
	pass # Replace with function body.
