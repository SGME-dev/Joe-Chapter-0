extends Node4D

var playing := true

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	pass


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	if playing:
		$CharacterBody4D/Camera_Controller/Camera_Target/Camera4D.current = true
		$CharacterBody4D/human.visible = false
		$CharacterBody4D/MeshInstance4D.visible = false
		Dialogic.start("welcomehome")
		playing = false
	if Dialogic.VAR.amniationhug:
		$body1/AnimationPlayer.play("hug")
	else:
		$body1/AnimationPlayer.pause()
	if Dialogic.VAR.animationcross:
		$body2/AnimationPlayer.play("crossarm")
		$body1/AnimationPlayer.play("default")
	else:
		$body2/AnimationPlayer.pause()

func _on_area_4d_body_entered_area(body: player) -> void:
	$Park/Path.visible = true


func _on_area_4d_body_exited_area(body: player) -> void:
	$Park/Path.visible = false


func _on_animation_player_animation_finished(anim_name: StringName) -> void:
	Dialogic.VAR.amniationhug = false
	$body1/AnimationPlayer.pause()


func _on_animation_player2_animation_finished(anim_name: StringName) -> void:
	$body2/AnimationPlayer.pause()
	Dialogic.VAR.animationcross = false
	
