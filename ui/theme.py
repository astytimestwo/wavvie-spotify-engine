class Theme:
    # wavvie palette ("low tide")
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

    FONT_HEADINGS = "Loubag"
    FONT_BODY = "Agrandir"
    FONT_MONO = "Agrandir"

    @classmethod
    def get_style_sheet(cls) -> str:
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
