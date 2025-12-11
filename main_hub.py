import sys
import os
import subprocess
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QFrame, QGridLayout,
                             QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, QPoint
from PyQt6.QtGui import QFont, QColor, QPalette

# Configuration des couleurs et du style global
STYLE_CONFIG = {
    "background": "#F4F7F6",      # Gris très clair apaisant
    "card_bg": "#FFFFFF",         # Blanc pur
    "text_primary": "#2C3E50",    # Bleu nuit foncé
    "text_secondary": "#7F8C8D",  # Gris moyen
    "accent": "#3498DB",          # Bleu professionnel
    "accent_hover": "#2980B9",    # Bleu plus foncé
    "success": "#2ECC71",         # Vert pour les icônes
    "font_family": "Segoe UI" if os.name == 'nt' else "Helvetica"
}

class AppCard(QFrame):
    def __init__(self, title, description, icon_text, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.setup_ui(title, description, icon_text)
        
    def setup_ui(self, title, description, icon_text):
        self.setFixedSize(360, 320)
        
        # Style de la carte (CSS)
        self.setStyleSheet(f"""
            AppCard {{
                background-color: {STYLE_CONFIG['card_bg']};
                border-radius: 16px;
                border: 1px solid #E0E0E0;
            }}
            AppCard:hover {{
                border: 1px solid {STYLE_CONFIG['accent']};
            }}
        """)
        
        # Ombre portée (Shadow effect)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(5)
        shadow.setColor(QColor(0, 0, 0, 20)) # Ombre noire légère
        self.setGraphicsEffect(shadow)
        
        # Layout interne
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(25, 30, 25, 30)
        
        # 1. Icone
        icon_bg = QLabel(icon_text)
        icon_bg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_bg.setFont(QFont(STYLE_CONFIG['font_family'], 32)) # Emoji size
        icon_bg.setFixedSize(80, 80)
        icon_bg.setStyleSheet(f"""
            background-color: #F0F8FF;
            border-radius: 40px;
            color: {STYLE_CONFIG['text_primary']};
        """)
        
        # Centrer l'icône
        icon_container = QHBoxLayout()
        icon_container.addStretch()
        icon_container.addWidget(icon_bg)
        icon_container.addStretch()
        
        # 2. Titre
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font_title = QFont(STYLE_CONFIG['font_family'], 14, QFont.Weight.Bold)
        title_label.setFont(font_title)
        title_label.setStyleSheet(f"color: {STYLE_CONFIG['text_primary']}; border: none;")
        
        # 3. Description
        desc_label = QLabel(description)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setFont(QFont(STYLE_CONFIG['font_family'], 10))
        desc_label.setStyleSheet(f"color: {STYLE_CONFIG['text_secondary']}; border: none; padding: 0 5px;")
        
        # 4. Bouton Launch
        launch_btn = QPushButton("Lancer l'application")
        launch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        launch_btn.setFixedHeight(40)
        launch_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {STYLE_CONFIG['accent']};
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
                font-family: {STYLE_CONFIG['font_family']};
            }}
            QPushButton:hover {{
                background-color: {STYLE_CONFIG['accent_hover']};
            }}
            QPushButton:pressed {{
                background-color: #1F618D;
            }}
        """)
        launch_btn.clicked.connect(self.launch_app)
        
        # Assemblage
        layout.addLayout(icon_container)
        layout.addSpacing(10)
        layout.addWidget(title_label)
        layout.addWidget(desc_label)
        layout.addStretch()
        layout.addWidget(launch_btn)
        
        self.setLayout(layout)

    def enterEvent(self, event):
        # Petit effet d'élévation au survol
        self.move(self.x(), self.y() - 2)
        super().enterEvent(event)

    def leaveEvent(self, event):
        # Retour à la position normale
        self.move(self.x(), self.y() + 2)
        super().leaveEvent(event)
        
    def launch_app(self):
        try:
            if os.path.exists(self.file_path):
                absolute_path = os.path.abspath(self.file_path)
                project_root = os.path.dirname(os.path.abspath(__file__))
                
                env = os.environ.copy()
                if 'PYTHONPATH' in env:
                    env['PYTHONPATH'] = project_root + os.pathsep + env['PYTHONPATH']
                else:  
                    env['PYTHONPATH'] = project_root
                
                subprocess.Popen(
                    [sys.executable, absolute_path], 
                    cwd=project_root,
                    env=env
                )
                print(f"Launched: {absolute_path}")
            else:
                print(f"File not found: {self.file_path}")
        except Exception as e:
            print(f"Error: {str(e)}")


class OptimizationHub(QMainWindow):
    def __init__(self):
        super().__init__()
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Optimization Hub - Projet RO")
        self.setMinimumSize(1280, 850)
        
        # Widget Central avec fond
        central_widget = QWidget()
        central_widget.setStyleSheet(f"background-color: {STYLE_CONFIG['background']};")
        self.setCentralWidget(central_widget)
        
        # Layout Principal
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(60, 50, 60, 50)
        main_layout.setSpacing(30)
        
        # --- HEADER ---
        header_layout = QVBoxLayout()
        header_layout.setSpacing(5)
        
        title = QLabel("Portail d'Optimisation")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont(STYLE_CONFIG['font_family'], 28, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {STYLE_CONFIG['text_primary']};")
        
        subtitle = QLabel("Sélectionnez un module de recherche opérationnelle pour commencer")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setFont(QFont(STYLE_CONFIG['font_family'], 12))
        subtitle.setStyleSheet(f"color: {STYLE_CONFIG['text_secondary']}; margin-bottom: 20px;")
        
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        
        # --- GRID DES APPLICATIONS ---
        grid_layout = QGridLayout()
        grid_layout.setSpacing(30)
        grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Configuration des applications
        apps = [
            {
                "title": "Allocation Ambulances",
                "description": "Optimisation dynamique de l'allocation et du routage des ambulances.",
                "icon": "🚑",
                "path": "amira/gui_dynamic.py"
            },
            {
                "title": "Vehicle Routing (VRP)",
                "description": "Planification de tournées et optimisation logistique.",
                "icon": "🚚",
                "path": "belkis/interface_vrp.py"
            },
            {
                "title": "Réseau 5G",
                "description": "Placement optimal et allocation des antennes 5G.",
                "icon": "📡",
                "path": "islem/local_v7.py"
            },
            {
                "title": "Cutting Stock",
                "description": "Minimisation des chutes de découpe de matériaux.",
                "icon": "✂️",
                "path": "CS.py"
            },
            {
                "title": "Plus Court Chemin",
                "description": "Algorithmes de recherche de chemin optimal dans un graphe.",
                "icon": "🗺️",
                "path": "projet11.py"
            }
        ]
        
        # Création des cartes
        row, col = 0, 0
        max_cols = 3 # Nombre de colonnes
        
        for app in apps:
            absolute_path = os.path.join(self.base_dir, app["path"])
            card = AppCard(
                app["title"],
                app["description"],
                app["icon"],
                absolute_path
            )
            grid_layout.addWidget(card, row, col)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        # --- FOOTER ---
        footer_layout = QHBoxLayout()
        footer = QLabel("© 2024 Projet RO | Interface Intelligente")
        footer.setFont(QFont(STYLE_CONFIG['font_family'], 9))
        footer.setStyleSheet(f"color: #BDC3C7; margin-top: 30px;")
        footer_layout.addStretch()
        footer_layout.addWidget(footer)
        footer_layout.addStretch()
        
        # Ajout au layout principal
        main_layout.addLayout(header_layout)
        main_layout.addLayout(grid_layout)
        main_layout.addStretch()
        main_layout.addLayout(footer_layout)
        
        central_widget.setLayout(main_layout)

def main():
    app = QApplication(sys.argv)
    
    # Amélioration du rendu des polices (High DPI)
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
        app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
    
    window = OptimizationHub()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()