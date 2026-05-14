extends RigidBody4D


class_name Physics4D

# Optimization: define the kick strength here
@export var push_friction: float = 1

var pusher: Node = null


func _on_area_4d_body_entered_area(body: player) -> void:
	var player_vel = body.velocity
	
	# 2. Convert it to a Vector4 for the 4D engine
	var target_vel = Vector4(player_vel.x, player_vel.y, player_vel.z, 0)
	
	# 3. "LERP" the velocity. 
	# This makes the object speed up gradually to match Joe, 
	# creating that "heavy push" feeling.
	self.linear_velocity = self.linear_velocity.lerp(target_vel, push_friction)

func _physics_process(delta: float) -> void:
	if pusher:
		# 1. Get Joe's current velocity
		var player_vel = pusher.velocity
		
		# 2. Convert it to a Vector4 for the 4D engine
		var target_vel = Vector4(player_vel.x, player_vel.y, player_vel.z, 0)
		
		# 3. "LERP" the velocity. 
		# This makes the object speed up gradually to match Joe, 
		# creating that "heavy push" feeling.
		self.linear_velocity = self.linear_velocity.lerp(target_vel, push_friction)
	else:
		# If no one is pushing, let it naturally slow down 
		# (Simulates 4D ground friction)
		self.linear_velocity = self.linear_velocity.lerp(Vector4.ZERO, 0.1)


func _on_area_4d_body_exited_area(body: player) -> void:
	self.linear_velocity = self.linear_velocity.lerp(Vector4.ZERO, 0.1)
