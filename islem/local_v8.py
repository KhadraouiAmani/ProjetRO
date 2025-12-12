import sys
import random
import math
import csv
import os
import numpy as np
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QMessageBox, 
                             QProgressBar, QFormLayout, QLineEdit, QGroupBox, 
                             QFileDialog, QTabWidget, QTextEdit, QRadioButton, QFrame, QSplitter)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QAction

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
import matplotlib.image as mpimg 

import gurobipy as gp
from gurobipy import GRB

# =============================================================================
# WORKER (Mathematical Logic - Unchanged)
# =============================================================================
class SolverWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    log_signal = pyqtSignal(str)
    
    def __init__(self, data):
        super().__init__()
        self.data = data 
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        try:
            self.log_signal.emit("--- Initialisation ---")
            sites = self.data['sites']
            districts = self.data['districts']
            techs = self.data['techs']
            budget = self.data['budget']
            
            num_sites = len(sites); num_dist = len(districts); num_techs = len(techs)

            # --- GEOGRAPHIC CHECK ---
            self.log_signal.emit("Vérification des distances...")
            a = {} 
            possible_connections = 0
            
            for i, d in enumerate(districts):
                if not self._is_running: return
                for j, s in enumerate(sites):
                    dist = math.sqrt((d['x']-s['x'])**2 + (d['y']-s['y'])**2)
                    for k, t in enumerate(techs):
                        if dist <= t['range']: 
                            a[(i,j,k)] = 1
                            possible_connections += 1
                        else: 
                            a[(i,j,k)] = 0
            
            if possible_connections == 0:
                self.error.emit("ERREUR GÉOGRAPHIQUE : Aucun client n'est à portée des sites.\n- Vérifiez l'échelle (km).\n- Vérifiez que vos sites ne sont pas à 0,0 et vos clients à 1000,1000.")
                return

            self.log_signal.emit(f"Connexions possibles : {possible_connections}")

            # --- GUROBI MODEL ---
            m = gp.Model("MCLP_5G_Continuous")
            m.setParam('OutputFlag', 0) 
            
            y = m.addVars(num_sites, num_techs, vtype=GRB.BINARY, name="y")
            x = m.addVars(num_dist, num_sites, vtype=GRB.CONTINUOUS, lb=0.0, ub=1.0, name="x")

            obj = gp.quicksum(districts[i]['demand'] * x[i,j] for i in range(num_dist) for j in range(num_sites))
            m.setObjective(obj, GRB.MAXIMIZE)

            # 1. Budget
            m.addConstr(gp.quicksum(techs[k]['cost'] * y[j,k] for j in range(num_sites) for k in range(num_techs)) <= budget, "Budget")
            
            # 2. Exclusivity
            for j in range(num_sites):
                m.addConstr(gp.quicksum(y[j,k] for k in range(num_techs)) <= 1, f"Excl_{j}")

            # 3. Coverage
            for i in range(num_dist):
                for j in range(num_sites):
                    m.addConstr(x[i,j] <= gp.quicksum(a.get((i,j,k), 0) * y[j,k] for k in range(num_techs)))

            # 4. Unicity
            for i in range(num_dist):
                m.addConstr(gp.quicksum(x[i,j] for j in range(num_sites)) <= 1.0)

            # 5. Capacity
            for j in range(num_sites):
                m.addConstr(
                    gp.quicksum(districts[i]['demand'] * x[i,j] for i in range(num_dist)) <= 
                    gp.quicksum(techs[k]['cap'] * y[j,k] for k in range(num_techs))
                )

            def my_callback(model, where):
                if not self._is_running: model.terminate()

            self.log_signal.emit("Optimisation en cours...")
            m.optimize(my_callback)

            if not self._is_running:
                self.error.emit("Arrêt demandé par l'utilisateur.")
                return

            if m.Status == GRB.OPTIMAL:
                self.log_signal.emit(f"✅ Optimal ! Clients servis : {int(m.ObjVal)}")
                res = {
                    'status': 'Optimal',
                    'obj_val': m.ObjVal,
                    'total_demand': sum(d['demand'] for d in districts),
                    'budget_used': 0,
                    'installations': [],
                    'links': []
                }
                
                for j in range(num_sites):
                    active_tech = None
                    for k in range(num_techs):
                        if y[j,k].X > 0.5: active_tech = k; break
                    
                    if active_tech is not None:
                        load = sum(districts[i]['demand'] * x[i,j].X for i in range(num_dist))
                        t = techs[active_tech]
                        res['installations'].append({
                            'site_id': sites[j]['id'], 'x': sites[j]['x'], 'y': sites[j]['y'],
                            'tech_name': t['name'], 'cost': t['cost'], 
                            'load': load, 'capacity': t['cap'], 'range': t['range']
                        })
                        res['budget_used'] += t['cost']

                for i in range(num_dist):
                    for j in range(num_sites):
                        if x[i,j].X > 0.01: 
                            res['links'].append((i, j, x[i,j].X))
                
                self.finished.emit(res)
            elif m.Status == GRB.INFEASIBLE:
                self.error.emit("❌ INFASIAIBLE : Budget trop faible pour installer la moindre antenne.")
            else:
                self.error.emit(f"Statut Gurobi : {m.Status}")

        except Exception as e:
            self.error.emit(f"Erreur interne : {str(e)}")

# =============================================================================
# VISUALISATION
# =============================================================================
class MplCanvas(FigureCanvasQTAgg):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        self.fig.patch.set_facecolor('#f0f0f0')
        super(MplCanvas, self).__init__(self.fig)

# =============================================================================
# MAIN WINDOW
# =============================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("5G Master Planner v8.0 (Editable & Legend)")
        self.setGeometry(50, 50, 1600, 900)
        
        self.current_mode = "random" 
        self.csv_sites_path = None
        self.csv_districts_path = None
        
        # Données
        self.sites = []
        self.districts = []
        self.techs = [
            {'name': 'Small Cell', 'cost': 3000, 'cap': 800, 'range': 15},
            {'name': 'Macro Cell', 'cost': 12000, 'cap': 3000, 'range': 40},
            {'name': 'High Tower', 'cost': 35000, 'cap': 8000, 'range': 90}
        ]
        self.budget = 80000 

        self.initUI()
        self.generate_random_data()

    def initUI(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # --- SIDEBAR ---
        sidebar = QWidget()
        sidebar.setFixedWidth(350)
        sidebar.setStyleSheet("background-color: #2c3e50; color: white;")
        side_layout = QVBoxLayout(sidebar)

        lbl_title = QLabel("CONFIGURATION")
        lbl_title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side_layout.addWidget(lbl_title)

        # Paramètres
        grp_in = QGroupBox("1. Paramètres")
        grp_in.setStyleSheet("QGroupBox { border: 1px solid #bdc3c7; margin-top: 10px; } QGroupBox::title { color: #ecf0f1; }")
        form = QFormLayout()
        
        self.inp_nb_sites = QLineEdit("20"); self.inp_nb_sites.setStyleSheet("color: white;")
        self.inp_nb_dist = QLineEdit("80"); self.inp_nb_dist.setStyleSheet("color: white;")
        self.inp_size = QLineEdit("200"); self.inp_size.setStyleSheet("color: white;")
        self.inp_budget = QLineEdit("80000"); self.inp_budget.setStyleSheet("color: white; font-weight: bold;")
        
        self.inp_nb_sites.returnPressed.connect(self.refresh_data)
        self.inp_nb_dist.returnPressed.connect(self.refresh_data)
        self.inp_size.returnPressed.connect(self.refresh_data)
        self.inp_budget.returnPressed.connect(self.refresh_data)

        form.addRow("Nb Sites:", self.inp_nb_sites)
        form.addRow("Nb Demandes:", self.inp_nb_dist)
        form.addRow("Taille (km):", self.inp_size)
        form.addRow("Budget (€):", self.inp_budget)
        
        btn_refresh = QPushButton("🔄 Actualiser & Générer")
        btn_refresh.setStyleSheet("background-color: #3498db; color: white; padding: 5px;")
        btn_refresh.clicked.connect(self.refresh_data)
        form.addRow(btn_refresh)
        
        grp_in.setLayout(form)
        side_layout.addWidget(grp_in)

        # Source Données
        grp_gen = QGroupBox("2. Sources")
        v_gen = QVBoxLayout()
        btn_rand = QPushButton("Aléatoire"); btn_rand.setStyleSheet("background-color: #e67e22;"); btn_rand.clicked.connect(self.generate_random_data)
        btn_grid = QPushButton("Grille"); btn_grid.setStyleSheet("background-color: #d35400;"); btn_grid.clicked.connect(self.generate_grid_data)
        btn_csv = QPushButton("Import CSV"); btn_csv.setStyleSheet("background-color: #8e44ad;"); btn_csv.clicked.connect(self.load_csv_real)
        v_gen.addWidget(btn_rand); v_gen.addWidget(btn_grid); v_gen.addWidget(btn_csv)
        grp_gen.setLayout(v_gen)
        side_layout.addWidget(grp_gen)

        side_layout.addStretch()

        # Actions
        self.btn_solve = QPushButton("LANCER OPTIMISATION")
        self.btn_solve.setFixedHeight(50)
        self.btn_solve.setStyleSheet("background-color: #27ae60; font-weight: bold; font-size: 14px;")
        self.btn_solve.clicked.connect(self.start_optimization)
        side_layout.addWidget(self.btn_solve)

        self.btn_stop = QPushButton("⛔ STOP")
        self.btn_stop.setFixedHeight(50)
        self.btn_stop.setStyleSheet("background-color: #c0392b; font-weight: bold; font-size: 14px; color: yellow;")
        self.btn_stop.clicked.connect(self.stop_optimization)
        self.btn_stop.setVisible(False)
        side_layout.addWidget(self.btn_stop)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFixedHeight(120)
        self.log_box.setStyleSheet("background-color: #34495e; color: white; font-size: 9pt;")
        side_layout.addWidget(self.log_box)

        main_layout.addWidget(sidebar)

        # --- CENTER ---
        self.tabs = QTabWidget()
        
        # Tab 1: Données
        tab_data = QWidget(); v_data = QVBoxLayout(tab_data)
        splitter_tables = QSplitter(Qt.Orientation.Horizontal)
        
        self.tbl_sites = self.create_table(["ID", "X", "Y"])
        self.tbl_dist = self.create_table(["ID", "X", "Y", "Demande"])
        self.tbl_techs = self.create_table(["Type", "Coût", "Cap", "Rayon"])
        
        splitter_tables.addWidget(self.create_group("Sites (Editable)", self.tbl_sites))
        splitter_tables.addWidget(self.create_group("Demandes (Editable)", self.tbl_dist))
        splitter_tables.addWidget(self.create_group("Technologies (Editable)", self.tbl_techs))
        
        v_data.addWidget(splitter_tables)
        self.tabs.addTab(tab_data, "1. Données")

        # Tab 2: Carte
        tab_map = QWidget(); v_map = QVBoxLayout(tab_map)
        h_tools = QHBoxLayout()
        self.radio_std = QRadioButton("Standard"); self.radio_sat = QRadioButton("Satellite")
        self.radio_std.setChecked(True)
        self.radio_std.toggled.connect(self.refresh_map_style)
        self.radio_sat.toggled.connect(self.refresh_map_style)
        h_tools.addWidget(QLabel("Vue:")); h_tools.addWidget(self.radio_std); h_tools.addWidget(self.radio_sat); h_tools.addStretch()
        v_map.addLayout(h_tools)
        self.canvas = MplCanvas(self, width=10, height=8, dpi=100)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        v_map.addWidget(self.toolbar); v_map.addWidget(self.canvas)
        self.tabs.addTab(tab_map, "2. Carte Interactive")

        # Tab 3: Résultats
        tab_res = QWidget(); v_res = QVBoxLayout(tab_res)
        
        # Bouton Export
        self.btn_export = QPushButton("💾 Exporter Résultats (CSV)")
        self.btn_export.clicked.connect(self.export_results_csv)
        self.btn_export.setStyleSheet("background-color: #3498db; color: white; padding: 5px;")
        v_res.addWidget(self.btn_export)

        self.tbl_res = self.create_table(["Site", "Loc", "Tech", "Charge", "Coût", "Rayon"])
        self.tbl_res.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        v_res.addWidget(QLabel("Résultats Optimisés :"))
        v_res.addWidget(self.tbl_res)
        self.lbl_metrics = QLabel("...")
        self.lbl_metrics.setStyleSheet("font-size: 12pt; font-weight: bold; padding: 10px;")
        v_res.addWidget(self.lbl_metrics)
        self.tabs.addTab(tab_res, "3. Résultats")

        main_layout.addWidget(self.tabs)

    # --- HELPERS ---
    def create_table(self, h):
        t = QTableWidget(); t.setColumnCount(len(h)); t.setHorizontalHeaderLabels(h); return t
    def create_group(self, t, w):
        g = QGroupBox(t); l = QVBoxLayout(); l.addWidget(w); g.setLayout(l); return g
    def log(self, m):
        self.log_box.append(f"> {m}"); sb = self.log_box.verticalScrollBar(); sb.setValue(sb.maximum())

    def update_tables(self):
        # Cette fonction met à jour l'affichage, mais l'utilisateur peut ensuite modifier les cases
        self.tbl_sites.setRowCount(len(self.sites))
        for r, s in enumerate(self.sites):
            self.tbl_sites.setItem(r,0,QTableWidgetItem(str(s['id']))); self.tbl_sites.setItem(r,1,QTableWidgetItem(f"{s['x']:.0f}")); self.tbl_sites.setItem(r,2,QTableWidgetItem(f"{s['y']:.0f}"))
        self.tbl_dist.setRowCount(len(self.districts))
        for r, d in enumerate(self.districts):
            self.tbl_dist.setItem(r,0,QTableWidgetItem(str(d['id']))); self.tbl_dist.setItem(r,1,QTableWidgetItem(f"{d['x']:.0f}")); self.tbl_dist.setItem(r,2,QTableWidgetItem(f"{d['y']:.0f}")); self.tbl_dist.setItem(r,3,QTableWidgetItem(str(d['demand'])))
        self.tbl_techs.setRowCount(len(self.techs))
        for r, t in enumerate(self.techs):
            self.tbl_techs.setItem(r,0,QTableWidgetItem(t['name'])); self.tbl_techs.setItem(r,1,QTableWidgetItem(str(t['cost']))); self.tbl_techs.setItem(r,2,QTableWidgetItem(str(t['cap']))); self.tbl_techs.setItem(r,3,QTableWidgetItem(str(t['range'])))

    # --- NEW: READ TABLES (Direct Edit) ---
    def read_data_from_tables(self):
        """Re-lit les données depuis les tableaux (permet l'édition manuelle)"""
        try:
            # 1. Sites
            new_sites = []
            for r in range(self.tbl_sites.rowCount()):
                new_sites.append({
                    'id': self.tbl_sites.item(r,0).text(),
                    'x': float(self.tbl_sites.item(r,1).text()),
                    'y': float(self.tbl_sites.item(r,2).text())
                })
            
            # 2. Districts
            new_dist = []
            for r in range(self.tbl_dist.rowCount()):
                new_dist.append({
                    'id': self.tbl_dist.item(r,0).text(),
                    'x': float(self.tbl_dist.item(r,1).text()),
                    'y': float(self.tbl_dist.item(r,2).text()),
                    'demand': float(self.tbl_dist.item(r,3).text())
                })
            
            # 3. Techs
            new_techs = []
            for r in range(self.tbl_techs.rowCount()):
                cost_txt = self.tbl_techs.item(r,1).text().replace('€', '')
                range_txt = self.tbl_techs.item(r,3).text().replace('km', '')
                new_techs.append({
                    'name': self.tbl_techs.item(r,0).text(),
                    'cost': float(cost_txt),
                    'cap': float(self.tbl_techs.item(r,2).text()),
                    'range': float(range_txt)
                })
            
            # Mise à jour des données internes
            self.sites = new_sites
            self.districts = new_dist
            self.techs = new_techs
            self.log("Données mises à jour depuis les tableaux.")
            return True

        except ValueError as e:
            QMessageBox.critical(self, "Erreur de Table", f"Une valeur dans les tableaux est invalide (texte au lieu de chiffre ?).\n\nErreur: {e}")
            return False

    # --- UPDATED: VALIDATION (Aggregated Errors) ---
    def check_inputs_errors(self):
        errors = []
        
        # Check Params
        try:
            ns = int(self.inp_nb_sites.text())
            if ns <= 0: errors.append("- Nb Sites doit être > 0")
        except: errors.append("- Nb Sites invalide")

        try:
            nd = int(self.inp_nb_dist.text())
            if nd <= 0: errors.append("- Nb Demandes doit être > 0")
        except: errors.append("- Nb Demandes invalide")

        try:
            sz = float(self.inp_size.text())
            if sz <= 0: errors.append("- Taille (km) doit être > 0")
        except: errors.append("- Taille invalide")

        try:
            bg = float(self.inp_budget.text())
            if bg < 0: errors.append("- Budget ne peut pas être négatif")
        except: errors.append("- Budget invalide")

        if errors:
            msg = "Veuillez corriger les erreurs suivantes :\n\n" + "\n".join(errors)
            QMessageBox.warning(self, "Saisie Incorrecte", msg)
            return False, None
        
        return True, (ns, nd, sz, bg)

    def refresh_data(self):
        ok, vals = self.check_inputs_errors()
        if not ok: return 

        if self.current_mode == "random": self.generate_random_data()
        elif self.current_mode == "grid": self.generate_grid_data()
        elif self.current_mode == "csv": self.reload_csv_files()

    def generate_random_data(self):
        self.current_mode = "random"
        ok, vals = self.check_inputs_errors()
        if not ok: return
        n_s, n_d, sz, _ = vals

        self.sites = [{'id':f"S{i}", 'x':random.uniform(0,sz), 'y':random.uniform(0,sz)} for i in range(n_s)]
        self.districts = [{'id':f"D{i}", 'x':random.uniform(0,sz), 'y':random.uniform(0,sz), 'demand':random.randint(100,2000)} for i in range(n_d)]
        self.last_res = None
        self.update_tables(); self.plot_map(); self.log("Aléatoire OK.")

    def generate_grid_data(self):
        self.current_mode = "grid"
        ok, vals = self.check_inputs_errors()
        if not ok: return
        _, n_d, sz, _ = vals
        
        self.sites = []
        step = sz/5
        for x in np.arange(0, sz+1, step):
            for y in np.arange(0, sz+1, step):
                self.sites.append({'id':f"S{len(self.sites)}", 'x':x, 'y':y})
        
        self.districts = [{'id':f"D{i}", 'x':random.uniform(0,sz), 'y':random.uniform(0,sz), 'demand':random.randint(100,2000)} for i in range(n_d)]
        self.last_res = None
        self.update_tables(); self.plot_map(); self.log("Grille OK.")

    def load_csv_real(self):
        path_s, _ = QFileDialog.getOpenFileName(self, "CSV Sites", "", "CSV (*.csv)")
        if not path_s: return
        path_d, _ = QFileDialog.getOpenFileName(self, "CSV Demandes", "", "CSV (*.csv)")
        if not path_d: return
        self.csv_sites_path = path_s; self.csv_districts_path = path_d; self.current_mode = "csv"
        self.reload_csv_files()

    def reload_csv_files(self):
        try:
            new_sites = []
            with open(self.csv_sites_path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                if 'x' not in reader.fieldnames: raise ValueError("CSV Sites: Manque colonne 'x'")
                for row in reader: new_sites.append({'id': row['id'], 'x': float(row['x']), 'y': float(row['y'])})
            
            new_dist = []
            with open(self.csv_districts_path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                if 'demand' not in reader.fieldnames: raise ValueError("CSV Demandes: Manque colonne 'demand'")
                for row in reader: new_dist.append({'id': row['id'], 'x': float(row['x']), 'y': float(row['y']), 'demand': int(row['demand'])})

            self.sites = new_sites; self.districts = new_dist
            self.inp_nb_sites.setText(str(len(self.sites))); self.inp_nb_dist.setText(str(len(self.districts)))
            self.last_res = None
            self.update_tables(); self.plot_map(); self.log(f"CSV OK.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur CSV", str(e))

    # --- VISUALISATION ---
    def refresh_map_style(self): self.plot_map(self.last_res)

    def plot_map(self, res=None):
        self.canvas.axes.clear()
        is_satellite = self.radio_sat.isChecked()
        try: max_size = float(self.inp_size.text())
        except: max_size = 200

        # Background
        if is_satellite:
            img_path = None
            for ext in ["jpg", "jpeg", "png"]:
                if os.path.exists(f"islem/paris.{ext}"): img_path = f"islem/paris.{ext}"; break
                if os.path.exists(f"paris.{ext}"): img_path = f"paris.{ext}"; break
            
            if img_path:
                try:
                    img = mpimg.imread(img_path)
                    self.canvas.axes.imshow(img, extent=[0, max_size, 0, max_size], aspect='auto', alpha=0.8)
                except: self.canvas.axes.set_facecolor('#051626')
            else: self.canvas.axes.set_facecolor('#051626')
            txt_c = 'white'; dem_uc = '#e74c3c'; dem_c = '#00ffaa'; site_ac = '#00d2ff'; link_c = '#00ffaa'
        else:
            self.canvas.axes.set_facecolor('white'); txt_c = 'black'; dem_uc = 'red'; dem_c = 'green'; site_ac = 'blue'; link_c = 'green'

        # Drawing
        dx = [d['x'] for d in self.districts]; dy = [d['y'] for d in self.districts]
        ds = [d['demand']/10 + 15 for d in self.districts]
        cols = [dem_uc] * len(self.districts)

        if res:
             covered = {i for i,j, pct in res['links']}
             for idx in covered: cols[idx] = dem_c
             
             for inst in res['installations']:
                 c = mpatches.Circle((inst['x'], inst['y']), inst['range'], color=site_ac, alpha=0.15)
                 self.canvas.axes.add_patch(c)
                 b = mpatches.Circle((inst['x'], inst['y']), inst['range'], fill=False, edgecolor=site_ac, linestyle='--')
                 self.canvas.axes.add_patch(b)

             for i, j, pct in res['links']:
                 d = self.districts[i]; s = self.sites[j]
                 alpha_line = max(0.2, pct * 0.8)
                 self.canvas.axes.plot([d['x'], s['x']], [d['y'], s['y']], color=link_c, lw=0.5, alpha=alpha_line)

        self.canvas.axes.scatter(dx, dy, s=ds, c=cols, edgecolors=txt_c, linewidth=0.5, label='_nolegend_', zorder=2)
        
        active_ids = {i['site_id'] for i in res['installations']} if res else set()
        sx = [s['x'] for s in self.sites if s['id'] not in active_ids]
        sy = [s['y'] for s in self.sites if s['id'] not in active_ids]
        self.canvas.axes.scatter(sx, sy, c='black', marker='s', s=40, alpha=0.6, label='_nolegend_', zorder=1)

        if res:
            ax = [i['x'] for i in res['installations']]; ay = [i['y'] for i in res['installations']]
            self.canvas.axes.scatter(ax, ay, c=site_ac, marker='^', s=130, edgecolors='white', linewidth=1, label='_nolegend_', zorder=3)

        self.canvas.axes.set_xlim(0, max_size); self.canvas.axes.set_ylim(0, max_size)
        self.canvas.axes.grid(True, linestyle=':', alpha=0.5)
        
        # --- MAP KEY (LEGEND) ---
        handles = []
        handles.append(mlines.Line2D([], [], color='black', marker='s', linestyle='None', markersize=8, label='Site Candidat'))
        handles.append(mlines.Line2D([], [], color=site_ac, marker='^', linestyle='None', markersize=8, label='Antenne Active'))
        handles.append(mlines.Line2D([], [], color=dem_uc, marker='o', linestyle='None', markersize=8, label='Demande (Non Couvert)'))
        handles.append(mlines.Line2D([], [], color=dem_c, marker='o', linestyle='None', markersize=8, label='Demande (Couvert)'))
        
        legend = self.canvas.axes.legend(handles=handles, loc='upper right', facecolor='white', framealpha=0.8)
        self.canvas.draw()

    # --- OPTIMISATION ---
    def start_optimization(self):
        # 1. Vérification Inputs
        ok, vals = self.check_inputs_errors()
        if not ok: return
        _, _, _, bg = vals
        
        # 2. Lecture Données Tableaux (Modifications Manuelles)
        if not self.read_data_from_tables(): return

        data = {'sites': self.sites, 'districts': self.districts, 'techs': self.techs, 'budget': bg}
        
        self.worker = SolverWorker(data)
        self.worker.log_signal.connect(self.log)
        self.worker.error.connect(self.handle_error)
        self.worker.finished.connect(self.handle_res)
        
        self.btn_solve.setVisible(False)
        self.btn_stop.setVisible(True)
        self.worker.start()

    def stop_optimization(self):
        if hasattr(self, 'worker'): self.worker.stop()

    def handle_error(self, msg):
        self.btn_solve.setVisible(True); self.btn_stop.setVisible(False)
        QMessageBox.critical(self, "Erreur", msg)

    def handle_res(self, res):
        self.last_res = res
        self.btn_solve.setVisible(True); self.btn_stop.setVisible(False)
        self.tabs.setCurrentIndex(1)
        
        self.tbl_res.setRowCount(len(res['installations']))
        for r, i in enumerate(res['installations']):
            self.tbl_res.setItem(r,0,QTableWidgetItem(str(i['site_id'])))
            self.tbl_res.setItem(r,1,QTableWidgetItem(f"({i['x']:.0f},{i['y']:.0f})"))
            self.tbl_res.setItem(r,2,QTableWidgetItem(i['tech_name']))
            litem = QTableWidgetItem(f"{int(i['load'])}/{i['capacity']}")
            if i['load']>i['capacity']*0.99: litem.setForeground(QColor('red')); litem.setFont(QFont("Arial", weight=QFont.Weight.Bold))
            self.tbl_res.setItem(r,3,litem)
            self.tbl_res.setItem(r,4,QTableWidgetItem(f"{i['cost']}€"))
            self.tbl_res.setItem(r,5,QTableWidgetItem(f"{i['range']}km"))

        pct = (res['obj_val']/res['total_demand'])*100
        self.lbl_metrics.setText(f"Couverture: {pct:.1f}% ({int(res['obj_val'])} clients) | Coût: {res['budget_used']}€")
        self.plot_map(res)

    def export_results_csv(self):
        if not hasattr(self, 'last_res') or not self.last_res:
            QMessageBox.warning(self, "Export Impossible", "Veuillez d'abord lancer une optimisation.")
            return
            
        f, _ = QFileDialog.getSaveFileName(self, "Sauvegarder Résultats", "", "CSV Files (*.csv)")
        if f:
            try:
                with open(f, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(["Site_ID", "X", "Y", "Technologie", "Charge", "Capacite_Max", "Cout", "Rayon"])
                    for item in self.last_res['installations']:
                        writer.writerow([
                            item['site_id'], item['x'], item['y'], 
                            item['tech_name'], int(item['load']), item['capacity'], 
                            item['cost'], item['range']
                        ])
                self.log(f"Résultats exportés vers : {f}")
                QMessageBox.information(self, "Succès", "Fichier CSV généré avec succès.")
            except Exception as e:
                QMessageBox.critical(self, "Erreur Export", str(e))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())