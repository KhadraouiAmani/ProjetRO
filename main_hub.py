import sys
import os
import subprocess
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QFrame, QGridLayout)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QIcon, QPalette, QColor, QLinearGradient

class AppCard(QFrame):
    def __init__(self, title, description, icon_text, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.setup_ui(title, description, icon_text)
        
    def setup_ui(self, title, description, icon_text):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setLineWidth(2)
        self.setStyleSheet("""
            AppCard {
                background-color: white;
                border-radius: 15px;
                border: 2px solid #e0e0e0;
            }
            AppCard:hover {
                border: 2px solid #4CAF50;
                background-color: #f5f5f5;
            }
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Icon
        icon_label = QLabel(icon_text)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("""
            QLabel {
                font-size: 48px;
                color: #4CAF50;
                background-color: #E8F5E9;
                border-radius: 40px;
                padding: 20px;
            }
        """)
        icon_label.setFixedSize(100, 100)
        
        # Title
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #2C3E50;")
        
        # Description
        desc_label = QLabel(description)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setFont(QFont("Arial", 10))
        desc_label.setStyleSheet("color: #7F8C8D;")
        
        # Launch button
        launch_btn = QPushButton("Launch Application")
        launch_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        launch_btn.clicked.connect(self.launch_app)
        
        # Add widgets to layout
        icon_container = QHBoxLayout()
        icon_container.addStretch()
        icon_container.addWidget(icon_label)
        icon_container.addStretch()
        
        layout.addLayout(icon_container)
        layout.addWidget(title_label)
        layout.addWidget(desc_label)
        layout.addStretch()
        layout.addWidget(launch_btn)
        
        self.setLayout(layout)
        
    def launch_app(self):
        try:
            if os.path.exists(self.file_path):
                # Get the directory containing the file
                file_dir = os.path.dirname(os.path.abspath(self.file_path))
                # Launch the Python file
                subprocess.Popen([sys.executable, self.file_path], cwd=file_dir)
                print(f"Launched: {self.file_path}")
            else:
                print(f"File not found: {self.file_path}")
        except Exception as e:
            print(f"Error launching {self.file_path}: {str(e)}")


class OptimizationHub(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Optimization Tools Hub")
        self.setMinimumSize(1200, 800)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(30)
        main_layout.setContentsMargins(40, 40, 40, 40)
        
        # Set background color
        central_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #E3F2FD, stop:1 #E8F5E9);
            }
        """)
        
        # Header
        header_layout = QVBoxLayout()
        header_layout.setSpacing(10)
        
        title = QLabel("🚀 Optimization Tools Hub")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 32, QFont.Weight.Bold))
        title.setStyleSheet("color: #1565C0; background: transparent;")
        
        subtitle = QLabel("Select an optimization tool to launch")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setFont(QFont("Arial", 14))
        subtitle.setStyleSheet("color: #424242; background: transparent;")
        
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        
        # Applications grid
        grid_layout = QGridLayout()
        grid_layout.setSpacing(20)
        
        # Define applications with their paths
        apps = [
            {
                "title": "Ambulance Allocation",
                "description": "Dynamic ambulance allocation and routing optimization",
                "icon": "🚑",
                "path": "amira/gui_dynamic.py"
            },
            {
                "title": "Vehicle Routing Problem",
                "description": "VRP optimization and route planning solutions",
                "icon": "🚚",
                "path": "belkis/interface_vrp.py"
            },
            {
                "title": "5G Antenna Allocation",
                "description": "Optimal placement and allocation of 5G antennas",
                "icon": "📡",
                "path": "islem/local_v7.py"
            },
            {
                "title": "Cutting Stock Problem",
                "description": "Optimize cutting patterns for material efficiency",
                "icon": "✂️",
                "path": "CS.py"
            },
            {
                "title": "Shortest Path",
                "description": "Find optimal paths using advanced algorithms",
                "icon": "🗺️",
                "path": "project11.py"
            }
        ]
        
        # Add application cards to grid
        row, col = 0, 0
        for app in apps:
            card = AppCard(
                app["title"],
                app["description"],
                app["icon"],
                app["path"]
            )
            card.setMinimumSize(350, 280)
            grid_layout.addWidget(card, row, col)
            
            col += 1
            if col > 2:  # 3 columns
                col = 0
                row += 1
        
        # Footer
        footer = QLabel("© 2024 Optimization Tools Suite | Version 1.0")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setFont(QFont("Arial", 9))
        footer.setStyleSheet("color: #757575; background: transparent; margin-top: 20px;")
        
        # Add all to main layout
        main_layout.addLayout(header_layout)
        main_layout.addLayout(grid_layout)
        main_layout.addStretch()
        main_layout.addWidget(footer)
        
        central_widget.setLayout(main_layout)


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern look
    
    window = OptimizationHub()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()