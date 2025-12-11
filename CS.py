# -*- coding: utf-8 -*-
import sys # acces aux arguments et fonctions système
import os

# --- ADAPTATION HUB : Passage à PyQt6 ---
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QTableWidget, QTableWidgetItem, QPushButton,
                             QLabel, QTextEdit, QTabWidget, QSpinBox, QDoubleSpinBox, QGroupBox,
                             QHeaderView, QFrame, QScrollArea, QMessageBox)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QColor # Nécessaire pour certains styles

import matplotlib.pyplot as plt
# --- ADAPTATION HUB : Backend compatible PyQt6 ---
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
except ImportError:
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

import gurobipy as gp
from gurobipy import GRB
from itertools import product

# ======================
# Styles (CSS/QSS) - Inchangé
# ======================
STYLESHEET = """
    QWidget {
        background-color: #f4f6f9;
        font-family: 'Segoe UI', 'Roboto', sans-serif;
        font-size: 10pt;
        color: #2c3e50;
    }
    QScrollArea {
        border: none;
        background-color: transparent;
    }
    QGroupBox {
        background-color: #ffffff;
        border: 1px solid #e1e4e8;
        border-radius: 8px;
        margin-top: 12px;
        padding-top: 25px;
        font-weight: bold;
        color: #34495e;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 5px;
        left: 10px;
        background-color: transparent;
    }
    QTableWidget {
        background-color: #ffffff;
        border: 1px solid #dcdcdc;
        border-radius: 4px;
        gridline-color: #eff0f1;
        selection-background-color: #3498db;
        selection-color: white;
    }
    QHeaderView::section {
        background-color: #ecf0f1;
        padding: 6px;
        border: none;
        border-right: 1px solid #dcdcdc;
        font-weight: bold;
        color: #2c3e50;
    }
    QTabWidget::pane {
        border: 1px solid #dcdcdc;
        background-color: #ffffff;
        border-radius: 4px;
    }
    QTabBar::tab {
        background-color: #e1e4e8;
        padding: 8px 20px;
        margin-right: 2px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        color: #7f8c8d;
    }
    QTabBar::tab:selected {
        background-color: #ffffff;
        color: #2c3e50;
        font-weight: bold;
        border-bottom: 2px solid #3498db;
    }
    QSpinBox {
        padding: 5px;
        border: 1px solid #bdc3c7;
        border-radius: 4px;
        background-color: white;
    }
    QTextEdit {
        background-color: #ffffff;
        border: 1px solid #dcdcdc;
        border-radius: 4px;
        font-family: 'Consolas', 'Courier New', monospace;
        color: #2c3e50;
    }
    QLabel {
        font-weight: 500;
    }
"""

# ======================
# Génération de patterns 
# ======================
def generate_patterns(stock_length, pieces, kerf=5):#peices = (longueur, quantité, nom)
    patterns = [] #initialisation liste des patterns
    n = len(pieces) #nombre de types de pièces
    if n == 0: return patterns
    max_counts = [] #liste des quantités max par type dans une barre
    for length, qty, name in pieces:
        max_fit = 0 #compteur du nombre max de pièces de ce type dans une barre
        current_length = 0 #longueur cumulée
        while current_length + length <= stock_length:#tant que longueur totale apres addition de la longuer ajoutée ne dépasse pas la longueur stock
            max_fit += 1 #on peut couper une pièce de plus
            current_length += length #on ajoute la longueur de la pièce
            if current_length < stock_length:#si on n'a pas encore atteint la longueur max, on ajoute le kerf
                current_length += kerf
        max_counts.append(min(max_fit, qty))
    for counts in product(*[range(m+1) for m in max_counts]):#genere toutes les combinaisons possibles de counts
        if sum(counts) == 0: continue #si somme des counts = 0, on passe au pattern suivant
        total_length = sum(counts[i] * pieces[i][0] for i in range(n))#calcul longueur totale 
        num_cuts = sum(counts)
        total_length += (num_cuts - 1) * kerf
        if total_length <= stock_length:
            pattern = {i: counts[i] for i in range(n) if counts[i] > 0} #pattern sous forme de dict {type de pieces: quantite}
            patterns.append(pattern)
    return patterns

# ======================
# Thread Solver 
# ======================
class SolverThread(QThread):#définit un thread pour exécuter le solveur Gurobi en arrière-plan .class SolverThread hérite de QThread
    finished = pyqtSignal(dict) #signal émis à la fin du calcul avec les résultats
    def __init__(self, stock_data, demand_100, demand_150, kerf, errors_pre_validation=None):
        super().__init__() 
        self.stock_data = stock_data
        self.demand_100 = demand_100
        self.demand_150 = demand_150
        self.kerf = kerf
        self.errors_pre = errors_pre_validation if errors_pre_validation else {}

    def run(self):#méthode exécutée automatiquement lorsque le thread démarre 
        results = {}
        
        # --- Calcul Diamètre 100 ---
        if "diameter_100" in self.errors_pre:
            results["diameter_100"] = {"error": self.errors_pre["diameter_100"]}
        else:
            try:
                results["diameter_100"] = self.solve_diameter(100, self.demand_100)
            except Exception as e:
                results["diameter_100"] = {"error": str(e)}

        # --- Calcul Diamètre 150 ---
        if "diameter_150" in self.errors_pre:
            results["diameter_150"] = {"error": self.errors_pre["diameter_150"]}
        else:
            try:
                results["diameter_150"] = self.solve_diameter(150, self.demand_150)
            except Exception as e:
                results["diameter_150"] = {"error": str(e)}

        self.finished.emit(results)#émission du signal finished avec les résultats

    def solve_diameter(self, diameter, demands):#résout le problème de cutting stock pour un diamètre donné
        if not demands or all(qty == 0 for _, qty, _ in demands):#si pas de demandes ou toutes les quantités sont nulles
            return {"cost": 0, "patterns": [], "stock_used": {}, "num_patterns": {}}#retourne coût 0 et pas de patterns utilisés
        model = gp.Model(f"CuttingStock_D{diameter}")#création d'un modèle Gurobi
        model.Params.OutputFlag = 0#désactivation de la sortie console de Gurobi
        all_patterns = {}#dictionnaire pour stocker tous les patterns générés
        x_vars = {}#initie un dictionnaire pour les variables de décision 
        for stock_idx, (length, cost, avail) in enumerate(self.stock_data):#pour chaque type de stock
            stock_name = f"S{stock_idx+1}"#nom du stock
            patterns = generate_patterns(length, demands, self.kerf)#génération des patterns pour ce stock
            all_patterns[stock_name] = patterns#stockage des patterns générés
            x_vars[stock_name] = {}#dictionnaire pour les variables de décision de ce stock
            for p_idx, pattern in enumerate(patterns):#pour chaque pattern généré
                x_vars[stock_name][p_idx] = model.addVar(vtype=GRB.CONTINUOUS, name=f"x_{stock_name}_{p_idx}")#variable de décision
        for piece_idx, (length, qty, name) in enumerate(demands):#pour chaque type de pièce demandée
            demand_expr = gp.LinExpr()#expression linéaire pour la contrainte de demande
            for stock_name in all_patterns:
                for p_idx, pattern in enumerate(all_patterns[stock_name]):
                    if piece_idx in pattern:
                        demand_expr += pattern[piece_idx] * x_vars[stock_name][p_idx]
            model.addConstr(demand_expr >= qty, f"Demand_{name}")
        stock_exprs = {}
        for stock_idx, (length, cost, avail) in enumerate(self.stock_data):
            stock_name = f"S{stock_idx+1}"
            stock_expr = gp.quicksum(x_vars[stock_name][p] for p in x_vars[stock_name])
            model.addConstr(stock_expr <= avail, f"Stock_{stock_name}")
            stock_exprs[stock_name] = stock_expr
        cost_expr = gp.LinExpr()
        for stock_idx, (length, cost, avail) in enumerate(self.stock_data):
            stock_name = f"S{stock_idx+1}"
            cost_expr += cost * stock_exprs[stock_name]
        model.setObjective(cost_expr, GRB.MINIMIZE)
        model.optimize()
        if model.status == GRB.OPTIMAL:
            used_patterns = []
            stock_used = {}
            num_patterns = {}
            for stock_idx, (length, cost, avail) in enumerate(self.stock_data):
                stock_name = f"S{stock_idx+1}"
                stock_total = 0
                num_patterns[stock_name] = len(all_patterns[stock_name])
                for p_idx in x_vars[stock_name]:
                    if x_vars[stock_name][p_idx].X > 0.01:
                        pattern = all_patterns[stock_name][p_idx]
                        pattern_desc = []
                        for piece_idx, count in pattern.items():
                            pattern_desc.append(f"{count}×{demands[piece_idx][2]}")
                        used_patterns.append({
                            "stock": stock_name,
                            "count": x_vars[stock_name][p_idx].X,
                            "pattern": ", ".join(pattern_desc)
                        })
                        stock_total += x_vars[stock_name][p_idx].X
                stock_used[stock_name] = stock_total
            return {"cost": model.ObjVal, "patterns": used_patterns, "stock_used": stock_used, "num_patterns": num_patterns}
        else:
            return {"cost": None, "patterns": [], "stock_used": {}, "infeasible": True}

# ======================
# Interface principale
# ======================
class CuttingStockApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Optimisation de Découpe - Gurobi")
        self.resize(1200, 900) 
        self.setStyleSheet(STYLESHEET) 
        
        # --- SCROLL AREA SETUP ---
        window_layout = QVBoxLayout(self)
        window_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.content_widget = QWidget()
        self.main_layout = QVBoxLayout(self.content_widget)
        self.main_layout.setSpacing(15)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.scroll_area.setWidget(self.content_widget)
        window_layout.addWidget(self.scroll_area)

        # Titre
        title = QLabel("Optimisation de Découpe Industrielle")
        title.setStyleSheet("font-size: 20pt; font-weight: bold; color: #2c3e50; margin-bottom: 10px;")
        # Adaptation PyQt6
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(title)

        # ===== CONFIGURATION =====
        config_group = QGroupBox("⚙️ Paramètres Généraux")
        config_layout = QHBoxLayout()
        config_layout.setSpacing(20)
        
        # STOCK (Limite à 10)
        l1 = QLabel("Types de stock:")
        self.num_stocks_spin = QSpinBox()
        self.num_stocks_spin.setRange(1, 10)
        self.num_stocks_spin.setValue(2)
        self.num_stocks_spin.setFixedWidth(80)
        self.num_stocks_spin.valueChanged.connect(self.update_stock_table)
        
        # KERF
        l2 = QLabel("Trait de scie (Kerf mm):")
        self.kerf_spin = QDoubleSpinBox()
        self.kerf_spin.setRange(0, 100)
        self.kerf_spin.setDecimals(2)
        self.kerf_spin.setSingleStep(0.1)
        self.kerf_spin.setValue(5.0)
        self.kerf_spin.setFixedWidth(60)

        # TYPES 100
        l3 = QLabel("Types Ø100mm:")
        self.num_types_100_spin = QSpinBox()
        self.num_types_100_spin.setRange(0, 10) 
        self.num_types_100_spin.setValue(3)  
        self.num_types_100_spin.setFixedWidth(80)
        self.num_types_100_spin.valueChanged.connect(self.update_demand_table_100)
        self.num_types_100_spin.valueChanged.connect(self.update_demand_table_150)
        
        # TYPES 150
        l4 = QLabel("Types Ø150mm:")
        self.num_types_150_spin = QSpinBox()
        self.num_types_150_spin.setRange(0, 10) 
        self.num_types_150_spin.setValue(3)
        self.num_types_150_spin.setFixedWidth(80)
        self.num_types_150_spin.valueChanged.connect(self.update_demand_table_150)

        for widget in [l1, self.num_stocks_spin, l2, self.kerf_spin, l3, self.num_types_100_spin, l4, self.num_types_150_spin]:
            config_layout.addWidget(widget)
        config_layout.addStretch()
        
        config_group.setLayout(config_layout)
        self.main_layout.addWidget(config_group)

        # ===== TABLE STOCK =====
        stock_group = QGroupBox("📦 Stock disponible")
        stock_layout = QVBoxLayout()
        self.stock_table = QTableWidget(2, 3)
        self.stock_table.setHorizontalHeaderLabels(["Longueur (mm)", "Coût (€)", "Disponibilité"])
        # Adaptation PyQt6
        self.stock_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.stock_table.setAlternatingRowColors(True)
        self.stock_table.setMinimumHeight(200) 
        self.update_stock_table()
        stock_layout.addWidget(self.stock_table)
        stock_group.setLayout(stock_layout)
        self.main_layout.addWidget(stock_group)

        # ===== TABLES DEMANDES =====
        demand_group = QGroupBox("🔧 Demandes par diamètre")
        demand_layout = QVBoxLayout()
        self.tabs = QTabWidget()
        self.tabs.setMinimumHeight(350) 
        
        # Diamètre 100
        self.tab_100 = QWidget()
        self.layout_100 = QVBoxLayout()
        self.layout_100.setContentsMargins(10, 10, 10, 10)
        self.demand_table_100 = QTableWidget(4, 2)
        self.demand_table_100.setHorizontalHeaderLabels(["Longueur (mm)", "Quantité"])
        # Adaptation PyQt6
        self.demand_table_100.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.demand_table_100.setAlternatingRowColors(True)
        self.update_demand_table_100()
        self.layout_100.addWidget(self.demand_table_100)
        self.tab_100.setLayout(self.layout_100)
        self.tabs.addTab(self.tab_100, "Diamètre 100mm")
        
        # Diamètre 150
        self.tab_150 = QWidget()
        self.layout_150 = QVBoxLayout()
        self.layout_150.setContentsMargins(10, 10, 10, 10)
        self.demand_table_150 = QTableWidget(3, 2)
        self.demand_table_150.setHorizontalHeaderLabels(["Longueur (mm)", "Quantité"])
        # Adaptation PyQt6
        self.demand_table_150.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.demand_table_150.setAlternatingRowColors(True)
        self.update_demand_table_150()
        self.layout_150.addWidget(self.demand_table_150)
        self.tab_150.setLayout(self.layout_150)
        self.tabs.addTab(self.tab_150, "Diamètre 150mm")
        
        demand_layout.addWidget(self.tabs)
        demand_group.setLayout(demand_layout)
        self.main_layout.addWidget(demand_group)

        # ===== BOUTONS =====
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)
        
        self.run_button = QPushButton("▶️  Lancer l'optimisation")
        # Adaptation PyQt6
        self.run_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.run_button.clicked.connect(self.start_solver)
        self.run_button.setMinimumHeight(50)
        self.run_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60; color: white; font-size: 12pt; font-weight: bold; 
                padding: 10px 20px; border-radius: 6px; border: 1px solid #219150;
            }
            QPushButton:hover { background-color: #2ecc71; }
            QPushButton:pressed { background-color: #1e8449; }
            QPushButton:disabled { background-color: #95a5a6; border: 1px solid #7f8c8d; }
        """)
        
        self.reset_button = QPushButton("🔄  Réinitialiser")
        # Adaptation PyQt6
        self.reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_button.clicked.connect(self.reset_data)
        self.reset_button.setMinimumHeight(50)
        self.reset_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c; color: white; font-size: 12pt; font-weight: bold; 
                padding: 10px 20px; border-radius: 6px; border: 1px solid #c0392b;
            }
            QPushButton:hover { background-color: #ff6b6b; }
            QPushButton:pressed { background-color: #c0392b; }
        """)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.reset_button)
        buttons_layout.addWidget(self.run_button)
        self.main_layout.addLayout(buttons_layout)

        # ===== RÉSULTATS & GRAPHIQUE =====
        results_layout = QHBoxLayout()
        
        res_group = QGroupBox("📊 Rapport détaillé")
        res_layout = QVBoxLayout()
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMinimumHeight(300) 
        res_layout.addWidget(self.result_text)
        res_group.setLayout(res_layout)
        
        graph_group = QGroupBox("📈 Visualisation")
        graph_layout = QVBoxLayout()
        self.figure = plt.Figure(figsize=(5, 4))
        self.figure.set_facecolor('#ffffff')
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setMinimumHeight(300)
        graph_layout.addWidget(self.canvas)
        graph_group.setLayout(graph_layout)
        
        results_layout.addWidget(res_group, 4)
        results_layout.addWidget(graph_group, 6)
        
        self.main_layout.addLayout(results_layout)

    # --- Méthodes de mise à jour ---
    def update_stock_table(self):
        num_stocks = self.num_stocks_spin.value()
        self.stock_table.setRowCount(num_stocks)
        labels = [f"Stock {chr(65+i)}" for i in range(num_stocks)]
        self.stock_table.setVerticalHeaderLabels(labels)
        defaults = [("8000", "1.2", "10"), ("12000", "1.8", "6"), ("10000", "1.5", "8"), ("15000", "2.0", "5"),
                    ("6000", "1.0", "12"), ("20000", "2.5", "4"), ("9000", "1.3", "7"), ("11000", "1.6", "9"),
                    ("13000", "1.9", "6"), ("7000", "1.1", "10")]
        
        for i in range(num_stocks):
            for j in range(3):
                if self.stock_table.item(i, j) is None:
                    val = defaults[i%len(defaults)][j]
                    item = QTableWidgetItem(val)
                    # Adaptation PyQt6
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.stock_table.setItem(i, j, item)

    def update_demand_table_100(self):
        num_types = self.num_types_100_spin.value()
        self.demand_table_100.setRowCount(num_types)
        labels = [f"Type {i+1}" for i in range(num_types)]
        self.demand_table_100.setVerticalHeaderLabels(labels)
        defaults = [("3000", "4"), ("2000", "6"), ("1200", "8"), ("700", "10"), ("1500", "5"),
                    ("2500", "7"), ("900", "12"), ("1800", "6"), ("2200", "8"), ("1100", "9"),
                    ("1600", "7"), ("800", "11"), ("2800", "5"), ("1300", "10"), ("1900", "6"),
                    ("1000", "8"), ("2100", "7"), ("1400", "9"), ("2600", "5"), ("1700", "6")]
        for i in range(num_types):
            for j in range(2):
                if self.demand_table_100.item(i, j) is None:
                    val = defaults[i%len(defaults)][j]
                    item = QTableWidgetItem(val)
                    # Adaptation PyQt6
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.demand_table_100.setItem(i, j, item)

    def update_demand_table_150(self):
        num_types = self.num_types_150_spin.value()
        self.demand_table_150.setRowCount(num_types)
        
        offset = self.num_types_100_spin.value()
        
        labels = [f"Type {i + 1 + offset}" for i in range(num_types)] 
        self.demand_table_150.setVerticalHeaderLabels(labels)
        
        defaults = [("2500", "5"), ("1800", "7"), ("600", "8"), ("2200", "6"), ("1500", "9"),
                    ("2800", "5"), ("1200", "10"), ("2000", "7"), ("1600", "8"), ("2400", "6"),
                    ("1000", "11"), ("2100", "7"), ("1700", "9"), ("2300", "6"), ("1400", "10"),
                    ("1900", "8"), ("2600", "5"), ("1100", "12"), ("2700", "6"), ("1300", "9")]
        for i in range(num_types):
            for j in range(2):
                if self.demand_table_150.item(i, j) is None:
                    val = defaults[i%len(defaults)][j]
                    item = QTableWidgetItem(val)
                    # Adaptation PyQt6
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.demand_table_150.setItem(i, j, item)

    def reset_data(self):
        self.num_stocks_spin.setValue(2)
        self.num_types_100_spin.setValue(3) 
        self.num_types_150_spin.setValue(3)
        self.kerf_spin.setValue(5)
        self.update_stock_table()
        self.update_demand_table_100()
        self.update_demand_table_150()
        self.result_text.clear()
        self.figure.clear()
        self.canvas.draw()

    def start_solver(self):
        # ----------------------------------------------------
        # 1. VERIFICATION DE LA COMPLEXITÉ (POP-UP)
        # ----------------------------------------------------
        LIMIT_COMPLEXITY = 7
        if (self.num_stocks_spin.value() >= LIMIT_COMPLEXITY or 
            self.num_types_100_spin.value() >= LIMIT_COMPLEXITY or 
            self.num_types_150_spin.value() >= LIMIT_COMPLEXITY):
            
            # Adaptation PyQt6 pour QMessageBox
            reply = QMessageBox.question(
                self, 
                "Avertissement de performance",
                "Le nombre de types ou de stocks est élevé (>= 7).\n"
                "Le calcul risque d'être très long ou de saturer la mémoire (complexité exponentielle).\n\n"
                "Voulez-vous continuer ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                self.result_text.setText("⚠️ Optimisation annulée par l'utilisateur (complexité trop élevée).")
                return

        try:
            # ----------------------------------------------------
            # 2. VALIDATION ET RECUPERATION DONNEES
            # ----------------------------------------------------
            stock_data = []
            kerf = 0.0
            demand_100 = []
            demand_150 = []
            
            errors_log = {}

            # --- Validation Stock (Critique: Si erreur, on ne peut rien faire) ---
            try:
                num_stocks = self.stock_table.rowCount()
                for i in range(num_stocks):
                    l_item = self.stock_table.item(i, 0)
                    c_item = self.stock_table.item(i, 1)
                    a_item = self.stock_table.item(i, 2)
                    
                    if not l_item or not c_item or not a_item:
                         raise ValueError(f"Stock {chr(65+i)} : Données manquantes")

                    length = float(l_item.text())
                    cost = float(c_item.text())
                    avail = float(a_item.text())
                    
                    if length <= 0: raise ValueError(f"Stock {chr(65+i)} : La longueur doit être > 0")
                    if cost < 0: raise ValueError(f"Stock {chr(65+i)} : Le coût ne peut pas être négatif")
                    if avail < 0: raise ValueError(f"Stock {chr(65+i)} : La disponibilité ne peut pas être négative")
                    
                    stock_data.append((length, cost, avail))
            except ValueError as ve:
                self.result_text.setText(f"⛔ ERREUR CRITIQUE STOCK :\n{str(ve)}")
                return # Arrêt total si stock invalide

            # --- Validation Kerf ---
            kerf = self.kerf_spin.value()
            if kerf < 0:
                self.result_text.setText("⛔ ERREUR CRITIQUE : Le Kerf ne peut pas être négatif")
                return

            # --- Validation DEMANDES Ø100 (Indépendant) ---
            try:
                num_types_100 = self.demand_table_100.rowCount()
                for i in range(num_types_100):
                    l_item = self.demand_table_100.item(i, 0)
                    q_item = self.demand_table_100.item(i, 1)
                    if not l_item or not q_item: raise ValueError(f"Ligne {i+1} : Données manquantes")

                    length = float(l_item.text())
                    qty = int(q_item.text())
                    
                    if length <= 0: raise ValueError(f"Ligne {i+1} : Longueur doit être > 0")
                    if qty < 0: raise ValueError(f"Ligne {i+1} : Quantité ne peut pas être négative")
                    
                    demand_100.append((length, qty, f"T{i+1}"))
            except ValueError as ve:
                errors_log["diameter_100"] = f"Erreur Saisie Ø100: {str(ve)}"
                demand_100 = [] # On vide pour ne pas planter le thread

            # --- Validation DEMANDES Ø150 (Indépendant) ---
            try:
                num_types_150 = self.demand_table_150.rowCount()
                offset = self.num_types_100_spin.value()
                for i in range(num_types_150):
                    l_item = self.demand_table_150.item(i, 0)
                    q_item = self.demand_table_150.item(i, 1)
                    if not l_item or not q_item: raise ValueError(f"Ligne {i+1} : Données manquantes")

                    length = float(l_item.text())
                    qty = int(q_item.text())
                    
                    if length <= 0: raise ValueError(f"Ligne {i+1} : Longueur doit être > 0")
                    if qty < 0: raise ValueError(f"Ligne {i+1} : Quantité ne peut pas être négative")
                    
                    demand_150.append((length, qty, f"T{i+1+offset}"))
            except ValueError as ve:
                errors_log["diameter_150"] = f"Erreur Saisie Ø150: {str(ve)}"
                demand_150 = [] # On vide

            # Si tout est invalide
            if "diameter_100" in errors_log and "diameter_150" in errors_log:
                 self.result_text.setText("⛔ ERREUR : Les deux tableaux de demande contiennent des erreurs invalides.\n" 
                                          f"Ø100: {errors_log['diameter_100']}\nØ150: {errors_log['diameter_150']}")
                 return

            # Lancement du calcul
            self.thread = SolverThread(stock_data, demand_100, demand_150, kerf, errors_pre_validation=errors_log)
            self.thread.finished.connect(self.show_results)
            self.run_button.setEnabled(False)
            self.run_button.setText("⏳ Calcul en cours...")
            self.result_text.setText("⏳ Calcul en cours...\n" + 
                                     ("⚠️ Erreur détectée sur Ø100, seul Ø150 sera calculé...\n" if "diameter_100" in errors_log else "") +
                                     ("⚠️ Erreur détectée sur Ø150, seul Ø100 sera calculé...\n" if "diameter_150" in errors_log else "") +
                                     "Génération des patterns et résolution...")
            self.thread.start()
            
        except Exception as e:
            self.result_text.setText(f"❌ Erreur inattendue au lancement: {str(e)}")
            self.run_button.setEnabled(True)

    def show_results(self, results):
        self.run_button.setEnabled(True)
        self.run_button.setText("▶️  Lancer l'optimisation")
        
        if "error" in results and len(results) == 1: # Erreur globale
            self.result_text.setText(f"❌ Erreur: {results['error']}")
            return

        text = "=" * 60 + "\n📊 RÉSULTATS D'OPTIMISATION\n" + "=" * 60 + "\n\n"
        total_cost = 0
        
        for diameter in [100, 150]:
            key = f"diameter_{diameter}"
            res = results.get(key)
            
            text += f"🔧 DIAMÈTRE {diameter}mm\n" + "-" * 60 + "\n"
            
            # Gestion d'erreur spécifique au diamètre
            if not res:
                text += "❌ Erreur interne : Pas de résultat retourné.\n\n"
                continue
            
            if "error" in res:
                text += f"❌ Impossible de calculer : {res['error']}\n\n"
                continue

            if res.get("infeasible"):
                text += "❌ Problème infaisable (stock insuffisant)\n\n"
                continue
            if res['cost'] == 0:
                text += "ℹ️  Aucune demande ou demande vide pour ce diamètre\n\n"
                continue
                
            text += f"💰 Coût: {res['cost']:.2f} €\n\n"
            text += "📦 Utilisation du stock:\n"
            for stock_name, qty in sorted(res['stock_used'].items()):
                if qty > 0.01: text += f"  • {stock_name}: {qty:.2f} barres\n"
            text += f"\n🔢 Patterns générés: " + ", ".join([f"{k}={v}" for k, v in sorted(res['num_patterns'].items())]) + "\n\n"
            text += "✂️  Patterns de découpe utilisés:\n"
            for p in res['patterns']:
                text += f"  • {p['stock']}: {p['count']:.2f} barres → [{p['pattern']}]\n"
            text += "\n"
            total_cost += res['cost']
            
        text += "=" * 60 + "\n" + f"💵 COÛT TOTAL (Calculé): {total_cost:.2f} €\n" + "=" * 60
        self.result_text.setText(text)
        
        self.figure.clear()
        num_stocks = self.stock_table.rowCount()
        colors = plt.cm.Set3(range(num_stocks))
        ax1 = self.figure.add_subplot(121)
        ax2 = self.figure.add_subplot(122)
        
        for ax, diameter in zip([ax1, ax2], [100, 150]):
            key = f"diameter_{diameter}"
            res = results.get(key)
            
            # Vérification de validité avant traçage
            if res and "error" not in res and not res.get("infeasible") and res['cost'] > 0:
                stock_names = sorted(res['stock_used'].keys())
                stock_values = [res['stock_used'][name] for name in stock_names]
                ax.bar(stock_names, stock_values, color=colors[:len(stock_names)], edgecolor='black', alpha=0.8)
                ax.set_ylabel("Barres utilisées", fontsize=9)
                ax.set_title(f"Ø{diameter}mm", fontsize=10, fontweight='bold')
                ax.grid(axis='y', alpha=0.3, linestyle='--')
                ax.tick_params(axis='both', which='major', labelsize=8)
            else:
                msg = "Erreur" if res and "error" in res else "Pas de données"
                ax.text(0.5, 0.5, msg, ha='center', va='center', color='red' if msg=="Erreur" else 'black')
                ax.axis('off')
                
        self.figure.tight_layout(pad=2.0)
        self.canvas.draw()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CuttingStockApp()
    window.showMaximized() # Modification : Ouverture en plein écran
    # Adaptation PyQt6
    sys.exit(app.exec())