from typing import Dict, List, Tuple
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QLinearGradient, QFont
from PySide6.QtWidgets import QWidget
from ui.theme import Theme

class ReleaseTypeDonutChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(180, 180)
        self.data: List[Tuple[str, int, QColor]] = [
            ("Albums", 0, QColor(Theme.VIOLET_ACCENT)),
            ("Singles", 0, QColor(Theme.CYAN_ACCENT)),
            ("EPs", 0, QColor(Theme.WARNING)),
            ("Collabs", 0, QColor(Theme.ERROR))
        ]
        self.total = 0

    def set_data(self, albums: int, singles: int, eps: int, collabs: int):
        self.data = [
            ("Albums", albums, QColor(Theme.VIOLET_ACCENT)),
            ("Singles", singles, QColor(Theme.CYAN_ACCENT)),
            ("EPs", eps, QColor(Theme.WARNING)),
            ("Collabs", collabs, QColor(Theme.ERROR))
        ]
        self.total = albums + singles + eps + collabs
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        side = min(width, height)
        rect = QRectF((width - side) / 2.0 + 16, (height - side) / 2.0 + 16, side - 32, side - 32)
        
        center = rect.center()
        outer_radius = rect.width() / 2.0
        inner_radius = outer_radius * 0.65
        
        if self.total == 0:
            # Draw empty state ring
            painter.setPen(QPen(QColor(Theme.BORDER), 10, Qt.SolidLine, Qt.RoundCap))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(center, (outer_radius + inner_radius) / 2.0, (outer_radius + inner_radius) / 2.0)
            
            # Label
            painter.setPen(QPen(QColor(Theme.MUTED_TEXT)))
            font = painter.font()
            font.setFamily(Theme.FONT_HEADINGS)
            font.setPointSize(10)
            painter.setFont(font)
            painter.drawText(QRectF(center.x() - 50, center.y() - 10, 100, 20), Qt.AlignCenter, "No Tracks")
            return

        # Draw donut segments
        current_angle = 90.0  # Start at top
        
        for name, value, color in self.data:
            if value == 0:
                continue
                
            span_angle = -(value / self.total) * 360.0
            
            # Draw outer arc, lines, inner arc
            path = QPainterPath()
            path.arcTo(rect, current_angle, span_angle)
            
            # Subtract inner circle
            inner_rect = QRectF(center.x() - inner_radius, center.y() - inner_radius, inner_radius * 2, inner_radius * 2)
            inner_path = QPainterPath()
            inner_path.arcTo(inner_rect, current_angle + span_angle, -span_angle)
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawPath(path - inner_path)
            
            current_angle += span_angle
            
        # Draw central text
        painter.setPen(QPen(QColor(Theme.STRONG_TEXT)))
        font = painter.font()
        font.setFamily(Theme.FONT_HEADINGS)
        font.setPointSize(16)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(center.x() - 60, center.y() - 18, 120, 20), Qt.AlignCenter, str(self.total))
        
        font.setPointSize(9)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QPen(QColor(Theme.MUTED_TEXT)))
        painter.drawText(QRectF(center.x() - 60, center.y() + 4, 120, 15), Qt.AlignCenter, "TOTAL")


class RoleComparisonChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80)
        self.main_count = 0
        self.featured_count = 0

    def set_data(self, main: int, featured: int):
        self.main_count = main
        self.featured_count = featured
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        total = self.main_count + self.featured_count
        
        # Labels
        painter.setPen(QPen(QColor(Theme.SECONDARY_TEXT)))
        font = painter.font()
        font.setFamily(Theme.FONT_BODY)
        font.setPointSize(10)
        painter.setFont(font)
        
        painter.drawText(10, 20, f"Main Performers: {self.main_count}")
        painter.drawText(width - 150, 20, Qt.AlignRight, f"Features: {self.featured_count}")
        
        bar_y = 35
        bar_h = 12
        bar_w = width - 20
        
        # Draw empty background bar
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(Theme.SECONDARY_SURFACE)))
        painter.drawRoundedRect(10, bar_y, bar_w, bar_h, 6, 6)
        
        if total == 0:
            return
            
        main_ratio = self.main_count / total
        main_w = bar_w * main_ratio
        
        # Draw Main bar (violet)
        if main_w > 0:
            painter.setBrush(QBrush(QColor(Theme.VIOLET_ACCENT)))
            painter.drawRoundedRect(10, bar_y, main_w, bar_h, 6, 6)
            
        # Draw Featured bar (cyan)
        feat_w = bar_w - main_w
        if feat_w > 0:
            painter.setBrush(QBrush(QColor(Theme.CYAN_ACCENT)))
            painter.drawRoundedRect(10 + main_w, bar_y, feat_w, bar_h, 6, 6)


class ReleaseTimelineChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.timeline_data: List[Tuple[str, int]] = []

    def set_data(self, date_counts: Dict[str, int]):
        # Sort counts by date string
        sorted_dates = sorted(date_counts.keys())
        self.timeline_data = [(d, date_counts[d]) for d in sorted_dates]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # Margins
        left_m = 40
        right_m = 20
        top_m = 20
        bottom_m = 30
        
        chart_w = width - left_m - right_m
        chart_h = height - top_m - bottom_m
        
        # Grid lines
        painter.setPen(QPen(QColor(Theme.BORDER), 1, Qt.DashLine))
        painter.drawLine(left_m, top_m, left_m + chart_w, top_m)
        painter.drawLine(left_m, top_m + chart_h / 2, left_m + chart_w, top_m + chart_h / 2)
        painter.setPen(QPen(QColor(Theme.BORDER), 1, Qt.SolidLine))
        painter.drawLine(left_m, top_m + chart_h, left_m + chart_w, top_m + chart_h)
        
        if not self.timeline_data:
            # Empty state text
            painter.setPen(QPen(QColor(Theme.MUTED_TEXT)))
            font = painter.font()
            font.setFamily(Theme.FONT_BODY)
            painter.setFont(font)
            painter.drawText(QRectF(left_m, top_m, chart_w, chart_h), Qt.AlignCenter, "No Release Timeline Data")
            return
            
        max_val = max([count for date, count in self.timeline_data])
        if max_val == 0:
            max_val = 1
            
        # Draw Y axis values
        painter.setPen(QPen(QColor(Theme.MUTED_TEXT)))
        font = painter.font()
        font.setFamily(Theme.FONT_MONO)
        font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(5, top_m + 5, f"{max_val}")
        painter.drawText(5, top_m + chart_h / 2 + 5, f"{int(max_val/2)}")
        painter.drawText(5, top_m + chart_h + 5, "0")
        
        num_points = len(self.timeline_data)
        x_step = chart_w / max(1, num_points - 1)
        
        # Generate area path and line path
        area_path = QPainterPath()
        line_path = QPainterPath()
        
        for i, (date, count) in enumerate(self.timeline_data):
            x = left_m + i * x_step
            y = top_m + chart_h - (count / max_val) * chart_h
            
            if i == 0:
                area_path.moveTo(x, top_m + chart_h)
                area_path.lineTo(x, y)
                line_path.moveTo(x, y)
            else:
                area_path.lineTo(x, y)
                line_path.lineTo(x, y)
                
            if i == num_points - 1:
                area_path.lineTo(x, top_m + chart_h)
                area_path.closeSubpath()
                
        # Draw gradient area fill
        grad = QLinearGradient(0, top_m, 0, top_m + chart_h)
        grad.setColorAt(0.0, QColor(139, 115, 255, 80)) # Iris translucent
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawPath(area_path)
        
        # Draw line
        painter.setPen(QPen(QColor(Theme.CYAN_ACCENT), 2, Qt.SolidLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(line_path)
        
        # Draw dots at data points
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(Theme.STRONG_TEXT)))
        for i, (date, count) in enumerate(self.timeline_data):
            if count == 0:
                continue
            x = left_m + i * x_step
            y = top_m + chart_h - (count / max_val) * chart_h
            painter.drawEllipse(QPointF(x, y), 3, 3)
            
        # Draw X axis labels (Start, End date)
        painter.setPen(QPen(QColor(Theme.MUTED_TEXT)))
        font.setFamily(Theme.FONT_BODY)
        painter.setFont(font)
        start_date = self.timeline_data[0][0]
        end_date = self.timeline_data[-1][0]
        
        painter.drawText(left_m, top_m + chart_h + 18, start_date)
        painter.drawText(width - right_m - 100, top_m + chart_h + 18, Qt.AlignRight, end_date)
