"""
Interface Graphique pour le VRP Transport de Fonds - Tunisie
Version avec design moderne et thème lumineux amélioré
"""

import sys
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QSpinBox, QDoubleSpinBox, QTextEdit, QGroupBox, QFormLayout,
    QMessageBox, QSplitter, QHeaderView, QProgressBar, QScrollArea
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.patches as mpatches


from belkis.projet_optimisation import VRPTransportFonds

# --- Thread pour ne pas bloquer l'IHM ---
class WorkerThread(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    def __init__(self, vrp_model, params):
        super().__init__()
        self.vrp_model = vrp_model
        self.params = params
    def run(self):
        try:
            solution = self.vrp_model.resoudre(**self.params)
            self.finished.emit(solution)
        except Exception as e:
            self.error.emit(str(e))

# --- Visualisation ---
class VisualisationCanvas(FigureCanvas):
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(8, 6), facecolor='#f8f9fa')
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self.setStyleSheet("background-color: #f8f9fa; border-radius: 8px;")
    
    def plot_solution(self, solution, positions, noms, niveaux_danger=None):
        self.ax.clear()
        self.ax.set_facecolor('#ffffff')
        if not positions or len(positions) == 0:
            self.ax.set_title("Aucune donnée", fontsize=12, pad=15)
            self.draw()
            return
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7']
        for i, (x, y) in enumerate(positions):
            nom = noms[i] if i < len(noms) else f"Point {i}"
            if i == 0:
                self.ax.scatter(x, y, c='#FF6B6B', s=300, marker='s', zorder=5, 
                              edgecolors='#2d3436', linewidth=2.5, alpha=0.9)
                self.ax.annotate(nom, (x, y), textcoords="offset points", 
                               xytext=(0, 14), ha='center', fontsize=9, 
                               fontweight='bold', color='#2d3436')
            else:
                self.ax.scatter(x, y, c='#74b9ff', s=180, zorder=5, 
                              edgecolors='#2d3436', linewidth=1.5, alpha=0.9)
                self.ax.annotate(nom, (x, y), textcoords="offset points", 
                               xytext=(0, 11), ha='center', fontsize=8, color='#2d3436')
        
        if solution and solution.get('status') == 'OPTIMAL' and 'tournees' in solution:
            for k, route in solution['tournees'].items():
                if len(route) > 2:
                    color = colors[k % len(colors)]
                    for i in range(len(route) - 1):
                        idx_start = route[i]
                        idx_end = route[i + 1]
                        if idx_start < len(positions) and idx_end < len(positions):
                            start = positions[idx_start]
                            end = positions[idx_end]
                            lw = 2.5
                            linestyle = '-'
                            alpha = 0.7
                            if niveaux_danger is not None:
                                danger = niveaux_danger[idx_start][idx_end]
                                if danger > 5:
                                    linestyle = '--'
                                    lw = 3.5
                                    alpha = 0.9
                            self.ax.annotate('', xy=end, xytext=start, 
                                           arrowprops=dict(arrowstyle='->', color=color, 
                                                         lw=lw, linestyle=linestyle, 
                                                         alpha=alpha))
            legend_elements = [
                mpatches.Patch(color=colors[k], label=f'Camion {k+1}')
                for k in solution['tournees'].keys() if len(solution['tournees'][k]) > 2
            ]
            if legend_elements:
                self.ax.legend(handles=legend_elements, loc='upper right', 
                             framealpha=0.95, edgecolor='#dfe6e9')
        
        self.ax.set_title("Tournées Optimales - Transport de Fonds", 
                         fontsize=12, fontweight='600', color='#2d3436', pad=15)
        self.ax.set_xlabel("Position X (km)", fontsize=10, color='#636e72')
        self.ax.set_ylabel("Position Y (km)", fontsize=10, color='#636e72')
        self.ax.grid(True, alpha=0.2, linestyle='--', linewidth=0.8, color='#b2bec3')
        self.ax.spines['top'].set_color('#dfe6e9')
        self.ax.spines['right'].set_color('#dfe6e9')
        self.ax.spines['bottom'].set_color('#b2bec3')
        self.ax.spines['left'].set_color('#b2bec3')
        self.fig.tight_layout()
        self.draw()

    def plot_error(self, message):
        self.ax.clear()
        self.ax.set_facecolor('#ffffff')
        self.ax.text(0.5, 0.5, message, ha='center', va='center',
                    fontsize=11, color='#d63031', transform=self.ax.transAxes, wrap=True)
        self.ax.set_title("Erreur", fontsize=12, fontweight='bold', color='#d63031')
        self.ax.axis('off')
        self.fig.tight_layout()
        self.draw()

# --- Main Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🏦 Transport de Fonds - VRP Tunisie")
        self.setMinimumSize(1400, 900)
        self.apply_modern_theme()
        self.vrp_model = VRPTransportFonds()
        self.solution = None
        self.worker = None
        self.positions = []
        self.niveaux_danger = None
        self.setup_ui()
        self.charger_donnees_exemple()

    def apply_modern_theme(self):
        """Applique un thème moderne et lumineux"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f3f7;
            }
            QWidget {
                background-color: #ffffff;
                color: #2d3436;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QGroupBox {
                background-color: #ffffff;
                border: 2px solid #e1e8ed;
                border-radius: 10px;
                margin-top: 12px;
                padding-top: 15px;
                font-weight: 600;
                font-size: 11pt;
                color: #2d3436;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
            }
            QPushButton {
                background-color: #4ECDC4;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 600;
                font-size: 10pt;
                min-height: 35px;
            }
            QPushButton:hover {
                background-color: #45B7D1;
            }
            QPushButton:pressed {
                background-color: #3da8bd;
            }
            QPushButton:disabled {
                background-color: #b2bec3;
            }
            QPushButton#btn_resoudre {
                background-color: #00b894;
                font-size: 11pt;
                min-height: 40px;
            }
            QPushButton#btn_resoudre:hover {
                background-color: #00a383;
            }
            QPushButton#btn_reset {
                background-color: #74b9ff;
            }
            QPushButton#btn_reset:hover {
                background-color: #5fa8f5;
            }
            QSpinBox, QDoubleSpinBox {
                background-color: #f8f9fa;
                border: 2px solid #e1e8ed;
                border-radius: 6px;
                padding: 6px 10px;
                min-height: 28px;
                font-size: 10pt;
            }
            QSpinBox:focus, QDoubleSpinBox:focus {
                border: 2px solid #4ECDC4;
                background-color: #ffffff;
            }
            QTableWidget {
                background-color: #ffffff;
                gridline-color: #e1e8ed;
                border: 2px solid #e1e8ed;
                border-radius: 8px;
                font-size: 9pt;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QTableWidget::item:selected {
                background-color: #dfe6e9;
                color: #2d3436;
            }
            QHeaderView::section {
                background-color: #f1f3f5;
                color: #2d3436;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #4ECDC4;
                font-weight: 600;
                font-size: 9pt;
            }
            QTabWidget::pane {
                border: 2px solid #e1e8ed;
                border-radius: 8px;
                background-color: #ffffff;
                top: -2px;
            }
            QTabBar::tab {
                background-color: #f8f9fa;
                color: #636e72;
                border: 2px solid #e1e8ed;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 10px 20px;
                margin-right: 4px;
                font-weight: 600;
                font-size: 9pt;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                color: #4ECDC4;
                border-color: #4ECDC4;
                border-bottom: 2px solid #ffffff;
            }
            QTabBar::tab:hover {
                background-color: #e8f5f4;
            }
            QTextEdit {
                background-color: #f8f9fa;
                border: 2px solid #e1e8ed;
                border-radius: 8px;
                padding: 12px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
                color: #2d3436;
            }
            QLabel {
                color: #2d3436;
                font-size: 9.5pt;
            }
            QProgressBar {
                border: 2px solid #e1e8ed;
                border-radius: 8px;
                background-color: #f8f9fa;
                text-align: center;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #4ECDC4;
                border-radius: 6px;
            }
            QFormLayout QLabel {
                font-weight: 500;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: #f8f9fa;
                width: 12px;
                border-radius: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #b2bec3;
                border-radius: 6px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #4ECDC4;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                background-color: #f8f9fa;
                height: 12px;
                border-radius: 6px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background-color: #b2bec3;
                border-radius: 6px;
                min-width: 30px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #4ECDC4;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)

    def update_tables_size(self):
        n = self.spin_clients.value()
        current_rows = self.table_agences.rowCount()
        self.table_agences.setRowCount(n)
        for row in range(current_rows, n):
            self.table_agences.setItem(row, 0, QTableWidgetItem(f"Agence {row+1}"))
            self.table_agences.setItem(row, 1, QTableWidgetItem("100000"))
            self.table_agences.setItem(row, 2, QTableWidgetItem(str(np.random.randint(5, 25))))
            self.table_agences.setItem(row, 3, QTableWidgetItem(str(np.random.randint(5, 25))))
            self.table_agences.setItem(row, 4, QTableWidgetItem("08:00"))
            self.table_agences.setItem(row, 5, QTableWidgetItem("17:00"))
        headers = ["Siège"] + [f"Ag. {i}" for i in range(1, n + 1)]
        self.table_distances.setRowCount(n + 1)
        self.table_distances.setColumnCount(n + 1)
        self.table_distances.setHorizontalHeaderLabels(headers)
        self.table_distances.setVerticalHeaderLabels(headers)
        self.table_danger.setRowCount(n + 1)
        self.table_danger.setColumnCount(n + 1)
        self.table_danger.setHorizontalHeaderLabels(headers)
        self.table_danger.setVerticalHeaderLabels(headers)
        for i in range(n + 1):
            for j in range(n + 1):
                if self.table_danger.item(i, j) is None:
                    item = QTableWidgetItem("0")
                    self.table_danger.setItem(i, j, item)
        self.calculer_distances()

    def update_capacite_values(self):
        for row in range(self.table_capacite.rowCount()):
            item = self.table_capacite.item(row, 0)
            if item is None or item.text() == "":
                self.table_capacite.setItem(row, 0, QTableWidgetItem(str(self.spin_capacite.value())))

    def charger_donnees_exemple(self):
        n = 5
        self.spin_clients.setValue(n)
        self.table_agences.setRowCount(n)
        agences_data = [
            ("Agence Av. Bourguiba", 150000, 5, 3, "08:00", "11:00"),
            ("Agence Lac 1", 200000, 8, 10, "09:00", "12:00"),
            ("DAB Aéroport Carthage", 100000, 12, 6, "08:00", "13:00"),
            ("Agence La Marsa", 180000, 15, 12, "10:00", "14:00"),
            ("DAB Carrefour La Marsa", 120000, 10, 8, "08:00", "12:00"),
        ]
        for row, data in enumerate(agences_data):
            for col, value in enumerate(data):
                self.table_agences.setItem(row, col, QTableWidgetItem(str(value)))
        self.update_tables_size()
        danger_data = [
            [0, 2, 1, 3, 2, 3],
            [2, 0, 2, 4, 3, 4],
            [1, 2, 0, 2, 1, 2],
            [3, 4, 2, 0, 2, 5],
            [2, 3, 1, 2, 0, 3],
            [3, 4, 2, 5, 3, 0]
        ]
        for i in range(n + 1):
            for j in range(n + 1):
                item = QTableWidgetItem(str(danger_data[i][j]))
                if danger_data[i][j] <= 2:
                    item.setBackground(QColor(200, 255, 200))
                elif danger_data[i][j] <= 4:
                    item.setBackground(QColor(255, 255, 200))
                else:
                    item.setBackground(QColor(255, 200, 200))
                self.table_danger.setItem(i, j, item)
        noms = ["Siège Central"] + [d[0] for d in agences_data]
        self.positions = [(0, 0)] + [(row[2], row[3]) for row in agences_data]
        self.canvas.plot_solution(None, self.positions, noms)
        self.text_results.clear()
        self.label_validation.clear()

    def calculer_distances(self):
        n = self.spin_clients.value()
        self.positions = [(0, 0)]
        for row in range(n):
            try:
                x_item = self.table_agences.item(row, 2)
                y_item = self.table_agences.item(row, 3)
                x = float(x_item.text()) if x_item else 0
                y = float(y_item.text()) if y_item else 0
                self.positions.append((x, y))
            except:
                self.positions.append((0, 0))
        for i in range(n + 1):
            for j in range(n + 1):
                xi, yi = self.positions[i]
                xj, yj = self.positions[j]
                dist = np.sqrt((xi - xj) ** 2 + (yi - yj) ** 2)
                self.table_distances.setItem(i, j, QTableWidgetItem(f"{dist:.1f}"))

    def get_danger_matrix(self):
        n = self.spin_clients.value()
        danger = np.zeros((n + 1, n + 1))
        for i in range(n + 1):
            for j in range(n + 1):
                try:
                    item = self.table_danger.item(i, j)
                    danger[i][j] = float(item.text()) if item else 0
                except:
                    danger[i][j] = 0
        return danger

    def valider_donnees(self):
        n = self.spin_clients.value()
        capacite = self.spin_capacite.value()
        erreurs = []
        for row in range(n):
            try:
                demande_item = self.table_agences.item(row, 1)
                if demande_item:
                    demande = float(demande_item.text())
                    nom_item = self.table_agences.item(row, 0)
                    nom = nom_item.text() if nom_item else f"Agence {row+1}"
                    if demande > capacite:
                        erreurs.append(f"'{nom}': {demande:,.0f} TND > capacité {capacite:,.0f} TND")
            except ValueError:
                erreurs.append(f"Ligne {row+1}: demande invalide")
        return erreurs

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        
        # --- Panneau gauche ---
        left_panel = QWidget()
        left_panel_scroll = QWidget()
        left_scroll_area = QScrollArea()
        left_scroll_area.setWidgetResizable(True)
        left_scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        left_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        left_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        left_layout = QVBoxLayout(left_panel_scroll)
        left_layout.setSpacing(20)
        
        # Paramètres généraux
        params_group = QGroupBox("⚙️ Paramètres Généraux")
        params_layout = QFormLayout()
        params_layout.setSpacing(15)
        params_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        
        self.spin_clients = QSpinBox()
        self.spin_clients.setRange(2, 15)
        self.spin_clients.setValue(5)
        self.spin_clients.valueChanged.connect(self.update_tables_size)
        params_layout.addRow("Nombre d'agences:", self.spin_clients)
        
        self.spin_vehicules = QSpinBox()
        self.spin_vehicules.setRange(1, 10)
        self.spin_vehicules.setValue(2)
        params_layout.addRow("Nombre de véhicules:", self.spin_vehicules)
        
        self.table_capacite = QTableWidget()
        self.table_capacite.setColumnCount(1)
        self.table_capacite.setHorizontalHeaderLabels(["Capacité (TND)"])
        self.table_capacite.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_capacite.setRowCount(self.spin_vehicules.value())
        self.table_capacite.setMinimumHeight(150)
        self.table_capacite.setMaximumHeight(250)
        
        self.spin_capacite = QDoubleSpinBox()
        self.spin_capacite.setRange(10000, 50000000)
        self.spin_capacite.setValue(500000)
        self.spin_capacite.setSuffix(" TND")
        self.spin_capacite.setSingleStep(50000)
        params_layout.addRow("Capacité véhicule:", self.spin_capacite)
        
        for row in range(self.table_capacite.rowCount()):
            self.table_capacite.setItem(row, 0, QTableWidgetItem(str(self.spin_capacite.value())))
        self.spin_capacite.valueChanged.connect(self.update_capacite_values)
        
        def update_capacite_table():
            k = self.spin_vehicules.value()
            current_rows = self.table_capacite.rowCount()
            self.table_capacite.setRowCount(k)
            for row in range(current_rows, k):
                self.table_capacite.setItem(row, 0, QTableWidgetItem(str(self.spin_capacite.value())))
        
        self.spin_vehicules.valueChanged.connect(update_capacite_table)
        params_layout.addRow("Capacités individuelles:", self.table_capacite)
        
        params_group.setLayout(params_layout)
        left_layout.addWidget(params_group)
        
        # Paramètres de coût
        cout_group = QGroupBox("💰 Paramètres de Coût")
        cout_layout = QFormLayout()
        cout_layout.setSpacing(15)
        cout_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        
        self.spin_cout_fixe = QDoubleSpinBox()
        self.spin_cout_fixe.setRange(0, 5000)
        self.spin_cout_fixe.setValue(350)
        self.spin_cout_fixe.setSuffix(" TND/veh")
        self.spin_cout_fixe.setSingleStep(10)
        cout_layout.addRow("Coût fixe véhicule:", self.spin_cout_fixe)
        
        self.spin_cout_km = QDoubleSpinBox()
        self.spin_cout_km.setRange(0.1, 10.0)
        self.spin_cout_km.setValue(0.8)
        self.spin_cout_km.setSuffix(" TND/km")
        self.spin_cout_km.setSingleStep(0.1)
        cout_layout.addRow("Coût carburant:", self.spin_cout_km)
        
        self.spin_danger_max = QSpinBox()
        self.spin_danger_max.setRange(1, 10)
        self.spin_danger_max.setValue(8)
        self.spin_danger_max.setSpecialValueText("Pas de limite")
        cout_layout.addRow("Danger max autorisé:", self.spin_danger_max)
        
        self.spin_beta = QDoubleSpinBox()
        self.spin_beta.setRange(0, 5)
        self.spin_beta.setValue(1.0)
        self.spin_beta.setSingleStep(0.1)
        cout_layout.addRow("Poids du risque (β):", self.spin_beta)
        
        cout_group.setLayout(cout_layout)
        left_layout.addWidget(cout_group)
        
        # Onglets
        tabs = QTabWidget()
        tabs.setMinimumHeight(400)
        
        # Tab Agences
        tab_agences = QWidget()
        tab_agences_layout = QVBoxLayout(tab_agences)
        tab_agences_layout.setContentsMargins(10, 10, 10, 10)
        self.table_agences = QTableWidget()
        self.table_agences.setColumnCount(6)
        self.table_agences.setHorizontalHeaderLabels([
            "Nom", "Demande (TND)", "X (km)", "Y (km)", "Ouverture", "Fermeture"
        ])
        self.table_agences.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_agences.horizontalHeader().setStretchLastSection(True)
        self.table_agences.setMinimumHeight(300)
        tab_agences_layout.addWidget(self.table_agences)
        tabs.addTab(tab_agences, "🏢 Agences")
        
        # Tab Distances
        tab_distances = QWidget()
        tab_distances_layout = QVBoxLayout(tab_distances)
        tab_distances_layout.setContentsMargins(10, 10, 10, 10)
        self.table_distances = QTableWidget()
        self.table_distances.setMinimumHeight(300)
        self.table_distances.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        tab_distances_layout.addWidget(self.table_distances)
        btn_calc_distances = QPushButton("📏 Calculer distances")
        btn_calc_distances.clicked.connect(self.calculer_distances)
        tab_distances_layout.addWidget(btn_calc_distances)
        tabs.addTab(tab_distances, "📏 Distances")
        
        # Tab Danger
        tab_danger = QWidget()
        tab_danger_layout = QVBoxLayout(tab_danger)
        tab_danger_layout.setContentsMargins(10, 10, 10, 10)
        lbl_danger_info = QLabel("Niveau de danger: 0 (sûr) à 10 (très dangereux): \nCe niveau sera divisé par 10 et multiplié par β dans le calcul du coût total.")
        lbl_danger_info.setStyleSheet("color: #636e72; font-style: italic; padding: 8px;")
        tab_danger_layout.addWidget(lbl_danger_info)
        self.table_danger = QTableWidget()
        self.table_danger.setMinimumHeight(300)
        self.table_danger.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        tab_danger_layout.addWidget(self.table_danger)
        tabs.addTab(tab_danger, "🚨 Danger")
        
        left_layout.addWidget(tabs)
        
        # Boutons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)
        buttons_layout.setContentsMargins(0, 15, 0, 10)
        
        self.btn_resoudre = QPushButton("RÉSOUDRE")
        self.btn_resoudre.setObjectName("btn_resoudre")
        self.btn_resoudre.clicked.connect(self.lancer_optimisation)
        buttons_layout.addWidget(self.btn_resoudre)
        
        btn_reset = QPushButton("Réinitialiser")
        btn_reset.setObjectName("btn_reset")
        btn_reset.clicked.connect(self.charger_donnees_exemple)
        buttons_layout.addWidget(btn_reset)
        
        left_layout.addLayout(buttons_layout)
        
        self.label_validation = QLabel("")
        self.label_validation.setStyleSheet("font-weight: 600; font-size: 10pt; padding: 8px;")
        self.label_validation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(self.label_validation)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        left_layout.addWidget(self.progress_bar)
        
        # Ajouter un stretch à la fin pour pousser le contenu vers le haut
        left_layout.addStretch()
        
        # Configurer le scroll area
        left_scroll_area.setWidget(left_panel_scroll)
        left_panel_main_layout = QVBoxLayout(left_panel)
        left_panel_main_layout.setContentsMargins(0, 0, 0, 0)
        left_panel_main_layout.addWidget(left_scroll_area)
        
        # --- Panneau droit ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(12)
        
        viz_group = QGroupBox("🗺️ Visualisation")
        viz_layout = QVBoxLayout()
        self.canvas = VisualisationCanvas()
        viz_layout.addWidget(self.canvas)
        viz_group.setLayout(viz_layout)
        right_layout.addWidget(viz_group)
        
        results_group = QGroupBox("📊 Résultats")
        results_layout = QVBoxLayout()
        self.text_results = QTextEdit()
        self.text_results.setReadOnly(True)
        self.text_results.setFont(QFont("Consolas", 10))
        results_layout.addWidget(self.text_results)
        results_group.setLayout(results_layout)
        right_layout.addWidget(results_group)
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([480, 920])
        
        main_layout.addWidget(splitter)

    def get_data_from_tables(self):
        n = self.spin_clients.value()
        k = self.spin_vehicules.value()
        
        noms = []
        demandes = []
        fenetres = []
        for row in range(n):
            nom_item = self.table_agences.item(row, 0)
            nom = nom_item.text() if nom_item else f"Agence_{row+1}"
            demande_item = self.table_agences.item(row, 1)
            demande = float(demande_item.text()) if demande_item else 100000
            ouv_item = self.table_agences.item(row, 4)
            ouv = ouv_item.text() if ouv_item else "08:00"
            ferm_item = self.table_agences.item(row, 5)
            ferm = ferm_item.text() if ferm_item else "18:00"
            noms.append(nom)
            demandes.append(demande)
            try:
                h_ouv, m_ouv = map(int, ouv.split(':'))
                h_ferm, m_ferm = map(int, ferm.split(':'))
                min_ouv = (h_ouv - 8) * 60 + m_ouv
                min_ferm = (h_ferm - 8) * 60 + m_ferm
                fenetres.append((max(0, min_ouv), max(min_ouv + 60, min_ferm)))
            except:
                fenetres.append((0, 600))

        distances = np.zeros((n + 1, n + 1))
        for i in range(n + 1):
            for j in range(n + 1):
                try:
                    item = self.table_distances.item(i, j)
                    distances[i][j] = float(item.text()) if item else 0
                except:
                    distances[i][j] = 0

        niveaux_danger = self.get_danger_matrix()
        r_ij = niveaux_danger / 10.0
        
        try:
            capacites = []
            for row in range(self.table_capacite.rowCount()):
                item = self.table_capacite.item(row, 0)
                val = float(item.text()) if item and item.text() else self.spin_capacite.value()
                capacites.append(val)
        except Exception as e:
            capacites = [self.spin_capacite.value()] * k
            
        try:
            beta = self.spin_beta.value()
        except AttributeError:
            beta = 1.0

        return {
            'n_clients': n,
            'n_vehicules': k,
            'capacites_vehicules': capacites,
            'demandes': demandes,
            'distances': distances,
            'fenetres_temps': fenetres,
            'temps_service': [15] * n,
            'noms_clients': noms,
            'niveaux_danger': niveaux_danger,
            'rij': r_ij,
            'beta': beta,
            'cout_fixe_vehicule': self.spin_cout_fixe.value(),
            'cout_km': self.spin_cout_km.value(),
            'danger_max_autorise': self.spin_danger_max.value() if self.spin_danger_max.value() < 10 else None
        }

    def afficher_resultats(self, solution):
        self.btn_resoudre.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.solution = solution
        params = self.get_data_from_tables()
        noms_complets = ["Siège Central"] + params['noms_clients']
        if solution.get('status') == 'OPTIMAL':
            text = "=" * 55 + "\n"
            text += "  ✅ SOLUTION OPTIMALE TROUVÉE\n"
            text += "=" * 55 + "\n\n"
            text += f"💰 Coût total: {solution['cout_total']:.2f} TND\n"
            text += f"🚐 Véhicules utilisés: {solution['vehicules_utilises']}\n"
            text += f"💵 Coût fixe: {solution.get('cout_fixe_vehicule', '-'):.2f} TND/véhicule\n"
            text += "-" * 55 + "\n"
            text += "📍 DÉTAIL DES TOURNÉES:\n"
            text += "-" * 55 + "\n"
            used_camion = 1
            for k, route in solution['tournees'].items():
                if len(route) > 2:
                    text += f"\n🚐 CAMION {used_camion}:\n"
                    route_noms = [noms_complets[i] if i < len(noms_complets) else f"Point {i}" for i in route]
                    text += f"   Route: {' → '.join(route_noms)}\n"
                    charge = sum(params['demandes'][i-1] for i in route if 0 < i <= len(params['demandes']))
                    text += f"   💵 Charge: {charge:,.0f} TND\n"
                    if k in solution.get('stats_tournees', {}):
                        stats = solution['stats_tournees'][k]
                        text += f"   📏 Distance: {stats['distance']:.1f} km\n"
                        text += f"   🚨 Danger moyen: {stats['danger_moyen']:.1f}/10\n"
                        text += f"   💲 Coût variable: {stats['cout_variable']:.2f} TND\n"
                        text += f"   💲 Coût fixe: {stats['cout_fixe']:.2f} TND\n"
                        text += f"   💲 Coût total: {stats['cout_total']:.2f} TND\n"
                    used_camion += 1
            self.label_validation.setText("Solution trouvée!")
            self.label_validation.setStyleSheet("color: #00b894; font-weight: 600; font-size: 10pt; padding: 8px; background-color: #d5f4e6; border-radius: 6px;")
            self.canvas.plot_solution(solution, self.positions, noms_complets, params['niveaux_danger'])
        else:
            text = "=" * 55 + "\n"
            text += "  ❌ AUCUNE SOLUTION TROUVÉE\n"
            text += "=" * 55 + "\n\n"
            text += solution.get('message', 'Infeasible')
            self.label_validation.setText("❌ Problème infaisable")
            self.label_validation.setStyleSheet("color: #d63031; font-weight: 600; font-size: 10pt; padding: 8px; background-color: #ffe0e0; border-radius: 6px;")
            self.canvas.plot_solution(None, self.positions, noms_complets)
        self.text_results.setText(text)

    def lancer_optimisation(self):
        erreurs = self.valider_donnees()
        if erreurs:
            message = "ERREURS:\n\n" + "\n".join(f"• {e}" for e in erreurs)
            self.label_validation.setText("❌ Erreurs détectées")
            self.label_validation.setStyleSheet("color: #d63031; font-weight: 600; font-size: 10pt; padding: 8px; background-color: #ffe0e0; border-radius: 6px;")
            self.text_results.setText(message)
            QMessageBox.warning(self, "Validation", message)
            return
        self.label_validation.clear()
        self.btn_resoudre.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.text_results.setText("⏳ Optimisation en cours...")
        self.calculer_distances()
        params = self.get_data_from_tables()
        self.worker = WorkerThread(self.vrp_model, params)
        self.worker.finished.connect(self.afficher_resultats)
        self.worker.error.connect(self.afficher_erreur)
        self.worker.start()

    def afficher_erreur(self, message):
        self.btn_resoudre.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.label_validation.setText("❌ Erreur")
        self.label_validation.setStyleSheet("color: #d63031; font-weight: 600; font-size: 10pt; padding: 8px; background-color: #ffe0e0; border-radius: 6px;")
        QMessageBox.critical(self, "Erreur", f"Erreur:\n{message}")
        self.text_results.setText(f"ERREUR:\n{message}")

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()