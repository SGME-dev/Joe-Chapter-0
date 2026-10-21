extends Node4D

var boss_state := "Start"
@onready var animation_player: AnimationPlayer = $AnimationPlayer
@onready var character_body_4d_2: player = $"../CharacterBody4D2"
@onready var bullet: Node4D = $gun/bullet
var has_hit: bool = false
var nuke_pos_choosen: bool = false
var black_hole_pos_choosen: bool = false
var teleported: bool = false
@onready var lasers := get_tree().get_nodes_in_group("enemy_lasers") 
@onready var particles := get_tree().get_nodes_in_group("particle") 
@onready var nukes := get_tree().get_nodes_in_group("nuke") 
@onready var bound_one: Node4D = $teleport_range/teleport_range2
@onready var bound_two: Node4D = $teleport_range/teleport_range3
var nuke_1_pos: Vector4
var nuke_2_pos: Vector4
var nuke_3_pos: Vector4
var nuke_4_pos: Vector4
var nuke_5_pos: Vector4
@onready var black_hole: Node4D = $black_hole


# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	pass


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	
	
	
	if Input.is_action_just_pressed("test_boss_state"):
		animation_player.play("Teleport")
	match boss_state:
			"Gun":
				$gun.visible = true
				# 1. Calculate 4D direction to player
				var current_pos: Vector4 = global_position
				var target_pos: Vector4 = character_body_4d_2.global_position
				var dir_to_player: Vector4 = (target_pos - current_pos)
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
			"laser":
				$laser.visible = true
			"particles":
				$particles.visible = true
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
			"nuke":
				$nuke.visible = true
				if !nuke_pos_choosen:
					nuke_pos_choosen = true
					
					randomize_nukes()
					$nuke/pos.global_position = nuke_1_pos
					$nuke/pos2.global_position = nuke_2_pos
					$nuke/pos3.global_position = nuke_3_pos
					$nuke/pos4.global_position = nuke_4_pos
					$nuke/pos5.global_position = nuke_5_pos
					
					
					await get_tree().create_timer(1.0).timeout
					nuke_pos_choosen = false
			"black_hole":
				$black_hole.visible = true
				if !black_hole_pos_choosen:
					black_hole_pos_choosen = true
					teleport_to_random_marker_range()
				var pull_speed: float = 4.0
				var current_pos: Vector4 = character_body_4d_2.global_position
				var target_pos: Vector4 = black_hole.global_position
				
				var dir_to_target: Vector4 = (target_pos - current_pos)
				var distance = dir_to_target.length()
				
				# Only pull if it's not already right on top of the target (prevents jitter)
				if distance > 0.1:
					dir_to_target = dir_to_target.normalized()
					character_body_4d_2.global_position += dir_to_target * pull_speed * delta
			"melee":
				$melee.visible = true
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
			"Teleport":
				$teleport.visible = true
				if !teleported:
					teleported = true
					var teleport_position := get_random_vector4_for_teleport()
					global_position = teleport_position
					await get_tree().create_timer(1.0).timeout
					teleported = false
	if animation_player.is_playing() and animation_player.current_animation == "Gun":
		boss_state = "Gun"
	if animation_player.is_playing() and animation_player.current_animation == "laser":
		boss_state = "laser"
	if animation_player.is_playing() and animation_player.current_animation == "particles":
		boss_state = "particles"
	if animation_player.is_playing() and animation_player.current_animation == "nuke":
		boss_state = "nuke"
	if animation_player.is_playing() and animation_player.current_animation == "black_hole":
		boss_state = "black_hole"
	if animation_player.is_playing() and animation_player.current_animation == "melee":
		boss_state = "melee"
	if animation_player.is_playing() and animation_player.current_animation == "Teleport":
		boss_state = "Teleport"
		
	if has_hit:
		return
	if $gun.visible:
		if character_body_4d_2 and bullet.global_position.distance_to(character_body_4d_2.global_position) < 1.5:
			if "health" in character_body_4d_2:
				character_body_4d_2.health -= 10
				print("ouch", character_body_4d_2.health)
				has_hit = true
				await get_tree().create_timer(1).timeout
				has_hit = false
	if $laser.visible:
		for laser in lasers:
			
			
			var laser_pos = laser.global_position
			var player_pos = character_body_4d_2.global_position
			
			# Calculate absolute distance on each axis individually
			var diff_x = abs(laser_pos.x - player_pos.x)
			var diff_y = abs(laser_pos.y - player_pos.y)
			var diff_z = abs(laser_pos.z - player_pos.z)
			var diff_w = abs(laser_pos.w - player_pos.w)
			
			# Check your custom 4D dimensions constraints
			if diff_x < 1.5 and diff_z < 1.5 and diff_y < 6.0 and diff_w < 12.0:
				if "health" in character_body_4d_2:
					character_body_4d_2.health -= 10
					print("ouch", character_body_4d_2.health)
					
					has_hit = true
					await get_tree().create_timer(1.0).timeout # Using your 1-second timeout here
					has_hit = false
					
	if $particles.visible:
		for particle in particles:
			
			
			var laser_pos = particle.global_position
			var player_pos = character_body_4d_2.global_position
			
			# Calculate absolute distance on each axis individually
			var diff_x = abs(laser_pos.x - player_pos.x)
			var diff_y = abs(laser_pos.y - player_pos.y)
			var diff_z = abs(laser_pos.z - player_pos.z)
			var diff_w = abs(laser_pos.w - player_pos.w)
			
			# Check your custom 4D dimensions constraints
			if diff_x < 1.5 and diff_z < 1.5 and diff_y < 1.5 and diff_w < 1.5:
				if "health" in character_body_4d_2:
					character_body_4d_2.health -= 1
					print("ouch", character_body_4d_2.health)
					
					has_hit = true
					await get_tree().create_timer(0.2).timeout # Using your 1-second timeout here
					has_hit = false
	if $nuke.visible:
		for nuke in nukes:
			
			
			var nuke_pos = nuke.global_position
			var player_pos = character_body_4d_2.global_position
			
			# Calculate absolute distance on each axis individually
			var diff_x = abs(nuke_pos.x - player_pos.x)
			var diff_y = abs(nuke_pos.y - player_pos.y)
			var diff_z = abs(nuke_pos.z - player_pos.z)
			var diff_w = abs(nuke_pos.w - player_pos.w)
			
			# Check your custom 4D dimensions constraints
			if diff_x < 2 and diff_z < 2 and diff_y < 2 and diff_w < 2:
				if "health" in character_body_4d_2:
					character_body_4d_2.health -= 20
					print("nuclear_ouch", character_body_4d_2.health)
					
					has_hit = true
					await get_tree().create_timer(1.0).timeout # Using your 1-second timeout here
					has_hit = false
	if $black_hole.visible:
		if character_body_4d_2 and black_hole.global_position.distance_to(character_body_4d_2.global_position) < 2:
			if "health" in character_body_4d_2:
				character_body_4d_2.health -= 85
				print("time_bending-ouch", character_body_4d_2.health)
				has_hit = true
				await get_tree().create_timer(2.5).timeout
				has_hit = false
	if $melee.visible:
		if character_body_4d_2 and global_position.distance_to(character_body_4d_2.global_position) < 2.5:
			if "health" in character_body_4d_2:
				character_body_4d_2.health -= 25
				print("slashing-ouch", character_body_4d_2.health)
				has_hit = true
				await get_tree().create_timer(1).timeout
				has_hit = false
	if $teleport.visible:
		if character_body_4d_2 and global_position.distance_to(character_body_4d_2.global_position) < 2:
			if "health" in character_body_4d_2:
				character_body_4d_2.health -= 25
				print("surprising-ouch", character_body_4d_2.health)
				has_hit = true
				await get_tree().create_timer(1).timeout
				has_hit = false


func get_random_vector4() -> Vector4:
	var pos_a = bound_one.global_position
	var pos_b = bound_two.global_position
	var player_pos = character_body_4d_2.global_position
	
	# Generate a random position within 6 units of the player on all axes
	var target_pos = Vector4(
		randf_range(player_pos.x - 6.0, player_pos.x + 6.0),
		randf_range(player_pos.y - 6.0, player_pos.y + 6.0),
		randf_range(player_pos.z - 6.0, player_pos.z + 6.0),
		randf_range(player_pos.w - 6.0, player_pos.w + 6.0)
	)
	
	# Clamp the position so it never goes outside your Marker arena bounds
	target_pos.x = clamp(target_pos.x, min(pos_a.x, pos_b.x), max(pos_a.x, pos_b.x))
	target_pos.y = clamp(target_pos.y, min(pos_a.y, pos_b.y), max(pos_a.y, pos_b.y))
	target_pos.z = clamp(target_pos.z, min(pos_a.z, pos_b.z), max(pos_a.z, pos_b.z))
	target_pos.w = clamp(target_pos.w, min(pos_a.w, pos_b.w), max(pos_a.w, pos_b.w))
	
	return target_pos

func get_random_vector4_for_teleport() -> Vector4:
	var pos_a = bound_one.global_position
	var pos_b = bound_two.global_position
	var player_pos = character_body_4d_2.global_position
	
	# Generate a random position within 6 units of the player on all axes
	var target_pos = Vector4(
		randf_range(player_pos.x - 3, player_pos.x + 3),
		randf_range(player_pos.y - 3, player_pos.y + 3),
		randf_range(player_pos.z - 3, player_pos.z + 3),
		randf_range(player_pos.w - 3, player_pos.w + 3)
	)
	
	# Clamp the position so it never goes outside your Marker arena bounds
	target_pos.x = clamp(target_pos.x, min(pos_a.x, pos_b.x), max(pos_a.x, pos_b.x))
	target_pos.y = clamp(target_pos.y, min(pos_a.y, pos_b.y), max(pos_a.y, pos_b.y))
	target_pos.z = clamp(target_pos.z, min(pos_a.z, pos_b.z), max(pos_a.z, pos_b.z))
	target_pos.w = clamp(target_pos.w, min(pos_a.w, pos_b.w), max(pos_a.w, pos_b.w))
	
	return target_pos

func randomize_nukes() -> void:
	nuke_1_pos = get_random_vector4()
	nuke_2_pos = get_random_vector4()
	nuke_3_pos = get_random_vector4()
	nuke_4_pos = get_random_vector4()
	nuke_5_pos = get_random_vector4()

func teleport_to_random_marker_range() -> void:
	var pos_a = bound_one.global_position
	var pos_b = bound_two.global_position
	
	# Pick a random 4D position strictly between the two nodes
	black_hole.global_position = Vector4(
		randf_range(min(pos_a.x, pos_b.x), max(pos_a.x, pos_b.x)),
		randf_range(min(pos_a.y, pos_b.y), max(pos_a.y, pos_b.y)),
		randf_range(min(pos_a.z, pos_b.z), max(pos_a.z, pos_b.z)),
		randf_range(min(pos_a.w, pos_b.w), max(pos_a.w, pos_b.w))
	)
