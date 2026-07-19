extends Control

@onready var label: Label = $Label
@export var dialougue := 1
# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	pass


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	
	if dialougue == 1:
		label.text = str("Bye! Remember to do your homework!")
	if dialougue == 2:
		#Waving bye
		label.text = str("Bye!")
	if dialougue == 3:
		#Waving bye
		label.text = str("Bye!")
	if dialougue == 4:
		label.text = str("Looks like the path to home has been destroyed by asteroids... It will be tough, but I will have to get home by jumping on these platforms.")
	if dialougue == 5:
		label.text = str("I can do it.")
	if dialougue == 6:
		#Wiping sweat off head
		label.text = str("Phew, I made it home.")
	if dialougue == 7:
		label.text = str("Hello sweetie, I made your favorite... Chicken curry!")
	if dialougue == 8:
		#Hugs
		label.text = str("Now remember darling, do not forget homework this time.")
	if dialougue == 9:
		#If homework succeded
		label.text = str("Well done, you really are smart! Now lets go eat dinner")
	if dialougue == 10:
		#If homework does not succeed
		label.text = str("Its okay. You might have been stressed after being at school for a unusual amount of time.")
