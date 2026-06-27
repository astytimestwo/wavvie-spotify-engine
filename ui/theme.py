class Theme:
    # Colors
    APP_BG = "#080A0D"
    MAIN_CANVAS = "#0C0F14"
    ELEVATED_SURFACE = "#12161D"
    SECONDARY_SURFACE = "#171C25"
    HOVER_SURFACE = "#1D2430"
    BORDER = "#28303D"
    
    STRONG_TEXT = "#F5F7FA"
    SECONDARY_TEXT = "#A1AAB8"
    MUTED_TEXT = "#687384"
    
    SPOTIFY_GREEN = "#1ED760"
    SPOTIFY_HOVER = "#35E477"
    SOFT_MINT = "#68F0AC"
    VIOLET_ACCENT = "#8B73FF"
    CYAN_ACCENT = "#55DDE0"
    WARNING = "#F5C451"
    ERROR = "#FF627D"
    
    # Fonts
    FONT_HEADINGS = "Loubag"
    FONT_BODY = "Futura PT"
    FONT_MONO = "Agrandir"

    @classmethod
    def get_style_sheet(cls) -> str:
        return f"""
            /* Base Widget Styles */
            QWidget {{
                color: {cls.SECONDARY_TEXT};
                font-family: {cls.FONT_BODY};
                font-size: 13px;
                background-color: transparent;
            }}
            
            QMainWindow {{
                background-color: {cls.APP_BG};
            }}
            
            /* ScrollBar Styling */
            QScrollBar:vertical {{
                background: {cls.APP_BG};
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }}
            
            QScrollBar::handle:vertical {{
                background: {cls.BORDER};
                min-height: 20px;
                border-radius: 4px;
            }}
            
            QScrollBar::handle:vertical:hover {{
                background: {cls.MUTED_TEXT};
            }}
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            
            QScrollBar:horizontal {{
                background: {cls.APP_BG};
                height: 8px;
                margin: 0px;
                border-radius: 4px;
            }}
            
            QScrollBar::handle:horizontal {{
                background: {cls.BORDER};
                min-width: 20px;
                border-radius: 4px;
            }}
            
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}

            /* Headers */
            QLabel[class="heading"] {{
                color: {cls.STRONG_TEXT};
                font-family: {cls.FONT_HEADINGS};
                font-weight: bold;
            }}
            
            /* Text inputs */
            QLineEdit, QDateEdit, QSpinBox {{
                background-color: {cls.SECONDARY_SURFACE};
                border: 1px solid {cls.BORDER};
                border-radius: 14px;
                padding: 10px 14px;
                color: {cls.STRONG_TEXT};
                font-family: {cls.FONT_BODY};
            }}
            
            QLineEdit:focus, QDateEdit:focus, QSpinBox:focus {{
                border: 1px solid {cls.VIOLET_ACCENT};
            }}
            
            QDateEdit::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left-width: 0px;
                border-top-right-radius: 14px;
                border-bottom-right-radius: 14px;
            }}

            /* Buttons */
            QPushButton {{
                background-color: {cls.SECONDARY_SURFACE};
                border: 1px solid {cls.BORDER};
                border-radius: 16px;
                padding: 10px 20px;
                color: {cls.STRONG_TEXT};
                font-weight: 500;
                font-family: {cls.FONT_BODY};
            }}
            
            QPushButton:hover {{
                background-color: {cls.HOVER_SURFACE};
                border-color: {cls.MUTED_TEXT};
            }}
            
            QPushButton:pressed {{
                background-color: {cls.ELEVATED_SURFACE};
            }}
            
            QPushButton[class="primary"] {{
                background-color: {cls.SPOTIFY_GREEN};
                border: 1px solid {cls.SPOTIFY_GREEN};
                color: {cls.APP_BG};
                font-weight: bold;
                border-radius: 16px;
            }}
            
            QPushButton[class="primary"]:hover {{
                background-color: {cls.SPOTIFY_HOVER};
                border-color: {cls.SPOTIFY_HOVER};
            }}
            
            QPushButton[class="primary"]:pressed {{
                background-color: {cls.SPOTIFY_GREEN};
            }}
            
            QPushButton[class="accent"] {{
                background-color: {cls.VIOLET_ACCENT};
                border: 1px solid {cls.VIOLET_ACCENT};
                color: {cls.STRONG_TEXT};
                font-weight: bold;
                border-radius: 16px;
            }}
            
            QPushButton[class="accent"]:hover {{
                background-color: #9D85FF;
            }}
            
            QPushButton[class="danger"] {{
                background-color: transparent;
                border: 1px solid {cls.ERROR};
                color: {cls.ERROR};
                border-radius: 16px;
            }}
            
            QPushButton[class="danger"]:hover {{
                background-color: rgba(255, 98, 125, 0.1);
            }}

            /* Toggles / Checkboxes */
            QCheckBox {{
                spacing: 8px;
            }}
            
            QCheckBox::indicator {{
                width: 20px;
                height: 20px;
                border: 1px solid {cls.BORDER};
                border-radius: 6px;
                background-color: {cls.SECONDARY_SURFACE};
            }}
            
            QCheckBox::indicator:unchecked:hover {{
                border-color: {cls.MUTED_TEXT};
            }}
            
            QCheckBox::indicator:checked {{
                background-color: {cls.VIOLET_ACCENT};
                border-color: {cls.VIOLET_ACCENT};
                image: url(data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>);
            }}
            
            /* Custom Cards style */
            QFrame[class="card"] {{
                background-color: {cls.ELEVATED_SURFACE};
                border: 1px solid {cls.BORDER};
                border-radius: 22px;
            }}
            
            QFrame[class="canvas"] {{
                background-color: {cls.MAIN_CANVAS};
                border-radius: 26px;
            }}
        """
