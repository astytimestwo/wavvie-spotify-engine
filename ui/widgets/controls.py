"""Builders that give every page the same labels, buttons and column layout."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget


def label(text="", role=None, wrap=True, selectable=False):
    widget = QLabel(text)
    widget.setTextFormat(Qt.PlainText)
    widget.setWordWrap(wrap)
    if role:
        widget.setProperty("role", role)
    if selectable:
        widget.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
    return widget


def button(text, role, name):
    widget = QPushButton(text)
    widget.setProperty("role", role)
    widget.setObjectName(name)
    widget.setCursor(Qt.PointingHandCursor)
    return widget


def rule():
    line = QFrame()
    line.setProperty("role", "rule")
    line.setFixedHeight(1)
    return line


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        # Read the widget once: after reparenting, the layout item no longer refers to it.
        widget = item.widget()
        if widget is not None:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


def scroll_column(owner, top=32, bottom=32):
    """Give owner a vertical scroll area holding one centred column up to 600 px wide."""
    outer = QVBoxLayout(owner)
    outer.setContentsMargins(0, 0, 0, 0)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    outer.addWidget(scroll)
    content = QWidget()
    scroll.setWidget(content)
    row = QHBoxLayout(content)
    row.setContentsMargins(24, top, 24, bottom)
    column = QWidget()
    column.setMaximumWidth(600)
    row.addStretch(1)
    row.addWidget(column, 100)
    row.addStretch(1)
    layout = QVBoxLayout(column)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)
    return scroll, layout
