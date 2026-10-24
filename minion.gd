extends CharacterBody4D

class_name minion

@onready var character_body_4d_2: player = $"../../CharacterBody4D2"
var has_hit := false
var velocity: Vector4 = Vector4.ZERO
static var gravity: float = ProjectSettings.get_setting("physics/3d/default_gravity") as float
var health := 3

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	pass # Replace with function body.


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	if !visible:
		return
	var is_actually_on_floor = is_on_floor()
	if is_actually_on_floor:
		if velocity.y < 0:
			velocity.y = -0.1
			
	else:
		velocity.y -= gravity * delta
	
	var speed: float = 3.0
	var current_pos: Vector4 = global_position
	var target_pos: Vector4 = character_body_4d_2.global_position
	var dir_to_player: Vector4 = (target_pos - current_pos)
	
	# Lock the Y axis so the boss stays at its current height
	dir_to_player.y = 0.0
	
	if dir_to_player.length_squared() > 0.0001:
		var distance = dir_to_player.length()
		dir_to_player = dir_to_player.normalized()
		
		# Only move if it's outside the stopping distance
		if distance > 2.0:
			global_position += dir_to_player * speed * delta
	var turn_speed := 1
	
	if dir_to_player.length_squared() < 0.0001:
		return
		
	dir_to_player = dir_to_player.normalized()
	var target_forward: Vector4 = -dir_to_player # Assuming -Z is local forward
	
	# 2. Extract current forward vector from the basis (-Z axis)
	var current_forward: Vector4 = -basis.z
	
	# 3. Manually step toward the target forward using a clamped distance (no lerp, no move_toward)
	var diff: Vector4 = target_forward - current_forward
	var max_step: float = turn_speed * delta
	
	if diff.length() <= max_step:
		current_forward = target_forward
	else:
		current_forward = (current_forward + diff.normalized() * max_step).normalized()
		
	var forward_z: Vector4 = -current_forward
	
	# 4. Rebuild the orthogonal 4D basis axes around the updated forward vector
	var up_y: Vector4 = Vector4(0, 1, 0, 0)
	if abs(up_y.dot(forward_z)) > 0.99:
		up_y = Vector4(1, 0, 0, 0)
	
	up_y = (up_y - forward_z * up_y.dot(forward_z)).normalized()
	
	var right_x: Vector4 = Vector4(up_y.y * forward_z.z - up_y.z * forward_z.y, 0, 0, 0)
	if right_x.length_squared() < 0.0001:
		right_x = Vector4(1, 0, 0, 0)
	right_x = (right_x - forward_z * right_x.dot(forward_z) - up_y * right_x.dot(up_y)).normalized()
	
	var ana_w: Vector4 = Vector4(0, 0, 0, 1)
	ana_w = (ana_w - forward_z * forward_z.dot(ana_w) - up_y * up_y.dot(ana_w) - right_x * right_x.dot(ana_w)).normalized()
	
	# 5. Apply the projection basis to rotate the enemy smoothly
	basis = Projection(right_x, up_y, forward_z, ana_w)
	scale = Vector4(0.25, 0.125, 0.25, 0.25)
	
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
	if has_hit:
		return
	if character_body_4d_2 and global_position.distance_to(character_body_4d_2.global_position) < 2.5:
			if "health" in character_body_4d_2:
				character_body_4d_2.health -= 0.1
				print("tiny-ouch", character_body_4d_2.health)
				has_hit = true
				await get_tree().create_timer(0.1).timeout
				has_hit = false
