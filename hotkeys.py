import keyboard
from PySide6.QtCore import QObject, Signal

class HotkeyManager(QObject):
    hotkey_pressed = Signal()

    def __init__(self):
        super().__init__()
        # Используем library 'keyboard' для глобального перехвата
        keyboard.add_hotkey('shift+caps lock', self.hotkey_pressed.emit)