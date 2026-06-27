import math
import random
import time
from typing import Optional
from PySide6.QtCore import QTimer, Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QRadialGradient, QImage, QPainterPath
from PySide6.QtWidgets import QWidget
from ui.theme import Theme

class CircularVisualizer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(280, 280)
        
        self.state = "idle"  # idle, scanning, rate_limit, error, complete
        self.artist_image: Optional[QImage] = None
        self.progress_percentage = 0.0
        
        # Animation parameters
        self.time_phase = 0.0
        self.num_bars = 60
        self.bar_values = [0.0] * self.num_bars
        self.target_values = [0.0] * self.num_bars
        
        # Event triggers
        self.pulse_intensity = 0.0
        self.collab_ripple = 0.0
        self.bloom_phase = 0.0
        
        # Timer for 60 FPS animation (16ms)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(16)
        
        self.last_update = time.time()

    def set_state(self, state: str):
        if state in ["idle", "scanning", "rate_limit", "error", "complete"]:
            self.state = state
            if state == "complete":
                self.bloom_phase = 1.0
            elif state == "scanning":
                self.bloom_phase = 0.0

    def set_artist_image(self, image: Optional[QImage]):
        self.artist_image = image
        self.update()

    def set_progress(self, progress: float):
        self.progress_percentage = max(0.0, min(100.0, progress))
        self.update()

    def trigger_track_discovery(self, is_collab: bool = False):
        self.pulse_intensity = 1.0
        if is_collab:
            self.collab_ripple = 1.0
        self.update()

    def update_animation(self):
        current_time = time.time()
        dt = current_time - self.last_update
        self.last_update = current_time
        
        self.time_phase += dt * 2.0
        
        # Decay events
        if self.pulse_intensity > 0:
            self.pulse_intensity -= dt * 4.0  # Decays in 250ms
            if self.pulse_intensity < 0:
                self.pulse_intensity = 0.0
                
        if self.collab_ripple > 0:
            self.collab_ripple -= dt * 2.0   # Decays in 500ms
            if self.collab_ripple < 0:
                self.collab_ripple = 0.0
                
        if self.state == "complete" and self.bloom_phase > 0:
            self.bloom_phase -= dt * 1.5
            if self.bloom_phase < 0:
                self.bloom_phase = 0.0

        # Target heights logic based on state
        for i in range(self.num_bars):
            if self.state == "idle":
                # Slow breathing sine waves
                base = 0.25 + 0.1 * math.sin(self.time_phase + i * 0.15)
                self.target_values[i] = base
            elif self.state == "scanning":
                # Energetic pseudo-random oscillations
                base = 0.35 + 0.25 * math.sin(self.time_phase * 2.5 + i * 0.4)
                # Random noise jump
                if random.random() < 0.05:
                    base += random.uniform(0.15, 0.45)
                # Add progress-percentage influence
                base += (self.progress_percentage / 100.0) * 0.1
                self.target_values[i] = base
            elif self.state == "rate_limit":
                # Restrained, sluggish, low breathing
                base = 0.15 + 0.05 * math.sin(self.time_phase * 0.5 + i * 0.1)
                self.target_values[i] = base
            elif self.state == "error":
                # Restrained red static
                base = 0.2 + 0.08 * math.cos(self.time_phase * 0.8 + i * 0.2)
                self.target_values[i] = base
            elif self.state == "complete":
                # Outward bloom explosion fading out
                base = self.bloom_phase * 0.8 + 0.1 * math.sin(self.time_phase + i * 0.3)
                self.target_values[i] = base

            # Interpolate towards target values (smooth filter)
            lerp_factor = 0.15 if self.state == "scanning" else 0.08
            self.bar_values[i] += (self.target_values[i] - self.bar_values[i]) * lerp_factor

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        center = QPointF(width / 2.0, height / 2.0)
        
        # Dimensions
        base_radius = min(width, height) * 0.25
        max_bar_length = base_radius * 0.75
        
        # Draw background radial glow in the center
        radial_grad = QRadialGradient(center, base_radius * 1.8)
        if self.state == "error":
            radial_grad.setColorAt(0.0, QColor(255, 98, 125, 25))
            radial_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        elif self.state == "scanning":
            radial_grad.setColorAt(0.0, QColor(139, 115, 255, 30))
            radial_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        else:
            radial_grad.setColorAt(0.0, QColor(30, 215, 96, 20))
            radial_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(radial_grad))
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.rect())
        
        # Draw bars
        for i in range(self.num_bars):
            angle = (i / self.num_bars) * 2.0 * math.pi
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            
            # Bar height calculation
            val = self.bar_values[i]
            
            # Discovery pulse overlay
            if self.pulse_intensity > 0:
                val += self.pulse_intensity * 0.35 * (1.0 + 0.5 * math.sin(i * 0.5))
                
            length = val * max_bar_length
            
            # Inner and Outer points
            inner_pt = QPointF(center.x() + base_radius * cos_a, center.y() + base_radius * sin_a)
            outer_pt = QPointF(center.x() + (base_radius + length) * cos_a, center.y() + (base_radius + length) * sin_a)
            
            # Select colors/pens
            pen = QPen()
            pen.setWidth(4)
            pen.setCapStyle(Qt.RoundCap)
            
            # Color configuration based on state and events
            if self.state == "error":
                # Error state uses warning/red theme
                color = QColor(Theme.ERROR)
            elif self.collab_ripple > 0:
                # Collaborations burst (violet/cyan gradient)
                color = QColor(Theme.VIOLET_ACCENT)
                # Interpolate color with cyan
                ratio = math.sin(i * 0.3) * 0.5 + 0.5
                color = QColor(
                    int(Theme.VIOLET_ACCENT[1:3], 16) * (1 - ratio) + int(Theme.CYAN_ACCENT[1:3], 16) * ratio,
                    int(Theme.VIOLET_ACCENT[3:5], 16) * (1 - ratio) + int(Theme.CYAN_ACCENT[3:5], 16) * ratio,
                    int(Theme.VIOLET_ACCENT[5:7], 16) * (1 - ratio) + int(Theme.CYAN_ACCENT[5:7], 16) * ratio
                )
            elif self.pulse_intensity > 0:
                # Discovered standard track (mint green flash)
                color = QColor(Theme.SOFT_MINT)
            elif self.state == "scanning":
                # Scanning rotates between green, mint and violet
                color = QColor(Theme.SPOTIFY_GREEN)
                # Fade out slightly towards the outer tips
            else:
                color = QColor(Theme.MUTED_TEXT)
            
            # Fade out alpha at outer edge
            pen.setColor(color)
            painter.setPen(pen)
            painter.drawLine(inner_pt, outer_pt)
            
        # Draw central disc
        disc_radius = base_radius - 4
        painter.setPen(QPen(QColor(Theme.BORDER), 2))
        painter.setBrush(QBrush(QColor(Theme.SECONDARY_SURFACE)))
        
        # Center circle path for clipping
        clip_path = QPainterPath()
        clip_path.addEllipse(center, disc_radius, disc_radius)
        
        # Save painter state to clip
        painter.save()
        painter.setClipPath(clip_path)
        
        if self.artist_image and not self.artist_image.isNull():
            # Draw scaled artist image cropped to circle
            scaled_img = self.artist_image.scaled(int(disc_radius * 2), int(disc_radius * 2), 
                                                 Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            x_offset = center.x() - disc_radius
            y_offset = center.y() - disc_radius
            # Center the image inside the disc
            painter.drawImage(QRectF(x_offset, y_offset, disc_radius * 2, disc_radius * 2), scaled_img)
        else:
            # Draw logo or app text
            painter.drawEllipse(center, disc_radius, disc_radius)
            painter.restore()
            painter.save()
            
            painter.setPen(QPen(QColor(Theme.STRONG_TEXT)))
            font = painter.font()
            font.setFamily(Theme.FONT_HEADINGS)
            font.setPointSize(18)
            font.setBold(True)
            painter.setFont(font)
            
            # Print current progress or wave text in center
            if self.state == "scanning":
                progress_text = f"{int(self.progress_percentage)}%"
                rect = QRectF(center.x() - disc_radius, center.y() - disc_radius, disc_radius * 2, disc_radius * 2)
                painter.drawText(rect, Qt.AlignCenter, progress_text)
            else:
                rect = QRectF(center.x() - disc_radius, center.y() - disc_radius, disc_radius * 2, disc_radius * 2)
                painter.drawText(rect, Qt.AlignCenter, "WAVE")
                
        painter.restore()
        
        # Draw border outline over center disc
        painter.setPen(QPen(QColor(Theme.BORDER), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(center, disc_radius, disc_radius)

    def sizeHint(self):
        return self.minimumSizeHint()

    def minimumSizeHint(self):
        return QRectF(0, 0, 280, 280).size().toSize()
