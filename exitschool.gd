extends Control


# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	Dialogic.signal_event.connect(endscene)
	Dialogic.start("start")
	


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	pass

func endscene(arg: String) -> void:
	if arg == str("endstart"):
		get_tree().change_scene_to_file("res://node_4d.tscn")
