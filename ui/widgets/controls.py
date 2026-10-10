"""Builders that give every page the same labels, buttons and column layout."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from ui.widgets.tide import Tide


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


def centre(container, column, top=0, bottom=0):
    """Lay column out in container centred, up to 600 px wide, with at least 24 px either side."""
    row = QHBoxLayout(container)
    row.setContentsMargins(24, top, 24, bottom)
    column.setMaximumWidth(600)
    row.addStretch(1)
    row.addWidget(column, 100)
    row.addStretch(1)


def scroll_column(owner, top=32, bottom=32, centred=False):
    """Give owner a vertical scroll area holding one centred column up to 600 px wide, above a low tide.

    With centred, content shorter than the window sits a little above the middle; longer content
    scrolls from the top.
    """
    outer = QVBoxLayout(owner)
    outer.setContentsMargins(0, 0, 0, 0)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    # A click still lets the keys scroll, but Tab skips the area: it has no focus ring to show.
    scroll.setFocusPolicy(Qt.ClickFocus)
    outer.addWidget(scroll)
    content = Tide()
    scroll.setWidget(content)
    column = QWidget()
    centre(content, column, top, bottom + Tide.HEIGHT)
    layout = QVBoxLayout(column)
    layout.setContentsMargins(0, 0, 0, 0)
    if centred:
        # Spare height splits 2:3 above and below, so the block rests just above the middle.
        layout.setSpacing(0)
        layout.addStretch(2)
        block = QVBoxLayout()
        layout.addLayout(block)
        layout.addStretch(3)
        layout = block
    layout.setSpacing(12)
    return scroll, layout
