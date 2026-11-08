extends Area4D

class_name player_area

var body_killable: Array = []

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	pass # Replace with function body.


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	if Input.is_action_just_pressed("hit"):
		for body in body_killable:
			if "health" in body:
				body.health -= 1
				print("Hit!!!")


func _on_body_entered_area(body: PhysicsBody4D) -> void:
	body_killable.append(body)
	print("Entered")


func _on_body_exited_area(body: PhysicsBody4D) -> void:
	body_killable.clear()
