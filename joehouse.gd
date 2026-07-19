extends Node4D


# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	Dialogic.start("welcomehome")


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	pass


func _on_area_4d_body_entered_area(body: player) -> void:
	$Park/Path.visible = true


func _on_area_4d_body_exited_area(body: player) -> void:
	$Park/Path.visible = false
