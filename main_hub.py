import sys
import os
import importlib.util
import inspect
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QFrame, QGridLayout,
                             QGraphicsDropShadowEffect, QTabWidget, QMessageBox, QScrollArea,
                             QTabBar)  # <--- Ajout de QTabBar ici
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QAction

# Configuration des couleurs et du style global
STYLE_CONFIG = {
    "background": "#F4F7F6",
    "card_bg": "#FFFFFF",
    "text_primary": "#2C3E50",
    "text_secondary": "#7F8C8D",
    "accent": "#3498DB",
    "accent_hover": "#2980B9",
    "success": "#2ECC71",
    "font_family": "Segoe UI" if os.name == 'nt' else "Helvetica"
}

# --- 1. La Carte Application (Modifiée pour émettre un signal) ---
class AppCard(QFrame):
    # Signal personnalisé : titre de l'app, chemin du fichier
    launch_requested = pyqtSignal(str, str)

    def __init__(self, title, description, icon_text, file_path, parent=None):
        super().__init__(parent)
        self.title = title
        self.file_path = file_path
        self.setup_ui(title, description, icon_text)
        
    def setup_ui(self, title, description, icon_text):
        self.setFixedSize(360, 320)
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
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setYOffset(5)
        shadow.setColor(QColor(0, 0, 0, 20))
        self.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(25, 30, 25, 30)
        
        icon_bg = QLabel(icon_text)
        icon_bg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_bg.setFont(QFont(STYLE_CONFIG['font_family'], 32))
        icon_bg.setFixedSize(80, 80)
        icon_bg.setStyleSheet(f"background-color: #F0F8FF; border-radius: 40px; color: {STYLE_CONFIG['text_primary']};")
        
        icon_container = QHBoxLayout()
        icon_container.addStretch()
        icon_container.addWidget(icon_bg)
        icon_container.addStretch()
        
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(QFont(STYLE_CONFIG['font_family'], 14, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {STYLE_CONFIG['text_primary']}; border: none;")
        
        desc_label = QLabel(description)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setFont(QFont(STYLE_CONFIG['font_family'], 10))
        desc_label.setStyleSheet(f"color: {STYLE_CONFIG['text_secondary']}; border: none;")
        
        launch_btn = QPushButton("Ouvrir dans un onglet")
        launch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        launch_btn.setFixedHeight(40)
        launch_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {STYLE_CONFIG['accent']};
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-family: {STYLE_CONFIG['font_family']};
            }}
            QPushButton:hover {{ background-color: {STYLE_CONFIG['accent_hover']}; }}
        """)
        # Connexion du bouton au signal
        launch_btn.clicked.connect(self.emit_launch)
        
        layout.addLayout(icon_container)
        layout.addWidget(title_label)
        layout.addWidget(desc_label)
        layout.addStretch()
        layout.addWidget(launch_btn)
        self.setLayout(layout)

    def emit_launch(self):
        self.launch_requested.emit(self.title, self.file_path)

    def enterEvent(self, event):
        self.move(self.x(), self.y() - 2)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.move(self.x(), self.y() + 2)
        super().leaveEvent(event)

# --- 2. Le Widget d'Accueil (La grille de cartes) ---
class HomeDashboard(QWidget):
    request_tab_open = pyqtSignal(str, str) # Signal vers la Main Window

    def __init__(self, base_dir):
        super().__init__()
        self.base_dir = base_dir
        self.setup_ui()

    def setup_ui(self):
        # Utilisation d'un ScrollArea au cas où l'écran est petit
        main_layout = QVBoxLayout(self)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(60, 50, 60, 50)
        content_layout.setSpacing(30)
        
        # Header
        header_layout = QVBoxLayout()
        title = QLabel("Portail d'Optimisation")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont(STYLE_CONFIG['font_family'], 28, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {STYLE_CONFIG['text_primary']};")
        
        subtitle = QLabel("Sélectionnez un module pour l'ouvrir dans un nouvel onglet")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setFont(QFont(STYLE_CONFIG['font_family'], 12))
        subtitle.setStyleSheet(f"color: {STYLE_CONFIG['text_secondary']}; margin-bottom: 20px;")
        
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        
        # Grid
        grid_layout = QGridLayout()
        grid_layout.setSpacing(30)
        grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        apps = [
            {"title": "Allocation Ambulances", "desc": "Optimisation dynamique.", "icon": "🚑", "path": "amira/gui_dynamic.py"},
            {"title": "Vehicle Routing (VRP)", "desc": "Planification de tournées.", "icon": "🚚", "path": "belkis/interface_vrp.py"},
            {"title": "Réseau 5G", "desc": "Placement optimal antennes.", "icon": "📡", "path": "islem/local_v7.py"},
            {"title": "Cutting Stock", "desc": "Minimisation des chutes.", "icon": "✂️", "path": "CS.py"},
            {"title": "Plus Court Chemin", "desc": "Algorithmes graphe.", "icon": "🗺️", "path": "projet11.py"}
        ]
        
        row, col, max_cols = 0, 0, 3
        for app in apps:
            abs_path = os.path.join(self.base_dir, app["path"])
            card = AppCard(app["title"], app["desc"], app["icon"], abs_path)
            card.launch_requested.connect(self.request_tab_open.emit)
            grid_layout.addWidget(card, row, col)
            col += 1
            if col >= max_cols:
                col = 0; row += 1
        
        content_layout.addLayout(header_layout)
        content_layout.addLayout(grid_layout)
        content_layout.addStretch()
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

# --- 3. La Fenêtre Principale avec Onglets ---
class OptimizationHub(QMainWindow):
    def __init__(self):
        super().__init__()
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.setWindowTitle("Optimization Hub - Projet RO")
        self.setMinimumSize(1280, 850)
        
        # Initialisation des onglets
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True) # Permettre de fermer les onglets
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid #E0E0E0; background: {STYLE_CONFIG['background']}; }}
            QTabBar::tab {{
                background: #E0E0E0;
                color: {STYLE_CONFIG['text_primary']};
                padding: 10px 20px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background: white;
                font-weight: bold;
                border-bottom: 2px solid {STYLE_CONFIG['accent']};
            }}
            QTabBar::close-button {{ image: none; }} 
            /* Note: Style du bouton fermer simplifié pour l'exemple */
        """)
        
        # Onglet Accueil
        self.home = HomeDashboard(self.base_dir)
        self.home.request_tab_open.connect(self.open_module_in_tab)
        
        # Le premier onglet (Dashboard) n'est pas fermable via l'index, on gère ça dans close_tab
        self.tabs.addTab(self.home, "🏠 Accueil")
        
        # Cacher le bouton fermer sur l'onglet Accueil (Index 0)
        # Cacher le bouton fermer sur l'onglet Accueil (Index 0)
        self.tabs.tabBar().setTabButton(0, QTabBar.ButtonPosition.RightSide, None)
        self.tabs.tabBar().setTabButton(0, QTabBar.ButtonPosition.LeftSide, None)
        

        self.setCentralWidget(self.tabs)

    def close_tab(self, index):
        # On empêche de fermer l'accueil (index 0)
        if index > 0:
            widget = self.tabs.widget(index)
            self.tabs.removeTab(index)
            widget.deleteLater()

    def open_module_in_tab(self, title, file_path):
        # Vérifier si le fichier existe
        if not os.path.exists(file_path):
            QMessageBox.critical(self, "Erreur", f"Fichier introuvable :\n{file_path}")
            return

        # 1. Charger dynamiquement le module Python
        try:
            # Créer un nom de module unique basé sur le nom du fichier
            module_name = os.path.basename(file_path).replace('.py', '')
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            
            # Ajouter le dossier du module au PATH pour qu'il puisse trouver ses propres dépendances
            module_dir = os.path.dirname(file_path)
            if module_dir not in sys.path:
                sys.path.append(module_dir)
            
            # Exécuter le module
            spec.loader.exec_module(module)
            
            # 2. Chercher une classe principale (QMainWindow ou QWidget) dans le module
            target_class = None
            
            # Option A: Chercher une classe qui hérite de QMainWindow ou QWidget
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, (QMainWindow, QWidget)):
                    # On évite d'importer QMainWindow lui-même
                    if obj.__module__ == module_name:
                        target_class = obj
                        break
            
            if target_class:
                # Instancier la classe
                app_widget = target_class()
                
                # Ajouter l'instance comme un nouvel onglet
                new_tab_index = self.tabs.addTab(app_widget, title)
                self.tabs.setCurrentIndex(new_tab_index)
                print(f"Module {module_name} chargé avec succès.")
            else:
                QMessageBox.warning(self, "Erreur d'intégration", 
                                    f"Aucune classe 'QMainWindow' ou 'QWidget' trouvée dans {file_path}.\n"
                                    "Le fichier doit contenir une classe principale.")

        except Exception as e:
            import traceback
            error_msg = traceback.format_exc()
            QMessageBox.critical(self, "Erreur de chargement", 
                                 f"Impossible de charger le module {title}.\n\nErreur:\n{str(e)}")
            print(error_msg)

def main():
    app = QApplication(sys.argv)
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
        app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
    
    window = OptimizationHub()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()