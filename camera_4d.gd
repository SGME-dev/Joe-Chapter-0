extends Camera4D

var time := 1

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	pass # Replace with function body.


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	if Input.is_action_pressed("ui_right"):
		$".".global_position.x += time
	if Input.is_action_pressed("ui_left"):
		$".".global_position.x -= time
