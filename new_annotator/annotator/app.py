import sys
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication


def _apply_dark_palette(app: QApplication):
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,          QColor(45, 45, 45))
    pal.setColor(QPalette.ColorRole.WindowText,      QColor(220, 220, 220))
    pal.setColor(QPalette.ColorRole.Base,            QColor(35, 35, 35))
    pal.setColor(QPalette.ColorRole.AlternateBase,   QColor(53, 53, 53))
    pal.setColor(QPalette.ColorRole.ToolTipBase,     QColor(25, 25, 25))
    pal.setColor(QPalette.ColorRole.ToolTipText,     QColor(220, 220, 220))
    pal.setColor(QPalette.ColorRole.Text,            QColor(220, 220, 220))
    pal.setColor(QPalette.ColorRole.Button,          QColor(55, 55, 55))
    pal.setColor(QPalette.ColorRole.ButtonText,      QColor(220, 220, 220))
    pal.setColor(QPalette.ColorRole.BrightText,      QColor(255, 100, 100))
    pal.setColor(QPalette.ColorRole.Link,            QColor(42, 130, 218))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor(42, 130, 218))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
    app.setPalette(pal)


def run():
    app = QApplication(sys.argv)
    app.setApplicationName("Annotator")
    app.setOrganizationName("AnnotatorProject")
    _apply_dark_palette(app)

    from annotator.ui.main_window import MainWindow
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
