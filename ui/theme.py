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
    MUTED_TEXT = "#929EAF"
    
    SPOTIFY_GREEN = "#1ED760"
    SPOTIFY_HOVER = "#35E477"
    SOFT_MINT = "#68F0AC"
    VIOLET_ACCENT = "#8B73FF"
    CYAN_ACCENT = "#55DDE0"
    WARNING = "#F5C451"
    ERROR = "#FF627D"
    POPPY = "#F24A3D"
    POPPY_HOVER = "#FF5C4E"
    # wavvie helper palette ("low tide")
    DEEP = "#0F2326"
    SURFACE = "#163338"
    RAISED = "#1D4047"
    LINE = "#2A5259"
    FOAM = "#EEF5F1"
    MIST = "#9DBAB6"
    SUN = "#F7C873"
    SUN_HOVER = "#FFD68F"
    ON_SUN = "#0F2326"
    CORAL = "#FF9A8B"
    SEA = "#8FE3B0"
    TAG_TEXT = "#CFE3DE"
    
    # Fonts
    FONT_HEADINGS = "Loubag"
    FONT_BODY = "Agrandir"
    FONT_MONO = "Agrandir"

    @classmethod
    def get_style_sheet(cls) -> str:
        from ui.resources import resource_path

        checkmark_icon = str(resource_path("checkmark.svg")).replace("\\", "/")
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
                color: {cls.APP_BG};
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
                width: 22px;
                height: 22px;
                border: 2px solid {cls.BORDER};
                border-radius: 7px;
                background-color: {cls.SECONDARY_SURFACE};
            }}
            
            QCheckBox::indicator:unchecked:hover {{
                border-color: {cls.MUTED_TEXT};
            }}
            
            QCheckBox::indicator:checked {{
                background-color: {cls.SPOTIFY_GREEN};
                border-color: {cls.SPOTIFY_GREEN};
                image: url("{checkmark_icon}");
            }}

            QCheckBox::indicator:checked:hover {{
                background-color: {cls.SPOTIFY_HOVER};
                border-color: {cls.SPOTIFY_HOVER};
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

            QComboBox {{
                background: {cls.SECONDARY_SURFACE};
                color: {cls.STRONG_TEXT};
                border: 1px solid {cls.BORDER};
                border-radius: 12px;
                padding: 10px 12px;
            }}
            QComboBox QAbstractItemView, QCalendarWidget QAbstractItemView, QMenu {{
                background: {cls.ELEVATED_SURFACE};
                color: {cls.STRONG_TEXT};
                selection-background-color: {cls.HOVER_SURFACE};
                selection-color: {cls.STRONG_TEXT};
                border: 1px solid {cls.BORDER};
            }}
            QPushButton:focus, QComboBox:focus {{
                border: 2px solid {cls.SOFT_MINT};
            }}
            QCheckBox:focus {{ color: {cls.STRONG_TEXT}; }}
            QCheckBox::indicator:focus {{ border: 2px solid {cls.SOFT_MINT}; }}
            QPushButton:disabled, QPushButton[class="primary"]:disabled,
            QPushButton[class="accent"]:disabled, QPushButton[class="danger"]:disabled {{
                background: {cls.ELEVATED_SURFACE};
                color: {cls.MUTED_TEXT};
                border: 1px solid {cls.BORDER};
            }}
            QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{ color: {cls.MUTED_TEXT}; }}
            QToolTip {{
                background: {cls.ELEVATED_SURFACE}; color: {cls.STRONG_TEXT};
                border: 1px solid {cls.BORDER}; padding: 8px;
            }}
            QScrollArea {{ border: none; }}
            QSplitter::handle {{ background: {cls.BORDER}; width: 1px; }}
        """

    @classmethod
    def helper_style_sheet(cls) -> str:
        from ui.resources import resource_path

        check = str(resource_path("checkmark.svg")).replace("\\", "/")
        chevron = str(resource_path("chevron_down.svg")).replace("\\", "/")
        return f"""
            QWidget {{ color: {cls.FOAM}; font-family: {cls.FONT_BODY}; font-size: 15px; background: transparent; }}
            QMainWindow, QDialog {{ background: {cls.DEEP}; }}
            QLabel[role="headline"] {{ font-family: {cls.FONT_HEADINGS}; font-size: 34px; }}
            QLabel[role="body"] {{ color: {cls.MIST}; }}
            QLabel[role="secondary"] {{ color: {cls.MIST}; font-size: 13px; }}
            QLabel[role="meta"] {{ color: {cls.MIST}; font-size: 12px; }}
            QLabel[role="note"] {{ color: {cls.CORAL}; font-size: 14px; }}
            QLabel[role="section"] {{ font-weight: bold; }}
            QLabel[role="code"] {{ background: {cls.SURFACE}; border: 1px solid {cls.LINE}; border-radius: 8px; padding: 6px 10px; }}
            QLabel[role="tag"] {{ background: {cls.RAISED}; color: {cls.TAG_TEXT}; border-radius: 9px; padding: 1px 8px; font-size: 12px; }}
            QLabel#artwork {{ background: {cls.RAISED}; border-radius: 6px; }}
            QFrame[role="rule"] {{ background: {cls.LINE}; border: none; }}
            QPushButton {{ border: 2px solid transparent; border-radius: 10px; padding: 6px; background: transparent; color: {cls.MIST}; }}
            QPushButton:hover {{ color: {cls.FOAM}; }}
            QPushButton:focus {{ border-color: {cls.FOAM}; }}
            QPushButton:disabled {{ color: {cls.LINE}; }}
            QPushButton[role="primary"] {{ background: {cls.SUN}; color: {cls.ON_SUN}; border-radius: 22px; padding: 0 24px; min-height: 40px; font-weight: bold; }}
            QPushButton[role="primary"]:hover {{ background: {cls.SUN_HOVER}; }}
            QPushButton[role="primary"]:focus {{ border-color: {cls.FOAM}; }}
            QPushButton[role="danger"] {{ color: {cls.CORAL}; }}
            QFrame#songRow {{ border: 2px solid transparent; border-radius: 10px; }}
            QFrame#songRow:hover {{ background: {cls.SURFACE}; }}
            QFrame#songRow:focus {{ border-color: {cls.FOAM}; }}
            QLineEdit, QSpinBox, QDateEdit, QComboBox {{ background: {cls.SURFACE}; border: 1px solid {cls.LINE}; border-radius: 10px; padding: 7px 12px; color: {cls.FOAM}; selection-background-color: {cls.SUN}; selection-color: {cls.ON_SUN}; }}
            QLineEdit:focus, QSpinBox:focus, QDateEdit:focus, QComboBox:focus {{ border: 2px solid {cls.FOAM}; padding: 6px 11px; }}
            QSpinBox::up-button, QSpinBox::down-button {{ width: 0px; border: none; }}
            QDateEdit::drop-down, QComboBox::drop-down {{ border: none; width: 28px; }}
            QDateEdit::down-arrow, QComboBox::down-arrow {{ image: url("{chevron}"); width: 14px; height: 14px; }}
            QComboBox QAbstractItemView {{ background: {cls.SURFACE}; color: {cls.FOAM}; border: 1px solid {cls.LINE}; selection-background-color: {cls.RAISED}; selection-color: {cls.FOAM}; outline: none; }}
            QCalendarWidget QWidget {{ background: {cls.SURFACE}; color: {cls.FOAM}; alternate-background-color: {cls.SURFACE}; }}
            QCalendarWidget QToolButton {{ color: {cls.FOAM}; background: transparent; border: none; padding: 4px 8px; }}
            QCalendarWidget QAbstractItemView:enabled {{ color: {cls.FOAM}; selection-background-color: {cls.SUN}; selection-color: {cls.ON_SUN}; }}
            QCalendarWidget QAbstractItemView:disabled {{ color: {cls.LINE}; }}
            QCheckBox {{ spacing: 10px; color: {cls.FOAM}; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; border: 2px solid {cls.LINE}; border-radius: 6px; background: {cls.SURFACE}; }}
            QCheckBox::indicator:checked {{ background: {cls.SUN}; border-color: {cls.SUN}; image: url("{check}"); }}
            QCheckBox:focus {{ color: {cls.SUN}; }}
            QPlainTextEdit {{ background: {cls.SURFACE}; border: 1px solid {cls.LINE}; border-radius: 10px; padding: 8px; color: {cls.FOAM}; font-size: 13px; }}
            QScrollArea {{ border: none; }}
            QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
            QScrollBar::handle:vertical {{ background: {cls.LINE}; border-radius: 3px; min-height: 28px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
            QToolTip {{ background: {cls.SURFACE}; color: {cls.FOAM}; border: 1px solid {cls.LINE}; padding: 6px; }}
        """
