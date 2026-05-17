extends Node4D


# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	pass # Replace with function body.


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	pass


func _on_area_4d_body_entered_area(body: player) -> void:
	$"Text 4".visible = true


func _on_area_4d_body_exited_area(body: player) -> void:
	$"Text 4".visible = false

func _on_area_4d_2_body_entered_area(body: player) -> void:
	$"Text 6".visible = true


func _on_area_4d_2_body_exited_area(body: player) -> void:
	$"Text 6".visible = false

func _on_area_4d_3_body_entered_area(body: player) -> void:
	$"Text 9".visible = true


func _on_area_4d_3_body_exited_area(body: player) -> void:
	$"Text 9".visible = false

func _on_area_4d_4_body_entered_area(body: player) -> void:
	$"Text 10".visible = true


func _on_area_4d_4_body_exited_area(body: player) -> void:
	$"Text 10".visible = false

func _on_area_4d_5_body_entered_area(body: player) -> void:
	$"Text 11".visible = true


func _on_area_4d_5_body_exited_area(body: player) -> void:
	$"Text 11".visible = false

func _on_area_4d_6_body_entered_area(body: player) -> void:
	$"Text 14".visible = true


func _on_area_4d_6_body_exited_area(body: player) -> void:
	$"Text 14".visible = false

func _on_area_4d_7_body_entered_area(body: player) -> void:
	$"Text 15".visible = true


func _on_area_4d_7_body_exited_area(body: player) -> void:
	$"Text 15".visible = false

func _on_area_4d_8_body_entered_area(body: player) -> void:
	$"Text 5".visible = true


func _on_area_4d_8_body_exited_area(body: player) -> void:
	$"Text 5".visible = false

func _on_area_4d_9_body_entered_area(body: player) -> void:
	$"Text 7".visible = true


func _on_area_4d_9_body_exited_area(body: player) -> void:
	$"Text 7".visible = false

func _on_area_4d_10_body_entered_area(body: player) -> void:
	$"Text 8".visible = true


func _on_area_4d_10_body_exited_area(body: player) -> void:
	$"Text 8".visible = false

func _on_area_4d_11_body_entered_area(body: player) -> void:
	$"Text 12".visible = true


func _on_area_4d_11_body_exited_area(body: player) -> void:
	$"Text 12".visible = false

func _on_area_4d_12_body_entered_area(body: player) -> void:
	$"Text 13".visible = true


func _on_area_4d_12_body_exited_area(body: player) -> void:
	$"Text 13".visible = false
