import sys
from PySide6.QtWidgets import QApplication
from ui.font_loader import load_bundled_fonts
from ui.main_window import MainWindow
from main import load_environment

def main():
    # Load env variables before starting
    load_environment()
    
    app = QApplication(sys.argv)
    app.setApplicationName("Wavefeed")
    app.setApplicationVersion("1.0.0")
    load_bundled_fonts()
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
