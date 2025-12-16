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
import math

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
def generate_patterns(stock_length, pieces, kerf=5):#pieces = (longueur, quantité, nom)
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
# Thread Solver (Adapté Dynamique)
# ======================
class SolverThread(QThread):
    finished = pyqtSignal(dict) #signal émis à la fin du calcul avec les résultats
    
    # MODIFICATION: Accepte une liste générique de demandes
    def __init__(self, stock_data, demands_list, kerf, errors_pre_validation=None):
        super().__init__() 
        self.stock_data = stock_data
        self.demands_list = demands_list # Liste de tuples: (diam_value, [pieces])
        self.kerf = kerf
        self.errors_pre = errors_pre_validation if errors_pre_validation else {}

    def run(self):
        results = {}
        
        # Copie des erreurs de pré-validation
        for k, v in self.errors_pre.items():
            results[k] = {"error": v}

        # Boucle sur chaque configuration de diamètre demandée
        for diam_val, demands in self.demands_list:
            key = f"diameter_{diam_val}"
            
            # Si déjà en erreur, on saute
            if key in results: continue

            try:
                results[key] = self.solve_diameter(diam_val, demands)
            except Exception as e:
                results[key] = {"error": str(e)}

        self.finished.emit(results)

    def solve_diameter(self, diameter, demands):#résout le problème de cutting stock pour un diamètre donné
        if not demands or all(qty == 0 for _, qty, _ in demands):
            return {"cost": 0, "patterns": [], "stock_used": {}, "num_patterns": {}}
        
        model = gp.Model(f"CuttingStock_D{diameter}")
        model.Params.OutputFlag = 0
        all_patterns = {}
        x_vars = {}
        
        for stock_idx, (length, cost, avail) in enumerate(self.stock_data):
            stock_name = f"Stock {chr(65+stock_idx)}"
            patterns = generate_patterns(length, demands, self.kerf)
            all_patterns[stock_name] = patterns
            x_vars[stock_name] = {}
            for p_idx, pattern in enumerate(patterns):
                x_vars[stock_name][p_idx] = model.addVar(vtype=GRB.CONTINUOUS, name=f"x_{stock_name}_{p_idx}")
        
        for piece_idx, (length, qty, name) in enumerate(demands):
            demand_expr = gp.LinExpr()
            for stock_name in all_patterns:
                for p_idx, pattern in enumerate(all_patterns[stock_name]):
                    if piece_idx in pattern:
                        demand_expr += pattern[piece_idx] * x_vars[stock_name][p_idx]
            model.addConstr(demand_expr >= qty, f"Demand_{name}")
        
        stock_exprs = {}
        for stock_idx, (length, cost, avail) in enumerate(self.stock_data):
            stock_name = f"Stock {chr(65+stock_idx)}"
            stock_expr = gp.quicksum(x_vars[stock_name][p] for p in x_vars[stock_name])
            model.addConstr(stock_expr <= avail, f"Stock_{stock_name}")
            stock_exprs[stock_name] = stock_expr
            
        cost_expr = gp.LinExpr()
        for stock_idx, (length, cost, avail) in enumerate(self.stock_data):
            stock_name = f"Stock {chr(65+stock_idx)}"
            cost_expr += cost * stock_exprs[stock_name]
            
        model.setObjective(cost_expr, GRB.MINIMIZE)
        model.optimize()
        
        if model.status == GRB.OPTIMAL:
            used_patterns = []
            stock_used = {}
            num_patterns = {}
            for stock_idx, (length, cost, avail) in enumerate(self.stock_data):
                stock_name = f"Stock {chr(65+stock_idx)}"
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
        
        # Stockage des références aux widgets dynamiques des diamètres
        self.tab_widgets_list = [] # Liste de tuples (spin_diam, spin_nb_types, table_widget)

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
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(title)

        # ===== CONFIGURATION =====
        config_group = QGroupBox("⚙️ Paramètres Généraux")
        config_layout = QHBoxLayout()
        config_layout.setSpacing(20)
        
        # STOCK
        l1 = QLabel("Types de stock:")
        self.num_stocks_spin = QSpinBox()
        self.num_stocks_spin.setRange(1, 10)
        self.num_stocks_spin.setValue(2)
        self.num_stocks_spin.setFixedWidth(80)
        self.num_stocks_spin.valueChanged.connect(self.update_stock_table)
        
        # KERF
        l2 = QLabel("Trait de scie (Kerf mm):")
        self.kerf_spin = QDoubleSpinBox()
        self.kerf_spin.setRange(0, 50)
        self.kerf_spin.setDecimals(2)
        self.kerf_spin.setSingleStep(0.1)
        self.kerf_spin.setValue(5.0)
        self.kerf_spin.setFixedWidth(80)

        # NB DIAMETRES (MODIFICATION)
        l3 = QLabel("Nombre de diamètres différents:")
        self.num_diams_spin = QSpinBox()
        self.num_diams_spin.setRange(1, 10)
        self.num_diams_spin.setValue(2) # Default
        self.num_diams_spin.setFixedWidth(80)
        self.num_diams_spin.valueChanged.connect(self.rebuild_demand_tabs)

        for widget in [l1, self.num_stocks_spin, l2, self.kerf_spin, l3, self.num_diams_spin]:
            config_layout.addWidget(widget)
        config_layout.addStretch()
        
        config_group.setLayout(config_layout)
        self.main_layout.addWidget(config_group)

        # ===== TABLE STOCK =====
        stock_group = QGroupBox("📦 Stock disponible")
        stock_layout = QVBoxLayout()
        self.stock_table = QTableWidget(2, 3)
        self.stock_table.setHorizontalHeaderLabels(["Longueur (mm)", "Coût (€)", "Disponibilité"])
        self.stock_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.stock_table.setAlternatingRowColors(True)
        self.stock_table.setMinimumHeight(200) 
        self.update_stock_table()
        stock_layout.addWidget(self.stock_table)
        stock_group.setLayout(stock_layout)
        self.main_layout.addWidget(stock_group)

        # ===== TABLES DEMANDES (DYNAMIQUE) =====
        demand_group = QGroupBox("🔧 Demandes par diamètre")
        demand_layout = QVBoxLayout()
        self.tabs = QTabWidget()
        self.tabs.setMinimumHeight(400) 
        
        # Initialisation des tabs
        self.rebuild_demand_tabs()
        
        demand_layout.addWidget(self.tabs)
        demand_group.setLayout(demand_layout)
        self.main_layout.addWidget(demand_group)

        # ===== BOUTONS =====
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)
        
        self.run_button = QPushButton("▶️  Lancer l'optimisation")
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
        self.figure = plt.Figure(figsize=(8, 4)) # Un peu plus large
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
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.stock_table.setItem(i, j, item)

    # --- NOUVELLE METHODE DYNAMIQUE ---
    def rebuild_demand_tabs(self):
        # Sauvegarde des données actuelles si possible ? 
        # Pour simplifier ici, on réinitialise la structure quand on change le nombre
        # mais on pourrait implémenter une persistance.
        
        num_diams = self.num_diams_spin.value()
        self.tabs.clear()
        self.tab_widgets_list = []

        # Valeurs par défaut pour démo
        defaults_data = [
            ("2500", "5"), ("1800", "7"), ("600", "8"), ("2200", "6"), 
            ("1500", "9"), ("2800", "5"), ("1200", "10"), ("2000", "7")
        ]

        for k in range(num_diams):
            tab_widget = QWidget()
            layout = QVBoxLayout()
            
            # Sous-config pour ce diamètre
            top_layout = QHBoxLayout()
            
            l_diam = QLabel("Diamètre (mm):")
            spin_diam = QSpinBox()
            spin_diam.setRange(1, 10000)
            spin_diam.setValue(100 + k*50) # Ex: 100, 150, 200...
            spin_diam.setFixedWidth(80)
            
            l_qty = QLabel("Nombre de types:")
            spin_types = QSpinBox()
            spin_types.setRange(1, 20)
            spin_types.setValue(3)
            spin_types.setFixedWidth(80)
            
            top_layout.addWidget(l_diam)
            top_layout.addWidget(spin_diam)
            top_layout.addSpacing(20)
            top_layout.addWidget(l_qty)
            top_layout.addWidget(spin_types)
            top_layout.addStretch()
            
            layout.addLayout(top_layout)
            
            # Table pour ce diamètre
            table = QTableWidget(3, 2)
            table.setHorizontalHeaderLabels(["Longueur (mm)", "Quantité"])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            table.setAlternatingRowColors(True)
            
            # Remplissage par défaut
            for i in range(3):
                val_len, val_qty = defaults_data[(k*3 + i) % len(defaults_data)]
                item_len = QTableWidgetItem(val_len)
                item_qty = QTableWidgetItem(val_qty)
                item_len.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item_qty.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(i, 0, item_len)
                table.setItem(i, 1, item_qty)

            # Connexion changement nbre types
            # On utilise une fonction lambda avec valeur par défaut pour capturer la variable 'table'
            spin_types.valueChanged.connect(lambda val, t=table: self.update_dynamic_table_rows(t, val))

            layout.addWidget(table)
            tab_widget.setLayout(layout)
            
            title = f"Diamètre #{k+1}"
            self.tabs.addTab(tab_widget, title)
            
            # On stocke les références
            self.tab_widgets_list.append((spin_diam, spin_types, table))
            
            # Mise à jour titre onglet quand diam change
            spin_diam.valueChanged.connect(lambda val, idx=k: self.tabs.setTabText(idx, f"Diamètre {val}mm"))
            self.tabs.setTabText(k, f"Diamètre {spin_diam.value()}mm")

    def update_dynamic_table_rows(self, table, num_rows):
        table.setRowCount(num_rows)
        # Remplissage auto si vide
        defaults_data = [("2000", "5"), ("1500", "10"), ("1000", "8")]
        for i in range(num_rows):
            if table.item(i, 0) is None:
                 val_len, val_qty = defaults_data[i % len(defaults_data)]
                 item_len = QTableWidgetItem(val_len)
                 item_qty = QTableWidgetItem(val_qty)
                 item_len.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                 item_qty.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                 table.setItem(i, 0, item_len)
                 table.setItem(i, 1, item_qty)
        # Etiquette lignes
        labels = [f"Type {i+1}" for i in range(num_rows)]
        table.setVerticalHeaderLabels(labels)

    def reset_data(self):
        self.num_stocks_spin.setValue(2)
        self.num_diams_spin.setValue(2) # Reset nb diametres
        self.kerf_spin.setValue(5)
        self.update_stock_table()
        self.rebuild_demand_tabs() # Reset tabs
        self.result_text.clear()
        self.figure.clear()
        self.canvas.draw()

    def start_solver(self):
        # 1. VERIFICATION COMPLEXITÉ
        total_types = sum([w[1].value() for w in self.tab_widgets_list])
        if (self.num_stocks_spin.value() >= 7 or total_types >= 15):
            reply = QMessageBox.question(
                self, "Avertissement",
                "Le nombre de variables est élevé. Continuer ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                self.result_text.setText("⚠️ Annulé.")
                return

        try:
            # 2. RECUPERATION DONNEES
            stock_data = []
            kerf = self.kerf_spin.value()
            if kerf < 0: raise ValueError("Kerf négatif")
            
            # Stock
            try:
                for i in range(self.stock_table.rowCount()):
                    l_item = self.stock_table.item(i, 0)
                    c_item = self.stock_table.item(i, 1)
                    a_item = self.stock_table.item(i, 2)
                    if not l_item or not c_item or not a_item: raise ValueError(f"Stock {chr(65+i)} incomplet")
                    stock_data.append((float(l_item.text()), float(c_item.text()), float(a_item.text())))
            except ValueError as ve:
                self.result_text.setText(f"⛔ ERREUR STOCK: {ve}")
                return

            # Demandes Dynamiques
            demands_list = [] # Liste de (diam_val, pieces_list)
            errors_log = {}

            for idx, (spin_diam, spin_types, table) in enumerate(self.tab_widgets_list):
                diam_val = spin_diam.value()
                pieces = []
                try:
                    for r in range(table.rowCount()):
                        l_it = table.item(r, 0)
                        q_it = table.item(r, 1)
                        if not l_it or not q_it: raise ValueError("Vide")
                        l_val = float(l_it.text())
                        q_val = int(q_it.text())
                        if l_val <= 0 or q_val < 0: raise ValueError("Valeurs invalides")
                        pieces.append((l_val, q_val, f"T{r+1}"))
                    
                    demands_list.append((diam_val, pieces))
                except ValueError as ve:
                    key = f"diameter_{diam_val}"
                    # Si doublon de diametre, on suffixe pour le log
                    if key in errors_log: key += f"_idx{idx}"
                    errors_log[key] = f"Erreur Tab {idx+1} (Ø{diam_val}): {str(ve)}"

            # Lancement
            self.thread = SolverThread(stock_data, demands_list, kerf, errors_pre_validation=errors_log)
            self.thread.finished.connect(self.show_results)
            self.run_button.setEnabled(False)
            self.run_button.setText("⏳ Calcul en cours...")
            self.result_text.setText("⏳ Optimisation de tous les diamètres configurés...")
            self.thread.start()
            
        except Exception as e:
            self.result_text.setText(f"❌ Erreur inattendue: {str(e)}")
            self.run_button.setEnabled(True)

    def show_results(self, results):
        self.run_button.setEnabled(True)
        self.run_button.setText("▶️  Lancer l'optimisation")
        
        text = "=" * 60 + "\n📊 RÉSULTATS D'OPTIMISATION\n" + "=" * 60 + "\n\n"
        total_global_cost = 0
        
        # Récupération triée des clés (diameter_100, diameter_200...)
        sorted_keys = sorted(results.keys(), key=lambda x: int(x.split('_')[1]) if '_' in x and x.split('_')[1].isdigit() else 0)

        valid_results_count = 0

        for key in sorted_keys:
            res = results[key]
            diam_display = key.replace("diameter_", "")
            
            text += f"🔧 DIAMÈTRE {diam_display}mm\n" + "-" * 60 + "\n"
            
            if "error" in res:
                text += f"❌ Erreur : {res['error']}\n\n"
                continue
            if res.get("infeasible"):
                text += "❌ Impossible (Stock insuffisant)\n\n"
                continue
            if res['cost'] == 0:
                text += "ℹ️  Pas de demande.\n\n"
                continue
            
            valid_results_count += 1
            text += f"💰 Coût: {res['cost']:.2f} €\n"
            text += "📦 Stock utilisé:\n"
            for stock_name, qty in sorted(res['stock_used'].items()):
                if qty > 0.01: text += f"  • {stock_name}: {qty:.2f} barres\n"
            
            text += "✂️  Détail découpe:\n"
            for p in res['patterns']:
                text += f"  • {p['stock']} ({p['count']:.1f}): [{p['pattern']}]\n"
            text += "\n"
            total_global_cost += res['cost']

        text += "=" * 60 + "\n" + f"💵 COÛT TOTAL GLOBAL: {total_global_cost:.2f} €\n" + "=" * 60
        self.result_text.setText(text)
        
        # --- Graphiques Dynamiques ---
        self.figure.clear()
        if valid_results_count > 0:
            # On crée autant de subplots que de résultats valides
            # Dispositions simple : tout sur 1 ligne
            cols = valid_results_count
            current_col = 1
            
            num_stocks = self.stock_table.rowCount()
            colors = plt.cm.Set3(range(num_stocks))

            for key in sorted_keys:
                res = results[key]
                if "error" in res or res.get("infeasible") or res['cost'] == 0:
                    continue
                
                diam_display = key.replace("diameter_", "")
                ax = self.figure.add_subplot(1, cols, current_col)
                
                stock_names = sorted(res['stock_used'].keys())
                stock_values = [res['stock_used'][name] for name in stock_names]
                
                ax.bar(stock_names, stock_values, color=colors[:len(stock_names)], edgecolor='black', alpha=0.8)
                ax.set_title(f"Ø{diam_display}mm", fontsize=10, fontweight='bold')
                ax.grid(axis='y', alpha=0.3)
                
                current_col += 1
        
        self.figure.tight_layout()
        self.canvas.draw()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CuttingStockApp()
    window.showMaximized()
    sys.exit(app.exec())