extends Node4D

var active_area = null

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	pass # Replace with function body.


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	if $tap.playing == true:
		$kitchentools/water.visible = true
	else:
		$kitchentools/water.visible = false
	if $flush.playing == true:
		$toilet/water.visible = true
		$toilet/water2.visible = true
	else:
		$toilet/water.visible = false
		$toilet/water2.visible = false

func _on_area_4d_body_entered_area(area: player) -> void:
	active_area = "tap"

func _on_area_4d_body_exited_area(area: player) -> void:
	if active_area == "tap":
		active_area = null

func _on_area_4d_2_body_entered_area(area: player) -> void:
	active_area = "stove"

func _on_area_4d_2_body_exited_area(area: player) -> void:
	if active_area == "stove":
		active_area = null

func _on_area_4d_3_body_entered_area(area: player) -> void:
	active_area = "washmachine"

func _on_area_4d_3_body_exited_area(area: player) -> void:
	if active_area == "washmachine":
		active_area = null


func _input(event: InputEvent) -> void:
	if event.is_action_pressed("Interact"):
		match active_area:
			"tap":
				$tap.play()
			"stove":
				$stove.play()
			"washmachine":
				$washmachine.play()
			"flush":
				$flush.play()


func _on_area_4d_4_body_entered_area(body: player) -> void:
	active_area = "flush"

func _on_area_4d_4_body_exited_area(body: player) -> void:
	if active_area == "flush":
		active_area = null
