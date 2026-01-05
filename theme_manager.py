import json
import os

class ThemeManager:
    DARK = """
        QWidget { background-color: #1E1E1E; color: #DCDCDC; }
        QPlainTextEdit { background-color: #000000; font-family: 'Consolas'; }
        QPushButton { background-color: #333; border: 1px solid #555; padding: 5px; }
    """
    LIGHT = """
        QWidget { background-color: #F0F0F0; color: #000000; }
        QPlainTextEdit { background-color: #FFFFFF; font-family: 'Consolas'; }
        QPushButton { background-color: #DDD; border: 1px solid #AAA; padding: 5px; }
    """

    def __init__(self, settings_path="storage/settings.json"):
        self.path = settings_path

    def get_theme(self):
        try:
            with open(self.path, 'r') as f:
                return json.load(f).get("theme", "dark")
        except:
            return "dark"

    def save_theme(self, theme_name):
        with open(self.path, 'w') as f:
            json.dump({"theme": theme_name}, f)

    def apply(self, app, theme_name):
        style = self.DARK if theme_name == "dark" else self.LIGHT
        app.setStyleSheet(style)