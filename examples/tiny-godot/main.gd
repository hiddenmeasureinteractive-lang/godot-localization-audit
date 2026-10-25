extends Node
## A deliberately tiny, synthetic migration example.

var message_label: Label


func _ready() -> void:
	var translated_demo := "--translated" in OS.get_cmdline_user_args()
	if translated_demo:
		var french := Translation.new()
		french.locale = "fr"
		french.add_message("Welcome aboard", "Bienvenue à bord")
		TranslationServer.add_translation(french)
		TranslationServer.set_locale("fr")
	message_label = Label.new()
	message_label.position = Vector2(32, 32)
	add_child(message_label)
	show_message("Welcome aboard")
	var button := Button.new()
	button.position = Vector2(32, 80)
	button.text = "Continue" # Godot already extracts this built-in property.
	add_child(button)
	if "--smoke" in OS.get_cmdline_user_args():
		var expected := "Bienvenue à bord" if translated_demo else "Welcome aboard"
		assert(message_label.text == expected)
		assert(button.text == "Continue")
		print("LOCALIZATION_DEMO_OK")
		get_tree().quit(0)


func show_message(message: String) -> void:
	message_label.text = message
