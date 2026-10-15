extends Node4D

var boss_state := "Start"
@onready var animation_player: AnimationPlayer = $AnimationPlayer


# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	pass # Replace with function body.


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	
	match boss_state:
			"Gun":
				$gun.visible = true
				# 1. Calculate 4D direction to player
				var current_pos: Vector4 = global_position
				var target_pos: Vector4 = $"../CharacterBody4D2".global_position
				var dir_to_player: Vector4 = (target_pos - current_pos)
				var turn_speed := 1.4
				
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
			"laser":
				$laser.visible = true
			"particles":
				$particles.visible = true
	if animation_player.is_playing() and animation_player.current_animation == "Gun":
		boss_state = "Gun"
	if animation_player.is_playing() and animation_player.current_animation == "laser":
		boss_state = "laser"
	if animation_player.is_playing() and animation_player.current_animation == "particles":
		boss_state = "particles"


func _on_area_4d_body_entered_area(body: player) -> void:
	body.health -= 10
	print("ouch", body.health)


func _on_area_4d_2_body_entered_area(body: PhysicsBody4D) -> void:
	body.health -= 10
	print("ouch", body.health)
