import sys
import os
import time
import math  # Important pour le calcul des suggestions (ceil)
import numpy as np

# PyQt5 Imports
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QFileDialog, QTextEdit, QSpinBox,
                             QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView,
                             QMessageBox, QSplitter, QTabWidget, QAbstractItemView)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QFont

# Matplotlib Integration
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# les modules
try:
    from build_A_dynamic import read_coords_csv, build_matrices
    from solver_dynamic import solve_dynamic_expected
    from simulator import Simulator
    from map_utils import create_map
except ImportError:
    pass

# ---------- Stylesheet ----------
#C'est du code CSS. Il définit l'apparence
# pour que l'application ne ressemble pas à un vieux logiciel Windows 95.
STYLE = """
QWidget { background-color: #f4f6f9; font-family: 'Segoe UI', Arial; color: #333; }
QPushButton { background-color: #2c3e50; color: white; border-radius: 5px; padding: 8px 15px; font-weight: bold; }
QPushButton:hover { background-color: #34495e; }
QPushButton:disabled { background-color: #bdc3c7; color: #7f8c8d; }
QPushButton#danger { background-color: #e74c3c; }
QPushButton#success { background-color: #27ae60; }
QTableWidget { border: 1px solid #bdc3c7; background-color: #ecf0f1; selection-background-color: #3498db; gridline-color: #bdc3c7; }
QHeaderView::section { background-color: #2c3e50; color: white; padding: 5px; border: 1px solid #34495e; font-weight: bold; }
QTabWidget::pane { border: 1px solid #bdc3c7; top: -1px; }
QTabBar::tab { background: #bdc3c7; padding: 8px 20px; border-top-left-radius: 4px; border-top-right-radius: 4px; }
QTabBar::tab:selected { background: #ecf0f1; border-bottom-color: #ecf0f1; font-weight: bold; }
QProgressBar { border: none; border-radius: 4px; height: 12px; background: #e2e8f0; }
QProgressBar::chunk { background-color: #27ae60; border-radius: 4px; }
QTextEdit { border: 1px solid #bdc3c7; border-radius: 6px; background: white; font-family: Consolas, monospace; }
"""

#pour les graphiques matplotlib intégrés
# ---------- Matplotlib Canvas ----------
class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title("Carte de Déploiement")
        self.ax.grid(True, linestyle=':', alpha=0.6)
        self.fig.tight_layout()
        super(MplCanvas, self).__init__(self.fig)


# ---------- Thread de Simulation ----------
#n Thread séparé pour la simulation
#  Cela permet de calculer les déplacements des ambulances en arrière-plan tout en gardant l'interface fluide et réactive
class SimThread(QThread):
    mission_signal = pyqtSignal(object)        
    progress_signal = pyqtSignal(int, int)     
    finished_signal = pyqtSignal(list)         

    def __init__(self, sim, rate_lambda, horizon):
        super().__init__()
        self.sim = sim
        self.rate_lambda = rate_lambda
        self.horizon = horizon
        self._stop = False
        self._pause = False

    def run(self):
        self.sim.generate_arrival(self.rate_lambda, self.horizon)
        events = list(self.sim.event_q)
        events.sort(key=lambda e: e[0])
        total = len(events)
        self.sim.event_q = events
        processed = 0
        while self.sim.event_q and not self._stop:
            while self._pause and not self._stop: time.sleep(0.05)
            time_event, func, args = self.sim.event_q.pop(0)
            self.sim.clock = time_event
            try: func(*args)
            except Exception as e: self.mission_signal.emit({'type': 'error', 'msg': str(e)})
            if self.sim.missions_log: self.mission_signal.emit(self.sim.missions_log[-1])
            processed += 1
            self.progress_signal.emit(processed, total)
            time.sleep(0.015) 
        self.finished_signal.emit(self.sim.missions_log)

    def stop(self): self._stop = True
    def pause(self): self._pause = True
    def resume(self): self._pause = False


# ---------- GUI Principal ----------
#L'interface est divisée ergonomiquement :
#  les contrôles en haut, les données analytiques à gauche (matrices) et la visualisation géographique à droite.
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('EMS Optimizer Pro - Aide à la Décision')
        self.resize(1400, 850)
        self.setStyleSheet(STYLE)
        
        main_layout = QVBoxLayout()
        
        # 1. Top Bar
        top_layout = QHBoxLayout()
        self.btn_load_addrs = QPushButton('📂 1. Charger Adresses')
        self.btn_load_hops = QPushButton('🏥 2. Charger Hôpitaux')
        top_layout.addWidget(self.btn_load_addrs)
        top_layout.addWidget(self.btn_load_hops)
        top_layout.addStretch()
        self.btn_export_map = QPushButton('🌐 Voir Carte Web')
        self.btn_export_map.setStyleSheet("background-color: #8e44ad; color: white;")
        top_layout.addWidget(self.btn_export_map)
        main_layout.addLayout(top_layout)

        # 2. Paramètres
        params_layout = QHBoxLayout()
        self.spin_vmax = QSpinBox(); self.spin_vmax.setRange(10,150); self.spin_vmax.setValue(50)
        self.spin_tmax = QSpinBox(); self.spin_tmax.setRange(1,240); self.spin_tmax.setValue(15)
        self.spin_lambda = QSpinBox(); self.spin_lambda.setRange(1,5000); self.spin_lambda.setValue(100)
        params_layout.addWidget(QLabel("<b>Vitesse (km/h):</b>")); params_layout.addWidget(self.spin_vmax)
        params_layout.addWidget(QLabel("<b>Tmax (min):</b>")); params_layout.addWidget(self.spin_tmax)
        params_layout.addWidget(QLabel("<b>Demandes/Heure (λ):</b>")); params_layout.addWidget(self.spin_lambda)
        params_layout.addStretch()
        main_layout.addLayout(params_layout)

        # 3. Actions
        action_layout = QHBoxLayout()
        self.btn_build = QPushButton('⚙️ 3. Construire Matrice')
        self.btn_solve = QPushButton('🚀 4. Optimiser')
        self.btn_start = QPushButton('▶ 5. Simulation')
        self.btn_start.setObjectName("success")
        self.btn_pause = QPushButton('⏸ Pause')
        self.btn_stop = QPushButton('⏹ Stop')
        self.btn_stop.setObjectName("danger")
        self.btn_pause.setEnabled(False); self.btn_stop.setEnabled(False)
        action_layout.addWidget(self.btn_build); action_layout.addWidget(self.btn_solve)
        action_layout.addWidget(self.btn_start); action_layout.addWidget(self.btn_pause); action_layout.addWidget(self.btn_stop)
        main_layout.addLayout(action_layout)

        # 4. Splitter Central
        splitter = QSplitter(Qt.Horizontal)
        
        # --- GAUCHE ---
        left_widget = QWidget(); left_layout = QVBoxLayout(left_widget)
        self.tabs = QTabWidget()
        
        # Onglet 1 : Matrice
        self.table_matrix = QTableWidget(); self.table_matrix.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabs.addTab(self.table_matrix, "📐 Matrice A (Heatmap)")
        
        # Onglet 2 : Simulation
        self.table_hops = QTableWidget(0, 3)
        self.table_hops.setHorizontalHeaderLabels(['Hôpital', 'Capacité', 'Dispo Live'])
        self.table_hops.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabs.addTab(self.table_hops, "🚑 Simulation")
        
        left_layout.addWidget(self.tabs)
        left_layout.addWidget(QLabel("<b>Journal :</b>"))
        self.log = QTextEdit(); self.log.setReadOnly(True)
        left_layout.addWidget(self.log)
        self.progress = QProgressBar(); left_layout.addWidget(self.progress)
        splitter.addWidget(left_widget)

        # --- DROITE ---
        right_widget = QWidget(); right_layout = QVBoxLayout(right_widget)
        self.canvas = MplCanvas(self); right_layout.addWidget(self.canvas)
        splitter.addWidget(right_widget)
        splitter.setSizes([600, 800])
        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

        # Interne
        self.addrs = []; self.hops = []; self.A = None; self.x_sol = None
        self.sim = None; self.sim_thread = None; self.mapfile = None; self.active_lines = {}

        # Signaux
        self.btn_load_addrs.clicked.connect(self.load_addrs)
        self.btn_load_hops.clicked.connect(self.load_hops)
        self.btn_build.clicked.connect(self.build_A)
        self.btn_solve.clicked.connect(self.solve)
        self.btn_start.clicked.connect(self.start_sim)
        self.btn_pause.clicked.connect(self.pause_sim)
        self.btn_stop.clicked.connect(self.stop_sim)
        self.btn_export_map.clicked.connect(self.open_map)

    def load_addrs(self):
        p, _ = QFileDialog.getOpenFileName(self, 'Adresses', '', 'CSV (*.csv)')
        if p: self.addrs = read_coords_csv(p); self.log.append(f'📍 Adresses: {len(self.addrs)}'); self.plot_static_map()

    def load_hops(self):
        p, _ = QFileDialog.getOpenFileName(self, 'Hôpitaux', '', 'CSV (*.csv)')
        if p: self.hops = read_coords_csv(p); self.log.append(f'🏥 Hôpitaux: {len(self.hops)}'); self.plot_static_map()

    def plot_static_map(self):
        self.canvas.ax.clear(); self.canvas.ax.set_title("Carte Géographique"); self.canvas.ax.grid(True, alpha=0.3)
        if self.addrs: self.canvas.ax.scatter([p[0] for p in self.addrs], [p[1] for p in self.addrs], c='#3498db', alpha=0.5, s=20, label='Demandes')
        if self.hops:
            hx = [p[0] for p in self.hops]; hy = [p[1] for p in self.hops]
            self.canvas.ax.scatter(hx, hy, c='#e74c3c', marker='s', s=120, edgecolors='black', label='Hôpitaux')
            for i, (x, y) in enumerate(zip(hx, hy)): self.canvas.ax.text(x, y, f" H{i}", fontsize=9, fontweight='bold')
        self.canvas.ax.legend(); self.canvas.draw()

  
    def build_A(self):
        if not self.addrs or not self.hops:
            QMessageBox.warning(self, "Erreur", "Veuillez charger les fichiers CSV.")
            return

        try:
            # Récupération des paramètres actuels
            current_vmax = self.spin_vmax.value()
            current_tmax = self.spin_tmax.value()

            # Calcul des matrices
            self.A, self.dist, self.times = build_matrices(self.addrs, self.hops, current_vmax, current_tmax)
            self.log.append(f"✅ Matrice construite : {self.A.shape}")

            # --- 1. AFFICHAGE DE LA HEATMAP (COULEURS) ---
            rows, cols = self.A.shape
            self.table_matrix.setRowCount(rows)
            self.table_matrix.setColumnCount(cols)
            self.table_matrix.setHorizontalHeaderLabels([f"H{j}" for j in range(cols)])
            self.table_matrix.setVerticalHeaderLabels([f"A{i}" for i in range(rows)])

            for i in range(rows):
                for j in range(cols):
                    val = self.A[i, j]
                    item = QTableWidgetItem(str(val))
                    item.setTextAlignment(Qt.AlignCenter)
                    if val == 1:
                        item.setBackground(QColor("#2ecc71")) # Vert
                        item.setForeground(QColor("white"))
                    else:
                        item.setBackground(QColor("#ecf0f1")) # Gris
                        item.setForeground(QColor("#95a5a6"))
                    self.table_matrix.setItem(i, j, item)
            
            self.table_matrix.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            self.tabs.setCurrentIndex(0)

            # --- 2. LOGIQUE DE SUGGESTION (RESTAURÉE) ---
            # On cherche les adresses non couvertes (somme ligne = 0)
            row_sums = self.A.sum(axis=1)
            unreachable_indices = np.where(row_sums == 0)[0]
            count_unreach = len(unreachable_indices)

            if count_unreach > 0:
                # Calculs pour suggestions
                times_for_unreach = self.times[unreachable_indices]
                min_times = np.min(times_for_unreach, axis=1) # Meilleur temps actuel pour ces adresses
                suggested_tmax = np.max(min_times)            # Le pire des meilleurs temps

                dists_for_unreach = self.dist[unreachable_indices]
                min_dists = np.min(dists_for_unreach, axis=1)
                worst_dist = np.max(min_dists)

                # Vitesse suggérée = Distance / Temps (où Temps = Tmax actuel)
                suggested_vmax = worst_dist / (current_tmax / 60.0)

                # Arrondis
                sugg_t = math.ceil(suggested_tmax)
                sugg_v = math.ceil(suggested_vmax)

                msg = (f"⚠️ <b>{count_unreach} adresse(s) sont inatteignables.</b><br><br>"
                       f"Avec vos paramètres actuels, les ambulances n'arrivent pas à temps.<br>"
                       f"Voici les valeurs minimales suggérées pour tout couvrir :<br><br>"
                       f"👉 <b>Tmax suggéré :</b> {sugg_t} min (au lieu de {current_tmax})<br>"
                       f"OU<br>"
                       f"👉 <b>Vitesse suggérée :</b> {sugg_v} km/h (au lieu de {current_vmax})")
                
                QMessageBox.warning(self, "Suggestions Intelligentes", msg)
                self.log.append(f"⚠️ ALERTE : {count_unreach} adresses non couvertes. Suggestion Tmax > {sugg_t} min.")

                # Marquer les points noirs sur la carte
                try:
                    unreach_x = [self.addrs[i][0] for i in unreachable_indices]
                    unreach_y = [self.addrs[i][1] for i in unreachable_indices]
                    self.canvas.ax.scatter(unreach_x, unreach_y, c='black', marker='x', s=80, label='INATTEIGNABLE', zorder=10)
                    self.canvas.draw()
                except: pass
            else:
                self.log.append("✅ Couverture totale possible avec ces paramètres.")

        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))

    def solve(self):
        if self.A is None: return
        p = [0.1] * self.A.shape[1]
        self.x_sol, total = solve_dynamic_expected(self.A, p)
        if self.x_sol:
            self.log.append(f"🏆 Optimisation : {total} ambulances.")
            self.table_hops.setRowCount(len(self.hops))
            for j, count in enumerate(self.x_sol):
                self.table_hops.setItem(j, 0, QTableWidgetItem(f"Hôpital {j}"))
                self.table_hops.setItem(j, 1, QTableWidgetItem(str(count)))
                self.table_hops.setItem(j, 2, QTableWidgetItem(str(count)))
            self.tabs.setCurrentIndex(1)
            self.mapfile = create_map(self.addrs, self.hops, self.x_sol, mapfile='res_optim.html')
        else:
            QMessageBox.warning(self, "Echec", "Pas de solution trouvée.")

    def start_sim(self):
        if not self.x_sol: return
        self.active_lines = {}
        self.plot_static_map()
        self.sim = Simulator(self.A, self.dist, self.times, self.x_sol)
        self.sim_thread = SimThread(self.sim, self.spin_lambda.value()/60.0, 24*60)
        self.sim_thread.mission_signal.connect(self.on_sim_event)
        self.sim_thread.progress_signal.connect(lambda c,t: self.progress.setValue(int(c/t*100)))
        self.sim_thread.finished_signal.connect(lambda: [self.log.append("Fin Simu"), self.btn_start.setEnabled(True)])
        self.sim_thread.start()
        self.btn_start.setEnabled(False); self.btn_pause.setEnabled(True); self.btn_stop.setEnabled(True)

    def pause_sim(self):
        if self.sim_thread:
            if self.sim_thread._pause: self.sim_thread.resume(); self.btn_pause.setText("⏸ Pause")
            else: self.sim_thread.pause(); self.btn_pause.setText("▶ Reprendre")

    def stop_sim(self):
        if self.sim_thread: self.sim_thread.stop()

    def on_sim_event(self, entry):
        if not isinstance(entry, dict): return
        if entry.get('served') and 'hop' in entry:
            try:
                h, a = self.hops[entry['hop']], self.addrs[entry['addr']]
                l, = self.canvas.ax.plot([h[0], a[0]], [h[1], a[1]], c='#2ecc71', lw=2, alpha=0.8)
                self.active_lines[entry.get('mission_id')] = l
                self.canvas.draw()
            except: pass
        elif entry.get('completed'):
            mid = entry.get('mission_id')
            if mid in self.active_lines:
                try: self.active_lines[mid].remove(); del self.active_lines[mid]; self.canvas.draw()
                except: pass
        for j in range(len(self.hops)):
            avail = len(self.sim.available[j]); cap = self.x_sol[j]
            item = QTableWidgetItem(f"{avail} / {cap}")
            item.setBackground(QColor("#e74c3c") if avail==0 else QColor("#f1c40f") if avail<cap else QColor("#2ecc71"))
            self.table_hops.setItem(j, 2, item)

    def open_map(self):
        if self.mapfile and os.path.exists(self.mapfile):
            import webbrowser
            webbrowser.open('file://' + os.path.realpath(self.mapfile))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 9))
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())