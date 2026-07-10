@tool
extends Node

@export var anim_player: AnimationPlayer

@export_group("Custom Loop Section")
@export var target_animation: String = "your_animation_name"
@export var loop_start_second: float = 1.0
@export var loop_end_second: float = 2.0
@export var enable_editor_loop: bool = true

func _process(_delta: float) -> void:
	# Safely check if the node is assigned and enabled
	if not is_instance_valid(anim_player) or not enable_editor_loop:
		return
		
	# Check if the active timeline matches our target animation
	if anim_player.current_animation == target_animation:
		var current_time = anim_player.current_animation_position
		
		# The moment the timeline head hits or passes the end second, warp it back!
		if current_time >= loop_end_second:
			# seek(..., true) forces the editor viewport to redraw instantly
			anim_player.seek(loop_start_second, true)

# This forces the editor to activate the processing frame loop for this node
func _enter_tree() -> void:
	print("hi")
	set_process(true)
