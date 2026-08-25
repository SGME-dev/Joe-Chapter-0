extends Node4D

var playing := true
var active_area = null
# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	Dialogic.signal_event.connect(deletepapers)


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	if $teststart/Area4D5/MeshInstance4D2 == null:
		$Label.text = str("Time left until level ends: ", time_left_to_live())
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
	

func _on_area_4d_5_body_entered_area(body: player) -> void:
	active_area = "test"

func _on_area_4d_5_body_exited_area(body: player) -> void:
	if active_area == "test":
		active_area = null

func _input(event: InputEvent) -> void:
	if event.is_action_pressed("Interact"):
		match active_area:
			"test":
				Dialogic.start("joetest")

func deletepapers(arg: String) -> void:
	if arg == str("delete test"):
		get_tree().queue_delete($teststart/Area4D5/MeshInstance4D2)
		label.show()
		$Timer.start()

@onready var timer: Timer = $Timer
@onready var label: Label = $Label

func time_left_to_live() -> String:
	var time_left := timer.time_left
	var minute := int(time_left / 60)
	var second := int(time_left) % 60
	return "%02d:%02d" % [minute, second]
