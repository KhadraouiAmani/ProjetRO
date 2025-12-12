import sys
import os
import time
import math
import numpy as np

# --- 1. MIGRATION VERS PYQT6 
# PyQt6 est la version la plus récente de la bibliothèque graphique.
# Nous importons ici tous les "Widgets" (Boutons, Tableaux, Fenêtres).
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QFileDialog, QTextEdit, QSpinBox,
                             QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView,
                             QMessageBox, QSplitter, QTabWidget, QAbstractItemView, QDoubleSpinBox,
                             QMainWindow)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont

# --- 2. INTÉGRATION DE MATPLOTLIB (GRAPHIQUES) ---
# Ce bloc permet d'afficher des graphiques scientifiques (Matplotlib)
# à l'intérieur d'une fenêtre PyQt.
try:
    # On essaie d'importer le backend spécifique à PyQt6
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
except ImportError:
    # Si non trouvé, on tente le backend générique (compatibilité)
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# --- 3. GESTION ROBUSTE DES IMPORTS  ---
# Ce bloc s'assure que Python trouve vos fichiers (solver, simulator...)
# même si le dossier d'exécution n'est pas le bon.
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

ERROR_MSG = None
try:
    # Importation de VOTRE logique métier (les fichiers que vous avez codés)
    from build_A_dynamic import read_coords_csv, build_matrices
    from solver_dynamic import solve_dynamic_expected
    from simulator import Simulator
    from map_utils import create_map
except ImportError as err:
    # Si un fichier manque, on ne fait pas crasher l'app tout de suite.
    # On stocke l'erreur pour l'afficher plus tard à l'utilisateur.
    ERROR_MSG = str(err)
    # On crée des fonctions "vides" pour que le code compile quand même
    def read_coords_csv(*args): raise ImportError(ERROR_MSG)
    def build_matrices(*args): raise ImportError(ERROR_MSG)
    def solve_dynamic_expected(*args): raise ImportError(ERROR_MSG)
    def Simulator(*args): raise ImportError(ERROR_MSG)
    def create_map(*args): raise ImportError(ERROR_MSG)

# --- 4. FEUILLE DE STYLE (CSS) ---
# Définit l'apparence "Professionnelle" de l'application.
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
QTextEdit { border: 1px solid #bdc3c7; border-radius: 6px; background: white; font-family: Consolas, monospace; }
"""

# --- CLASSE 1 : LA CARTE (CANVAS) ---
#C'est le composant qui permet de dessiner dans la fenêtre
class MplCanvas(FigureCanvas):
    """
    Widget personnalisé qui hérite de FigureCanvas.
    Il sert de 'toile' pour dessiner la carte et les vecteurs.
    """
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        # Création de la figure (la feuille blanche)
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        # Création des axes (le graphique)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title("Carte Géographique")
        self.ax.grid(True, linestyle=':', alpha=0.6)
        # Initialisation du parent
        super(MplCanvas, self).__init__(self.fig)

# --- CLASSE 2 : LE MOTEUR ASYNCHRONE (THREAD) ---
class SimThread(QThread):
    """
    Cette classe gère le Multithreading.
    Pourquoi ? Si on lançait la simulation (boucle while) dans la fenêtre principale,
    l'interface gèlerait et on ne pourrait plus cliquer sur 'Stop'.
    """
    # Signaux pour communiquer avec l'interface principale (Main Thread)
    mission_signal = pyqtSignal(object)        # Envoi d'info sur une mission
    progress_signal = pyqtSignal(int, int)     # Mise à jour barre de progression
    finished_signal = pyqtSignal(list)         # Signal de fin

    def __init__(self, sim, rate_lambda, horizon):
        super().__init__()
        self.sim = sim
        self.rate_lambda = rate_lambda
        self.horizon = horizon
        self._stop = False
        self._pause = False

    def run(self):
        """C'est ici que tourne la simulation en arrière-plan."""
        try:
            # 1. Génération des événements (Appels) selon loi de Poisson
            self.sim.generate_arrival(self.rate_lambda, self.horizon)
            
            # Récupération de la file d'attente
            events = list(self.sim.event_q)
            events.sort(key=lambda e: e[0]) # Tri chronologique
            total = len(events)
            self.sim.event_q = events
            processed = 0

            # 2. Boucle de traitement des événements
            while self.sim.event_q and not self._stop:
                # Gestion de la Pause
                while self._pause and not self._stop: 
                    time.sleep(0.05)
                
                # Extraction de l'événement le plus proche
                time_event, func, args = self.sim.event_q.pop(0)
                self.sim.clock = time_event
                
                # Exécution de la logique métier (handle_arrival ou finish_mission)
                try: 
                    func(*args)
                except Exception as e: 
                    self.mission_signal.emit({'type': 'error', 'msg': str(e)})
                
                # Envoi du signal à l'interface pour mise à jour graphique
                if self.sim.missions_log: 
                    self.mission_signal.emit(self.sim.missions_log[-1])
                
                processed += 1
                self.progress_signal.emit(processed, total)
                
                # Petit délai pour l'animation visuelle (sinon c'est trop rapide)
                time.sleep(0.015) 
            
            self.finished_signal.emit(self.sim.missions_log)
        except Exception as e:
            print(f"Erreur thread: {e}")

    def stop(self): self._stop = True
    def pause(self): self._pause = True
    def resume(self): self._pause = False

# --- CLASSE 3 : L'INTERFACE PRINCIPALE (IHM) ---
#QSplitter pour séparer l'analyse de données (à gauche avec des onglets) de la visualisation géographique (à droite),
#  offrant une ergonomie professionnelle pour le décideur
class MainWindow(QMainWindow): 
    def __init__(self):
        super().__init__()
        # Configuration de la fenêtre
        self.setWindowTitle('Optimization Hub - Projet RO')
        self.resize(1400, 850)
        self.setStyleSheet(STYLE)
        
        # Widget Central (Nécessaire pour QMainWindow)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # --- A. BARRE D'OUTILS (Haut) ---
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

        # --- B. PARAMÈTRES (Inputs) ---
        params_layout = QHBoxLayout()
        
        # Création des SpinBoxes (Boîtes à nombres)
        self.spin_vmax = QSpinBox(); self.spin_vmax.setRange(10,150); self.spin_vmax.setValue(50)
        self.spin_tmax = QSpinBox(); self.spin_tmax.setRange(1,240); self.spin_tmax.setValue(10)
        self.spin_lambda = QSpinBox(); self.spin_lambda.setRange(1,5000); self.spin_lambda.setValue(100)
        
        self.spin_budget = QDoubleSpinBox(); self.spin_budget.setRange(0, 100000000); self.spin_budget.setValue(1000000)
        self.spin_cost = QDoubleSpinBox(); self.spin_cost.setRange(0, 1000000); self.spin_cost.setValue(100000)
        
        # Ajout des labels et widgets
        params_layout.addWidget(QLabel("<b>Vitesse (km/h):</b>")); params_layout.addWidget(self.spin_vmax)
        params_layout.addWidget(QLabel("<b>Tmax (min):</b>")); params_layout.addWidget(self.spin_tmax)
        params_layout.addWidget(QLabel("<b>Budget Total:</b>")); params_layout.addWidget(self.spin_budget)
        params_layout.addWidget(QLabel("<b>Coût/Amb.:</b>")); params_layout.addWidget(self.spin_cost)
        
        main_layout.addLayout(params_layout)

        # --- C. BARRE D'ACTIONS ---
        action_layout = QHBoxLayout()
        self.btn_build = QPushButton('⚙ 3. Construire Matrice')
        self.btn_solve = QPushButton('🚀 4. Optimiser (avec Budget)')
        self.btn_start = QPushButton('▶ 5. Simulation')
        self.btn_start.setObjectName("success") # Style vert
        self.btn_pause = QPushButton('▶ Reprendre') # Initialement
        self.btn_stop = QPushButton('⏹ Stop')
        self.btn_stop.setObjectName("danger") # Style rouge
        
        # Désactivation initiale (sécurité)
        self.btn_pause.setEnabled(False); self.btn_stop.setEnabled(False)
        
        action_layout.addWidget(self.btn_build); action_layout.addWidget(self.btn_solve)
        action_layout.addWidget(self.btn_start); action_layout.addWidget(self.btn_pause); action_layout.addWidget(self.btn_stop)
        main_layout.addLayout(action_layout)

        # --- D. ZONE CENTRALE (SPLITTER) ---
        # Permet de redimensionner gauche/droite
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # --- GAUCHE : TABLEAUX ---
        left_widget = QWidget(); left_layout = QVBoxLayout(left_widget)
        self.tabs = QTabWidget()
        
        # Onglet 1 : Matrice A
        self.table_matrix = QTableWidget()
        self.table_matrix.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers) # Lecture seule
        self.tabs.addTab(self.table_matrix, "📐 Matrice A")
        
        # Onglet 2 : Résultats
        self.table_hops = QTableWidget(0, 3)
        self.table_hops.setHorizontalHeaderLabels(['Hôpital', 'Ambulances', 'Dispo Live'])
        self.table_hops.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabs.addTab(self.table_hops, "🚑 Résultat & Simu")
        
        left_layout.addWidget(self.tabs)
        
        # Zone de logs
        left_layout.addWidget(QLabel("<b>Journal :</b>"))
        self.log = QTextEdit(); self.log.setReadOnly(True)
        left_layout.addWidget(self.log)
        self.progress = QProgressBar(); left_layout.addWidget(self.progress)
        
        splitter.addWidget(left_widget)

        # --- DROITE : CARTE ---
        right_widget = QWidget(); right_layout = QVBoxLayout(right_widget)
        self.canvas = MplCanvas(self); right_layout.addWidget(self.canvas)
        splitter.addWidget(right_widget)
        
        # Réglage de la largeur (40% gauche, 60% droite)
        splitter.setSizes([600, 800])
        main_layout.addWidget(splitter)

        # Variables internes
        self.addrs = []; self.hops = []; self.A = None; self.x_sol = None
        self.sim = None; self.sim_thread = None; self.mapfile = None; self.active_lines = {}

        # --- CONNEXION DES SIGNAUX (INTERACTIVITÉ) ---
        self.btn_load_addrs.clicked.connect(self.load_addrs)
        self.btn_load_hops.clicked.connect(self.load_hops)
        self.btn_build.clicked.connect(self.build_A)
        self.btn_solve.clicked.connect(self.solve)
        self.btn_start.clicked.connect(self.start_sim)
        self.btn_pause.clicked.connect(self.pause_sim)
        self.btn_stop.clicked.connect(self.stop_sim)
        self.btn_export_map.clicked.connect(self.open_map)

    # --- LOGIQUE MÉTIER ---

    def load_addrs(self):
        """Charge le fichier CSV des demandes"""
        try:
            p, _ = QFileDialog.getOpenFileName(self, 'Adresses', '', 'CSV (*.csv)')
            if p: 
                self.addrs = read_coords_csv(p)
                self.log.append(f'📍 Adresses chargées: {len(self.addrs)}')
                self.plot_static_map()
        except ImportError: QMessageBox.critical(self, "Erreur", f"Module manquant: {ERROR_MSG}")
        except Exception as e: QMessageBox.critical(self, "Erreur", str(e))

    def load_hops(self):
        """Charge le fichier CSV des hôpitaux"""
        try:
            p, _ = QFileDialog.getOpenFileName(self, 'Hôpitaux', '', 'CSV (*.csv)')
            if p: 
                self.hops = read_coords_csv(p)
                self.log.append(f'🏥 Hôpitaux chargés: {len(self.hops)}')
                self.plot_static_map()
        except ImportError: QMessageBox.critical(self, "Erreur", f"Module manquant: {ERROR_MSG}")
        except Exception as e: QMessageBox.critical(self, "Erreur", str(e))

    def plot_static_map(self):
        """Dessine les points statiques sur la carte"""
        self.canvas.ax.clear()
        self.canvas.ax.set_title("Carte Géographique")
        self.canvas.ax.grid(True, alpha=0.3)
        if self.addrs: 
            self.canvas.ax.scatter([p[0] for p in self.addrs], [p[1] for p in self.addrs], c='#3498db', alpha=0.5, s=20, label='Demandes')
        if self.hops:
            hx = [p[0] for p in self.hops]; hy = [p[1] for p in self.hops]
            self.canvas.ax.scatter(hx, hy, c='#e74c3c', marker='s', s=120, edgecolors='black', label='Hôpitaux')
            for i, (x, y) in enumerate(zip(hx, hy)): 
                self.canvas.ax.text(x, y, f" H{i}", fontsize=9, fontweight='bold')
        self.canvas.ax.legend()
        self.canvas.draw()

    def build_A(self):
        """
        1. Calcule la matrice de couverture A.
        2. Affiche la Heatmap.
        3. MODULE INTELLIGENT : Suggère des paramètres si échec.
        """
        if not self.addrs or not self.hops: 
            QMessageBox.warning(self, "Erreur", "Veuillez charger les données."); return
        try:
            current_vmax = self.spin_vmax.value()
            current_tmax = self.spin_tmax.value()
            
            # Appel Module Mathématique
            self.A, self.dist, self.times = build_matrices(self.addrs, self.hops, current_vmax, current_tmax)
            self.log.append(f"✅ Matrice A construite : {self.A.shape}")

            # Remplissage Tableau (Heatmap)
            rows, cols = self.A.shape
            self.table_matrix.setRowCount(rows); self.table_matrix.setColumnCount(cols)
            self.table_matrix.setHorizontalHeaderLabels([f"H{j}" for j in range(cols)])
            self.table_matrix.setVerticalHeaderLabels([f"A{i}" for i in range(rows)])

            for i in range(rows):
                for j in range(cols):
                    val = self.A[i, j]
                    item = QTableWidgetItem(str(val))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    # Coloriage
                    if val == 1: item.setBackground(QColor("#2ecc71")); item.setForeground(QColor("white"))
                    else: item.setBackground(QColor("#ecf0f1")); item.setForeground(QColor("#95a5a6"))
                    self.table_matrix.setItem(i, j, item)
            
            self.table_matrix.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            self.tabs.setCurrentIndex(0)

            # --- MODULE DE SUGGESTION ---
            # Analyse si des lignes sont vides (adresses inatteignables)
            unreach = np.where(self.A.sum(axis=1) == 0)[0]
            if len(unreach) > 0:
                # Calcul inverse pour trouver ce qu'il manque
                times_un = self.times[unreach]
                min_t = np.min(times_un, axis=1)
                sugg_t = math.ceil(np.max(min_t))
                
                dists_un = self.dist[unreach]
                min_d = np.min(dists_un, axis=1)
                worst_d = np.max(min_d)
                sugg_v = math.ceil(worst_d / (current_tmax/60.0))
                
                msg = (f"⚠ <b>{len(unreach)} adresses inatteignables.</b><br>"
                       f"👉 Tmax suggéré: {sugg_t} min<br>👉 Vitesse suggérée: {sugg_v} km/h")
                QMessageBox.warning(self, "Alerte Smart", msg)
                self.log.append(f"⚠ {len(unreach)} adresses non couvertes.")
                
                # Marquer les points noirs sur la carte
                try:
                    ux = [self.addrs[i][0] for i in unreach]
                    uy = [self.addrs[i][1] for i in unreach]
                    self.canvas.ax.scatter(ux, uy, c='black', marker='x', s=80, label='INATTEIGNABLE', zorder=10)
                    self.canvas.draw()
                except: pass

        except Exception as e: QMessageBox.critical(self, "Erreur", str(e))

    def solve(self):
        """
        Appelle le solveur Gurobi avec les contraintes budgétaires.
        Gère le cas où la couverture stricte est impossible.
        """
        if self.A is None: return
        
        budget = self.spin_budget.value()
        cost = self.spin_cost.value()
        self.log.append(f"⏳ Optimisation Stricte... Budget={budget:,.0f}, Coût/U={cost:,.0f}")
        
        try:
            p = [0.1] * self.A.shape[1]
            
            # Appel du solveur (Soft Constraint sur l'ouverture, Hard sur la couverture)
            self.x_sol, total_ambs = solve_dynamic_expected(
                self.A, p, budget=budget, cost_per_amb=cost, min_per_hop=1 
            )
            
            if self.x_sol:
                # SUCCES
                cout_total = total_ambs * cost
                self.log.append(f"✅ Solution trouvée : {total_ambs} ambulances.")
                
                # Analyse de l'équité (Hôpitaux vides ?)
                hopitaux_vides = self.x_sol.count(0)
                if hopitaux_vides > 0:
                    self.log.append(f"⚠ Info : {hopitaux_vides} hôpital/aux vide(s) pour respecter le budget.")
                
                self.log.append(f"💰 Coût total : {cout_total:,.0f} (Reste : {budget - cout_total:,.0f})")
                
                # Mise à jour Tableau
                self.table_hops.setRowCount(len(self.hops))
                for j, count in enumerate(self.x_sol):
                    self.table_hops.setItem(j, 0, QTableWidgetItem(f"Hôpital {j}"))
                    self.table_hops.setItem(j, 1, QTableWidgetItem(str(count)))
                    self.table_hops.setItem(j, 2, QTableWidgetItem(str(count)))
                
                self.tabs.setCurrentIndex(1)
                self.mapfile = create_map(self.addrs, self.hops, self.x_sol, mapfile='res_optim.html')
            else:
                # ECHEC STRICT
                msg = "❌ <b>Optimisation Impossible.</b><br><br>" \
                      "Le budget est insuffisant pour garantir une <b>couverture stricte</b> de toutes les adresses.<br><br>" \
                      "Solutions :<br>1. Augmentez le Budget.<br>2. Augmentez Tmax."
                QMessageBox.critical(self, "Echec Critique", msg)
                self.log.append("❌ Echec : Pas de solution avec ce budget.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur Solveur", str(e))

    def start_sim(self):
        """Lance la simulation en Multithreading"""
        if not self.x_sol: return
        self.active_lines = {}
        self.plot_static_map() # Nettoyage carte
        
        # Initialisation Simulateur Métier
        self.sim = Simulator(self.A, self.dist, self.times, self.x_sol)
        
        # Initialisation Thread
        self.sim_thread = SimThread(self.sim, self.spin_lambda.value()/60.0, 24*60)
        
        # Connexion des signaux
        self.sim_thread.mission_signal.connect(self.on_sim_event)
        self.sim_thread.progress_signal.connect(lambda c,t: self.progress.setValue(int(c/t*100)))
        self.sim_thread.finished_signal.connect(lambda: [self.log.append("Fin Simu"), self.btn_start.setEnabled(True)])
        
        # Lancement
        self.sim_thread.start()
        self.btn_start.setEnabled(False); self.btn_pause.setEnabled(True); self.btn_stop.setEnabled(True)

    def pause_sim(self):
        if self.sim_thread:
            if self.sim_thread._pause: 
                self.sim_thread.resume()
                self.btn_pause.setText("⏸ Pause")
            else: 
                self.sim_thread.pause()
                self.btn_pause.setText("▶ Reprendre")

    def stop_sim(self):
        if self.sim_thread: self.sim_thread.stop()

    def on_sim_event(self, entry):
        """
        Appelée par le Thread pour mettre à jour l'IHM.
        Dessine les vecteurs verts sur la carte.
        """
        if not isinstance(entry, dict): return
        
        # CAS 1 : Départ mission
        if entry.get('served') and 'hop' in entry:
            try:
                h, a = self.hops[entry['hop']], self.addrs[entry['addr']]
                l, = self.canvas.ax.plot([h[0], a[0]], [h[1], a[1]], c='#2ecc71', lw=2, alpha=0.8)
                self.active_lines[entry.get('mission_id')] = l
                self.canvas.draw()
            except: pass
            
        # CAS 2 : Fin mission
        elif entry.get('completed'):
            mid = entry.get('mission_id')
            if mid in self.active_lines:
                try: self.active_lines[mid].remove(); del self.active_lines[mid]; self.canvas.draw()
                except: pass
        
        # Mise à jour dispo tableau (Couleurs)
        for j in range(len(self.hops)):
            avail = len(self.sim.available[j]); cap = self.x_sol[j]
            item = QTableWidgetItem(f"{avail} / {cap}")
            if avail == 0: item.setBackground(QColor("#e74c3c")) # Rouge
            elif avail < cap: item.setBackground(QColor("#f1c40f")) # Orange
            else: item.setBackground(QColor("#2ecc71")) # Vert
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
    sys.exit(app.exec())