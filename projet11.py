#version finale du projet
"""
OptiRoute_Ultimate_Edition.py
Logiciel d'Optimisation de Tournées (VRPTW) - Version Enterprise Finale.
Fonctionnalités : Moteur Gurobi, Validation Stricte, Sauvegarde JSON, Export CSV.
"""

import sys
import json
import csv
import numpy as np

from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QPushButton, QTableWidget, QTableWidgetItem, QMessageBox,
    QHeaderView, QGroupBox, QFormLayout, QLineEdit, QTextEdit, QTabWidget,
    QFrame, QSplitter, QToolBar, QStatusBar, QFileDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QIcon

# Sécurisation de l'import Matplotlib pour compatibilité Hub
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
except ImportError:
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

# --- CONFIGURATION GRAPHIQUE PRO ---
C_PRIMARY = "#2c3e50"    # Bleu Nuit
C_ACCENT  = "#2980b9"    # Bleu Action
C_SUCCESS = "#27ae60"    # Vert
C_WARNING = "#f39c12"    # Orange
C_DANGER  = "#c0392b"    # Rouge
C_BG      = "#f4f6f9"    # Gris Fond

STYLESHEET = f"""
QMainWindow {{ background-color: {C_BG}; }}
QGroupBox {{
    font-weight: bold; border: 1px solid #dcdde1; border-radius: 8px;
    margin-top: 12px; background-color: white; font-family: 'Segoe UI';
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; color: {C_PRIMARY}; }}
QTableWidget {{
    border: 1px solid #dfe6e9; gridline-color: #ecf0f1;
    selection-background-color: {C_ACCENT}; background-color: white; font-size: 13px;
}}
QHeaderView::section {{
    background-color: #ecf0f1; padding: 5px; border: 0px;
    border-bottom: 2px solid {C_ACCENT}; font-weight: bold; color: {C_PRIMARY};
}}
QPushButton {{
    background-color: {C_ACCENT}; color: white; border-radius: 4px;
    padding: 8px 15px; font-weight: 600; border: none; font-size: 13px;
}}
QPushButton:hover {{ background-color: #3498db; }}
QLineEdit, QSpinBox {{ padding: 6px; border: 1px solid #bdc3c7; border-radius: 4px; background: white; }}
QLineEdit:focus, QSpinBox:focus {{ border: 1px solid {C_ACCENT}; }}
QTabWidget::pane {{ border: 1px solid #dcdde1; background: white; border-radius: 4px; }}
QTabBar::tab {{ background: #ecf0f1; color: #7f8c8d; padding: 8px 12px; margin-right: 2px; border-top-left-radius: 4px; border-top-right-radius: 4px; }}
QTabBar::tab:selected {{ background: white; color: {C_ACCENT}; border-top: 2px solid {C_ACCENT}; font-weight: bold; }}
"""

# Import Gurobi
try:
    from gurobipy import Model, GRB, quicksum
    GUROBI_AVAILABLE = True
except ImportError:
    GUROBI_AVAILABLE = False
    Model, GRB, quicksum = None, None, None

# -----------------------------
# FENÊTRE PRINCIPALE
# -----------------------------
class OptiRouteWindow(QMainWindow):
    
    # --- CLASSE INTERNE POUR KPI (Cachée du Hub) ---
    class KPI_Card(QFrame):
        def __init__(self, title, icon, color=C_SUCCESS):
            super().__init__()
            self.setFrameShape(QFrame.Shape.StyledPanel)
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: white; border-radius: 8px;
                    border-left: 5px solid {color}; border: 1px solid #ecf0f1;
                }}
            """)
            self.setMinimumWidth(130)
            layout = QVBoxLayout()
            layout.setContentsMargins(15, 10, 15, 10)
            
            self.lbl_title = QLabel(f"{icon}  {title}")
            self.lbl_title.setStyleSheet("color: #95a5a6; font-size: 11px; font-weight: bold; text-transform: uppercase;")
            self.lbl_value = QLabel("-")
            self.lbl_value.setStyleSheet(f"color: {C_PRIMARY}; font-size: 20px; font-weight: bold;")
            self.lbl_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            layout.addWidget(self.lbl_title)
            layout.addWidget(self.lbl_value)
            self.setLayout(layout)
            
        def set_value(self, text):
            self.lbl_value.setText(text)
    # -----------------------------------------------

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Route optimale - Réparateur de distributeurs automatiques")
        self.resize(1800, 800)
        self.setStyleSheet(STYLESHEET)
        
        self.last_schedule_data = None # Pour stocker les données à exporter
        
        self._init_ui()
        self._create_actions()
        self._create_menubar()
        self._create_toolbar()
        self._create_statusbar()
        self.create_tables()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)

        # --- GAUCHE ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 10, 0)
        
        lbl_cfg = QLabel("PARAMÉTRAGE")
        lbl_cfg.setStyleSheet(f"color: {C_PRIMARY}; font-weight: 900; font-size: 14px; letter-spacing: 1px;")
        left_layout.addWidget(lbl_cfg)

        param_group = QGroupBox("Paramètres de la Tournée")
        pg_layout = QFormLayout()
        
        self.spin_n = QSpinBox()
        self.spin_n.setRange(1, 30)
        self.spin_n.setValue(3)
        self.spin_n.valueChanged.connect(self.create_tables)
        
        self.edit_max_shift = QLineEdit("480")
        self.edit_max_shift.setPlaceholderText("Minutes")
        
        pg_layout.addRow("Nombre de Clients :", self.spin_n)
        pg_layout.addRow("Durée Max en minutes :", self.edit_max_shift)
        param_group.setLayout(pg_layout)
        left_layout.addWidget(param_group)

        self.tabs = QTabWidget()
        def create_tab(title, subtitle):
            w = QWidget()
            l = QVBoxLayout(w)
            l.addWidget(QLabel(subtitle))
            table = QTableWidget()
            table.setAlternatingRowColors(True)
            l.addWidget(table)
            self.tabs.addTab(w, title)
            return table

        self.dist_table = create_tab("📍 Distances", "Matrice des temps de trajet en minutes")
        self.service_table = create_tab("🔧 Services", "Temps de service en minutes")
        self.tw_table = create_tab("⏰ Horaires", "Fenêtres [Ouverture, Fermeture]")
        left_layout.addWidget(self.tabs)

        self.btn_solve = QPushButton("ORDONNANCER LA MISSION")
        self.btn_solve.setMinimumHeight(50)
        self.btn_solve.setStyleSheet(f"QPushButton {{ background-color: {C_SUCCESS}; font-size: 14px; border-radius: 6px; }} QPushButton:hover {{ background-color: #2ecc71; }}")
        self.btn_solve.clicked.connect(self.on_solve)
        left_layout.addWidget(self.btn_solve)

        # --- DROITE ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 0, 0, 0)

        lbl_dash = QLabel("TABLEAU DE BORD")
        lbl_dash.setStyleSheet(f"color: {C_PRIMARY}; font-weight: 900; font-size: 14px; letter-spacing: 1px;")
        right_layout.addWidget(lbl_dash)

        kpi_layout = QHBoxLayout()
        # Appel via self.KPI_Card car la classe est maintenant interne
        self.kpi_dist = self.KPI_Card("Distance Totale", "📏", C_ACCENT)
        self.kpi_time = self.KPI_Card("Heure Retour", "🏁", C_WARNING)
        self.kpi_stat = self.KPI_Card("Statut", "🤖", C_PRIMARY)
        kpi_layout.addWidget(self.kpi_dist)
        kpi_layout.addWidget(self.kpi_time)
        kpi_layout.addWidget(self.kpi_stat)
        right_layout.addLayout(kpi_layout)

        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.fig.patch.set_facecolor('white')
        self.ax = self.fig.add_subplot(111)
        
        grp_plot = QGroupBox("Carte de la Tournée")
        l_plot = QVBoxLayout()
        l_plot.addWidget(self.canvas)
        grp_plot.setLayout(l_plot)
        right_layout.addWidget(grp_plot, 2)

        grp_log = QGroupBox("Feuille de Route Détaillée")
        l_log = QVBoxLayout()
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setStyleSheet("border: 1px solid #dfe6e9; font-family: Consolas; font-size: 12px;")
        l_log.addWidget(self.results_text)
        grp_log.setLayout(l_log)
        right_layout.addWidget(grp_log, 1)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        main_layout.addWidget(splitter)

    # --- ACTIONS & MENUS ---
    def _create_actions(self):
        self.act_new = QAction("Nouveau", self)
        self.act_new.setShortcut("Ctrl+N")
        self.act_new.triggered.connect(self.on_reset)

        self.act_open = QAction("Ouvrir un scénario...", self)
        self.act_open.setShortcut("Ctrl+O")
        self.act_open.triggered.connect(self.load_from_json)

        self.act_save = QAction("Sauvegarder le scénario...", self)
        self.act_save.setShortcut("Ctrl+S")
        self.act_save.triggered.connect(self.save_to_json)

        self.act_export = QAction("Exporter les résultats (CSV)...", self)
        self.act_export.setShortcut("Ctrl+E")
        self.act_export.triggered.connect(self.export_to_csv)

        self.act_exit = QAction("Quitter", self)
        self.act_exit.setShortcut("Ctrl+Q")
        self.act_exit.triggered.connect(self.close)

        self.act_about = QAction("À propos", self)
        self.act_about.triggered.connect(self.show_about)

    def _create_menubar(self):
        menu = self.menuBar()
        file_menu = menu.addMenu("&Fichier")
        file_menu.addAction(self.act_new)
        file_menu.addSeparator()
        file_menu.addAction(self.act_open)
        file_menu.addAction(self.act_save)
        file_menu.addSeparator()
        file_menu.addAction(self.act_export)
        file_menu.addSeparator()
        file_menu.addAction(self.act_exit)
        help_menu = menu.addMenu("&Aide")
        help_menu.addAction(self.act_about)

    def _create_toolbar(self):
        toolbar = QToolBar()
        toolbar.setStyleSheet("QToolBar { background: white; border-bottom: 1px solid #dcdde1; padding: 5px; spacing: 10px; }")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        btn_new = QPushButton("✨ Nouveau")
        btn_new.clicked.connect(self.on_reset)
        toolbar.addWidget(btn_new)
        btn_open = QPushButton("📂 Ouvrir")
        btn_open.clicked.connect(self.load_from_json)
        toolbar.addWidget(btn_open)
        btn_save = QPushButton("💾 Sauvegarder")
        btn_save.clicked.connect(self.save_to_json)
        toolbar.addWidget(btn_save)
        toolbar.addSeparator()
        btn_export = QPushButton("📊 Exporter CSV")
        btn_export.clicked.connect(self.export_to_csv)
        toolbar.addWidget(btn_export)

    def _create_statusbar(self):
        self.status = QStatusBar()
        self.status.setStyleSheet("background: #ecf0f1; color: #34495e;")
        self.setStatusBar(self.status)
        self.status.showMessage("Prêt. Veuillez configurer les données.")

    # --- LOGIQUE TABLEAUX ---
    def create_tables(self):
        n_clients = self.spin_n.value()
        N = n_clients + 1 
        headers = [f"Dépôt" if i==0 else f"Client {i}" for i in range(N)]

        self.dist_table.setRowCount(N); self.dist_table.setColumnCount(N)
        self.dist_table.setHorizontalHeaderLabels(headers); self.dist_table.setVerticalHeaderLabels(headers)
        self.dist_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for i in range(N):
            for j in range(N):
                if not self.dist_table.item(i, j): 
                    val = "0" if i==j else "15"
                    self.dist_table.setItem(i, j, QTableWidgetItem(val))

        self.service_table.setRowCount(N); self.service_table.setColumnCount(1)
        self.service_table.setHorizontalHeaderLabels(["Durée en minutes"]); self.service_table.setVerticalHeaderLabels(headers)
        self.service_table.horizontalHeader().setStretchLastSection(True)
        for i in range(N):
            if not self.service_table.item(i, 0):
                val = "0" if i==0 else "10"
                self.service_table.setItem(i, 0, QTableWidgetItem(val))

        self.tw_table.setRowCount(N); self.tw_table.setColumnCount(2)
        self.tw_table.setHorizontalHeaderLabels(["Ouverture", "Fermeture"]); self.tw_table.setVerticalHeaderLabels(headers)
        self.tw_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        max_s = self.edit_max_shift.text()
        for i in range(N):
            if not self.tw_table.item(i, 0):
                self.tw_table.setItem(i, 0, QTableWidgetItem("0"))
                self.tw_table.setItem(i, 1, QTableWidgetItem(max_s))

    def on_reset(self):
        box = QMessageBox(self)
        box.setWindowTitle("Nouveau Projet")
        box.setText("Tout effacer et recommencer ?")
        box.setIcon(QMessageBox.Icon.Question)
        btn_oui = box.addButton("Oui", QMessageBox.ButtonRole.YesRole)
        btn_non = box.addButton("Non", QMessageBox.ButtonRole.NoRole)
        box.exec()
        if box.clickedButton() == btn_oui:
            self.spin_n.blockSignals(True)
            self.spin_n.setValue(3)
            self.spin_n.blockSignals(False)
            self.edit_max_shift.setText("480")
            self.dist_table.clearContents()
            self.service_table.clearContents()
            self.tw_table.clearContents()
            self.create_tables()
            self.results_text.clear()
            self.ax.clear()
            self.canvas.draw()
            self.kpi_dist.set_value("-")
            self.kpi_time.set_value("-")
            self.kpi_stat.set_value("Prêt")
            self.last_schedule_data = None
            self.status.showMessage("Nouveau projet vierge.")
        
    # --- SAUVEGARDE / CHARGEMENT (JSON) ---
    def get_current_data(self):
        try:
            N, dist, service, tw_e, tw_l, max_shift = self.read_inputs() 
            return {
                "n_clients": self.spin_n.value(),
                "max_shift": self.edit_max_shift.text(),
                "dist": dist.tolist(),
                "service": service.tolist(),
                "tw_e": tw_e.tolist(),
                "tw_l": tw_l.tolist()
            }
        except ValueError as e:
            return None 

    def save_to_json(self):
        data = self.get_current_data()
        if not data:
            QMessageBox.warning(self, "Impossible de sauvegarder", "Les données actuelles contiennent des erreurs.")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Sauvegarder Scénario", "", "Fichiers JSON (*.json)")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4)
                self.status.showMessage(f"Sauvegardé : {file_path}")
                QMessageBox.information(self, "Succès", "Scénario sauvegardé avec succès.")
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur lors de la sauvegarde : {e}")

    def load_from_json(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Ouvrir Scénario", "", "Fichiers JSON (*.json)")
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.spin_n.setValue(data["n_clients"])
                self.edit_max_shift.setText(data["max_shift"])
                self.create_tables() 
                N = data["n_clients"] + 1
                dist = data["dist"]
                service = data["service"]
                tw_e = data["tw_e"]
                tw_l = data["tw_l"]
                for i in range(N):
                    for j in range(N):
                        self.dist_table.setItem(i, j, QTableWidgetItem(str(dist[i][j])))
                    self.service_table.setItem(i, 0, QTableWidgetItem(str(service[i])))
                    self.tw_table.setItem(i, 0, QTableWidgetItem(str(tw_e[i])))
                    self.tw_table.setItem(i, 1, QTableWidgetItem(str(tw_l[i])))
                self.status.showMessage(f"Chargé : {file_path}")
                self.kpi_stat.set_value("Chargé")
                self.results_text.clear(); self.ax.clear(); self.canvas.draw()
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Fichier invalide ou corrompu : {e}")

    # --- EXPORT (CSV) ---
    def export_to_csv(self):
        if not self.last_schedule_data:
            QMessageBox.warning(self, "Rien à exporter", "Veuillez d'abord lancer une optimisation réussie.")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Exporter Résultats", "Resultats_Tournee.csv", "Fichiers CSV (*.csv)")
        if file_path:
            try:
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f, delimiter=';') 
                    writer.writerow(["Type", "Noeud", "Arrivee en minutes", "Service en minutes", "Depart en minutes"])
                    for step in self.last_schedule_data:
                        node_name = f"Client {step['n']}" if step['n'] > 0 else "Dépôt"
                        writer.writerow([
                            step['t'], node_name, 
                            f"{step['a']:.2f}".replace('.', ','), 
                            f"{step['s']:.2f}".replace('.', ','), 
                            f"{step['d']:.2f}".replace('.', ',')
                        ])
                self.status.showMessage(f"Exporté : {file_path}")
                QMessageBox.information(self, "Succès", "Fichier CSV généré avec succès.")
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur lors de l'export : {e}")

    def show_about(self):
        QMessageBox.about(self, "À Propos", 
                          "<b>Route optimale - Réparateur de distributeurs automatiques</b><br>"
                          "Version 2.4<br><br>"
                          "voyageur de Commerce (TSP) - Planification de la tournée d'un réparateur de distributeurs automatiques.<br>"
                          "Utilise : Python, PyQt6, Gurobi Optimizer.<br><br>"
                          "© 2025 - Tous droits réservés.")

    # --- VALIDATION (SECURE) ---
    def get_float_from_item(self, item):
        if item is None or item.text().strip() == "": return 0.0, False, "Cellule vide"
        try: return float(item.text().replace(',', '.')), True, ""
        except: return 0.0, False, f"Valeur invalide '{item.text()}'"

    def read_inputs(self):
        n_clients = self.spin_n.value(); N = n_clients + 1
        errors = []
        try:
            max_shift = float(self.edit_max_shift.text().replace(',', '.'))
            if max_shift <= 0: errors.append("• Shift Max doit être > 0.")
        except: errors.append("• Shift Max invalide.")

        dist = np.zeros((N,N))
        for i in range(N):
            for j in range(N):
                item = self.dist_table.item(i,j)
                val, ok, msg = self.get_float_from_item(item)
                if not ok: errors.append(f"• Distance [{i}->{j}] : {msg}")
                else:
                    if val < 0: errors.append(f"• Distance [{i}->{j}] : < 0 interdite.")
                    if i == j and val != 0: errors.append(f"• Distance [{i}->{j}] : Diagonale != 0.")
                    dist[i,j] = val

        service = np.zeros(N)
        for i in range(N):
            item = self.service_table.item(i,0)
            val, ok, msg = self.get_float_from_item(item)
            if not ok: errors.append(f"• Service {i} : {msg}")
            else:
                if val < 0: errors.append(f"• Service {i} : < 0 interdit.")
                if i > 0 and val == 0: errors.append(f"• Service {i} : Doit être > 0.")
                service[i] = val

        tw_e = np.zeros(N); tw_l = np.zeros(N)
        for i in range(N):
            e_val, ok_e, msg_e = self.get_float_from_item(self.tw_table.item(i,0))
            l_val, ok_l, msg_l = self.get_float_from_item(self.tw_table.item(i,1))
            if not ok_e or not ok_l: errors.append(f"• Horaires {i} invalides.")
            else:
                if e_val < 0 or l_val < 0: errors.append(f"• Horaires {i} doivent être positifs.")
                if e_val > l_val: errors.append(f"• {i} : Ouverture. ({e_val}) > Fermeture. ({l_val}).")
                tw_e[i] = e_val; tw_l[i] = l_val

        if errors:
            d_err = errors[:15]
            if len(errors)>15: d_err.append("...")
            raise ValueError("\n".join(d_err))
        return N, dist, service, tw_e, tw_l, max_shift

    # --- MOTEUR D'OPTIMISATION FLEXIBLE ---
    def solve_engine(self, N, dist, serv, tw_e, tw_l, time_limit, must_visit_all=True):
        model = Model("VRPTW_Smart")
        model.setParam('OutputFlag', 0)
        
        x = {}; t = {}; y = {} 
        
        for i in range(N):
            if must_visit_all or i == 0:
                y[i] = 1 
            else:
                y[i] = model.addVar(vtype=GRB.BINARY, name=f"visit_{i}")
            for j in range(N):
                if i != j: x[i,j] = model.addVar(vtype=GRB.BINARY)
            t[i] = model.addVar(lb=tw_e[i], ub=tw_l[i], vtype=GRB.CONTINUOUS)

        t_end = model.addVar(lb=0, ub=time_limit, vtype=GRB.CONTINUOUS)

        dist_cost = quicksum(dist[i,j]*x[i,j] for i in range(N) for j in range(N) if i!=j)
        
        if must_visit_all:
            model.setObjective(dist_cost, GRB.MINIMIZE)
        else:
            penalty = 100000 
            missed_cost = quicksum(penalty * (1 - y[i]) for i in range(1, N))
            model.setObjective(dist_cost + missed_cost, GRB.MINIMIZE)

        for i in range(N):
            model.addConstr(quicksum(x[i,j] for j in range(N) if i!=j) == y[i])
            model.addConstr(quicksum(x[j,i] for j in range(N) if i!=j) == y[i])

        M = time_limit + 1000
        for i in range(N):
            for j in range(1, N):
                if i!=j:
                    model.addConstr(t[j] >= t[i] + serv[i] + dist[i,j] - M*(1-x[i,j]))
        
        for i in range(1, N):
            model.addConstr(t_end >= t[i] + serv[i] + dist[i,0] - M*(1-x[i,0]))
        
        model.addConstr(t_end <= time_limit)
        model.optimize()
        return model, x, t, t_end, y
    
    # --- RÉSOLUTION INTELLIGENTE ---
    def on_solve(self):
        if Model is None: QMessageBox.critical(self, "Erreur", "Gurobi absent."); return
        try:
            N, dist, service, tw_e, tw_l, max_shift = self.read_inputs()
        except ValueError as e:
            QMessageBox.warning(self, "Erreur Données", str(e))
            self.kpi_stat.set_value("Erreur")
            return
        
        depot_close = tw_l[0]
        if max_shift > depot_close:
            msg_text = (f"La durée max définie ({max_shift} min) est supérieure à l'heure de fermeture du dépôt ({depot_close} min).\n"
                        f"Le camion devra rentrer avant {depot_close} min.\n"
                        f"Voulez-vous continuer ?")
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("Avertissement Logique")
            box.setText(msg_text)
            btn_oui = box.addButton("Oui, continuer", QMessageBox.ButtonRole.YesRole)
            btn_non = box.addButton("Non, annuler", QMessageBox.ButtonRole.NoRole)
            box.exec()
            if box.clickedButton() == btn_non:
                self.status.showMessage("Optimisation annulée.")
                return

        self.status.showMessage("Calcul en cours...")
        QApplication.processEvents()

        model_theo, _, _, _, _ = self.solve_engine(N, dist, service, tw_e, tw_l, max_shift, must_visit_all=True)
        is_theo_feasible = (model_theo.status == GRB.OPTIMAL)
        
        real_limit = min(max_shift, depot_close)
        model_real, x_re, t_re, t_end_re, y_re = self.solve_engine(N, dist, service, tw_e, tw_l, real_limit, must_visit_all=False)

        if model_real.status != GRB.OPTIMAL:
            self.kpi_stat.set_value("Erreur")
            QMessageBox.critical(self, "Echec", "Le solveur n'a pas trouvé de solution.")
            return

        visited = []
        missed = []
        for i in range(1, N):
            val = y_re[i].X if hasattr(y_re[i], "X") else y_re[i]
            if val > 0.5: visited.append(i)
            else: missed.append(i)

        if len(missed) > 0:
            self.kpi_stat.set_value("Partiel")
            self.status.showMessage(f"Terminé. {len(missed)} clients non livrés.")
        else:
            self.kpi_stat.set_value("Optimal")
            self.status.showMessage("Succès. Tous les clients livrés.")

        self.display_smart_visuals(x_re, t_re, t_end_re, visited, missed, N, service, dist, tw_e, is_theo_feasible, depot_close)

    def display_smart_visuals(self, x, t, t_end, visited, missed, N, service, dist, tw_e, is_theo_feasible, depot_close):
        tour = [0]
        curr = 0
        arcs = []
        while True:
            found = False
            for j in range(N):
                if curr != j and x[curr,j].X > 0.5:
                    arcs.append((curr, j))
                    curr = j
                    tour.append(curr)
                    found = True
                    break
            if curr == 0 or not found: break
        
        self.last_schedule_data = []
        cur_t = 0.0
        start = max(cur_t, tw_e[0])
        end = start + service[0]
        self.last_schedule_data.append({"n":0, "t":"Départ Dépôt", "a":start, "s":service[0], "d":end})
        cur_t = end
        prev = 0
        tot_d = 0.0
        
        for n in tour[1:-1]:
            tr = dist[prev, n]
            tot_d += tr
            arr = cur_t + tr
            s_start = max(arr, tw_e[n])
            s_end = s_start + service[n]
            self.last_schedule_data.append({"n":n, "t":"Client Livré", "a":arr, "s":service[n], "d":s_end})
            cur_t = s_end
            prev = n
            
        tr = dist[prev, 0]
        tot_d += tr
        arr = cur_t + tr
        self.last_schedule_data.append({"n":0, "t":"Retour Dépôt", "a":arr, "s":0, "d":arr})

        self.kpi_dist.set_value(f"{tot_d:.1f} min")
        self.kpi_time.set_value(f"{arr:.1f} min")
        
        html = "<h3 style='color:#2c3e50; font-family: Segoe UI;'>Rapport de Mission</h3>"
        
        if missed:
            html += f"<div style='background-color:#fdedec; border:1px solid {C_DANGER}; padding:10px; border-radius:4px;'>"
            html += f"<b style='color:{C_DANGER}'>⚠️ MISSION PARTIELLE : {len(missed)} client(s) annulé(s).</b><br>"
            html += f"Le camion est rentré à <b>{arr:.1f} min</b> (Fermeture : {depot_close} min).<br>"
            if is_theo_feasible:
                html += "<i>Une tournée complète était théoriquement possible si le dépôt restait ouvert plus longtemps.</i>"
            else:
                html += "<i>Même sans fermeture du dépôt, la durée max était insuffisante pour tout livrer.</i>"
            html += "</div><br>"
            html += f"<b style='color:{C_DANGER}'>Clients non livrés :</b><ul>"
            for m in missed: html += f"<li>Client {m}</li>"
            html += "</ul>"
        else:
            html += f"<div style='background-color:#eafaf1; border:1px solid {C_SUCCESS}; padding:10px; border-radius:4px;'>"
            html += f"<b style='color:{C_SUCCESS}'>✅ MISSION RÉUSSIE : Tous les clients sont livrés.</b>"
            html += "</div><br>"

        html += "<table width='100%' border='1' cellspacing='0' cellpadding='5' style='border-collapse:collapse; border-color:#ddd;'>"
        html += "<tr style='background:#ecf0f1; color:#2c3e50;'><th>Statut</th><th>Lieu</th><th>Arrivée</th><th>Départ</th></tr>"
        for s in self.last_schedule_data:
            if s['t'] == "Départ Dépôt": color = "#27ae60"
            elif s['t'] == "Retour Dépôt": color = "#c0392b"
            else: color = "#2c3e50"
            nm = "HUB" if s['n']==0 else f"Client {s['n']}"
            html += f"<tr style='color:{color}'><td><b>{s['t']}</b></td><td>{nm}</td><td>{s['a']:.1f}</td><td>{s['d']:.1f}</td></tr>"
        html += "</table>"
        self.results_text.setHtml(html)

        self.ax.clear()
        theta = np.linspace(0, 2*np.pi, N, endpoint=False) + np.pi/2
        xs = 10*np.cos(theta); ys = 10*np.sin(theta)
        
        for (i, j) in arcs:
            self.ax.annotate("", xy=(xs[j], ys[j]), xytext=(xs[i], ys[i]), 
                             arrowprops=dict(arrowstyle="-|>", color=C_PRIMARY, lw=2, shrinkA=15, shrinkB=15, mutation_scale=20), zorder=2)
        for v in visited:
            self.ax.scatter(xs[v], ys[v], s=500, c=C_ACCENT, edgecolors='white', linewidth=2, zorder=3)
        for m in missed:
            self.ax.scatter(xs[m], ys[m], s=400, c='#bdc3c7', edgecolors='white', linewidth=1, zorder=1)
        self.ax.scatter(xs[0], ys[0], s=600, c=C_DANGER, marker='s', edgecolors='white', linewidth=2, zorder=3)
        for i in range(N):
            lbl = "HUB" if i==0 else str(i)
            self.ax.text(xs[i], ys[i], lbl, color='white', fontweight='bold', ha='center', va='center', zorder=4, fontsize=9)
            
        from matplotlib.lines import Line2D
        legend_elem = [
            Line2D([0], [0], marker='o', color='w', markerfacecolor=C_ACCENT, markersize=10, label='Livré'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='#bdc3c7', markersize=10, label='Non Livré'),
            Line2D([0], [0], marker='s', color='w', markerfacecolor=C_DANGER, markersize=10, label='Dépôt')
        ]
        self.ax.legend(handles=legend_elem, loc='lower left', fontsize='x-small')
        self.ax.axis('off'); self.ax.set_aspect('equal')
        self.canvas.draw()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QtGui.QFont("Segoe UI", 9))
    win = OptiRouteWindow()
    win.show()
    sys.exit(app.exec())