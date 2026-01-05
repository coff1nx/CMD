from PySide6.QtWidgets import QTextEdit
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor
from PySide6.QtCore import Qt

class TerminalView(QTextEdit): # Меняем на QTextEdit для поддержки ссылок
    def __init__(self):
        super().__init__()
        # Настройки для "чистого" вида терминала
        self.setReadOnly(True)
        self.setUndoRedoEnabled(False)
        self.setAcceptRichText(True)
        self.setTextInteractionFlags(Qt.TextBrowserInteraction | Qt.LinksAccessibleByMouse)
        
        # Цветовая палитра
        self.colors = {
            "user_cmd": "#58a6ff",   # Ярко-синий (стиль GitHub)
            "normal": "#dcdcdc",     # Основной серый 
            "success": "#3fb950",    # Приятный зеленый
            "warning": "#d29922",    # Горчичный
            "error": "#f85149",      # Мягкий красный
            "traceback": "#bc8cff",  # Светло-фиолетовый
            "hint": "#39c5bb"        # Бирюзовый
        }

    def append_formatted(self, text: str, text_type: str):
        color = self.colors.get(text_type, self.colors["normal"])
        html_text = text.replace('\n', '<br>')
        
        # Создаем уникальный стиль для каждой строки с эффектом "Солнечных лучей"
        # Оранжевый центр, переходящий в красный по краям при наведении
        style = f'''
        <style>
            .log_line {{
                color: {color};
                text-decoration: none;
                padding: 2px;
            }}
            .log_line:hover {{
                color: #ffcc00; /* Оранжевый текст */
                background: qradialgradient(
                    cx: 0.5, cy: 0.5, radius: 1.0,
                    fx: 0.5, fy: 0.5,
                    stop: 0 #ff8c00,  /* Оранжевый центр */
                    stop: 0.8 #ff0000, /* Красные лучи к углам */
                    stop: 1 transparent
                );
                border-radius: 5px;
            }}
        </style>
        <span class="log_line">{html_text}</span>
        '''
        
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(style)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
        
        # Получаем цвет или дефолтный серый
        color = self.colors.get(text_type, self.colors["normal"])
        
        # Подготавливаем текст: заменяем переносы строк на HTML-теги
        html_text = text.replace('\n', '<br>')
        
        # Формируем HTML со стилем цвета
        # Используем <span> для раскраски
        formatted_html = f'<span style="color: {color};">{html_text}</span>'
        
        cursor.insertHtml(formatted_html)
        
        # Автопрокрутка вниз
        self.setTextCursor(cursor)
        self.ensureCursorVisible()