extends Node4D

@export var text_to_display: String = "A TESSERACT IS THE FOUR DIMENSIONAL ANALOGUE:OF A CUBE EXTENDING INTO SPACE AT A RIGHT:ANGLE TO OUR KNOWN THREE:WHILE A 3D CUBE IS BOUNDED BY SIX SQUARE:FACES A TESSERACT IS BOUNDED BY EIGHT:CUBIC CELLS:IT CONSISTS OF 16 VERTICES AND 32 EDGES:WHERE EVERY SINGLE CORNER MEETS FOUR:EDGES AT PERFECT RIGHT ANGLES:IF IT PASSED THROUGH OUR 3D WORLD WE:WOULD SEE A CUBE APPEAR CHANGE SHAPE:INTERNALLY AND THEN VANISH:IT IS MOST COMMONLY VISUALIZED AS A CUBE:WITHIN A CUBE THOUGH THAT IS JUST A 3D:SHADOW OF ITS TRUE FORM"
@export var char_spacing: float = 0.35
@export var line_spacing: float = 0.45



func _ready():
	generate_4d_text()


func generate_4d_text():
	# Convert to upper to match file names (A.tscn, B.tscn)
	var characters = text_to_display.to_upper().split("")
	
	var cursor_x := 0.0
	var cursor_y := 0.0

	for char in characters:
		# 1. Handle New Line (:)
		if char == ":":
			cursor_y -= 1.0 # Move down on the Y axis
			cursor_x = 0.0  # Reset horizontal position to the start
			continue
		
		# 2. Handle Space
		if char == " ":
			cursor_x += 1.0
			continue
			
		# 3. Handle Letters
		var scene_path = "res://" + char + ".tscn"
		
		if FileAccess.file_exists(scene_path):
			var letter_scene = load(scene_path)
			var instance = letter_scene.instantiate()
			
			add_child(instance)
			
			# Set the Vector4 position: (X, Y, Z, W)
			# We use cursor_x * char_spacing and cursor_y * line_spacing
			instance.position = Vector4(
				0, 
				cursor_y * line_spacing, 
				-float(cursor_x * char_spacing), 
				0
			)
			
			# Move the cursor forward for the next letter
			cursor_x += 1.0
		else:
			push_warning("Character scene not found: " + scene_path)
