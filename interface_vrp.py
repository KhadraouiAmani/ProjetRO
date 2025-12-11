"""
Interface Graphique pour le VRP Transport de Fonds - Tunisie
Version optimisée : coût fixe véhicule entièrement géré côté interface
"""

import sys
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QSpinBox, QDoubleSpinBox, QTextEdit, QGroupBox, QFormLayout,
    QMessageBox, QSplitter, QHeaderView, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.patches as mpatches

from projet_optimisation import VRPTransportFonds

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
        self.fig = Figure(figsize=(8, 6))
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
    def plot_solution(self, solution, positions, noms, niveaux_danger=None):
        self.ax.clear()
        if not positions or len(positions) == 0:
            self.ax.set_title("Aucune donnée")
            self.draw()
            return
        colors = ['#e74c3c', '#3498db', '#2ecc71', '#9b59b6', '#f39c12']
        for i, (x, y) in enumerate(positions):
            nom = noms[i] if i < len(noms) else f"Point {i}"
            if i == 0:
                self.ax.scatter(x, y, c='red', s=250, marker='s', zorder=5, edgecolors='black', linewidth=2)
                self.ax.annotate(nom, (x, y), textcoords="offset points", xytext=(0, 12), ha='center', fontsize=8, fontweight='bold')
            else:
                self.ax.scatter(x, y, c='#3498db', s=150, zorder=5, edgecolors='black', linewidth=1)
                self.ax.annotate(nom, (x, y), textcoords="offset points", xytext=(0, 10), ha='center', fontsize=7)
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
                            lw = 2
                            linestyle = '-'
                            if niveaux_danger is not None:
                                danger = niveaux_danger[idx_start][idx_end]
                                if danger > 5:
                                    linestyle = '--'
                                    lw = 3
                            self.ax.annotate('', xy=end, xytext=start, arrowprops=dict(arrowstyle='->', color=color, lw=lw, linestyle=linestyle))
            legend_elements = [
                mpatches.Patch(color=colors[k], label=f'Camion {k+1}')
                for k in solution['tournees'].keys() if len(solution['tournees'][k]) > 2
            ]
            if legend_elements:
                self.ax.legend(handles=legend_elements, loc='upper right')
        self.ax.set_title("Tournées Optimales - Transport de Fonds (Tunisie)", fontsize=11, fontweight='bold')
        self.ax.set_xlabel("Position X (km)")
        self.ax.set_ylabel("Position Y (km)")
        self.ax.grid(True, alpha=0.3)
        self.fig.tight_layout()
        self.draw()

    def plot_error(self, message):
        self.ax.clear()
        self.ax.text(0.5, 0.5, message, ha='center', va='center',
                    fontsize=11, color='red', transform=self.ax.transAxes, wrap=True)
        self.ax.set_title("Erreur", fontsize=12, fontweight='bold', color='red')
        self.ax.axis('off')
        self.fig.tight_layout()
        self.draw()

# --- Main Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        print("Methods:", dir(self))
        super().__init__()
        self.setWindowTitle("🏦 Transport de Fonds - VRP Tunisie")
        self.setMinimumSize(1300, 850)
        self.vrp_model = VRPTransportFonds()
        self.solution = None
        self.worker = None
        self.positions = []
        self.niveaux_danger = None
        self.setup_ui()
        self.charger_donnees_exemple()

    def update_tables_size(self):
        """
        Update agencies/distances/danger table sizes and headers when number of clients changes.
        """
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
        # Update distance and danger tables
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


    def charger_donnees_exemple(self):
        """
        Remplit les tables avec des données d'exemple typiques (Tunis).
        """
        n = 5
        self.spin_clients.setValue(n)
        self.table_agences.setRowCount(n)
        # Données exemple : agences (nom, demande, X, Y, ouverture, fermeture)
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
                # Colorer selon le danger
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
        """
        Remplit la matrice de distances euclidiennes automatique (en km).
        """
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
        """
        Retourne la matrice numpy des niveaux de danger.
        """
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
        """
        Valide la saisie utilisateur (demande < capacité, etc).
        """
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
        splitter = QSplitter(Qt.Orientation.Horizontal)
        # --- Paramètres généraux ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        params_group = QGroupBox("⚙️ Paramètres Généraux")
        params_layout = QFormLayout()
        self.spin_clients = QSpinBox()
        self.spin_clients.setRange(2, 15)
        self.spin_clients.setValue(5)
        self.spin_clients.valueChanged.connect(self.update_tables_size)
        params_layout.addRow("Nombre d'agences:", self.spin_clients)
        self.spin_vehicules = QSpinBox()
        self.spin_vehicules.setRange(1, 10)
        self.spin_vehicules.setValue(2)
        params_layout.addRow("Nombre de véhicules:", self.spin_vehicules)
        self.spin_capacite = QDoubleSpinBox()
        self.spin_capacite.setRange(10000, 50000000)
        self.spin_capacite.setValue(500000)
        self.spin_capacite.setSuffix(" TND")
        self.spin_capacite.setSingleStep(50000)
        params_layout.addRow("Capacité véhicule:", self.spin_capacite)
        params_group.setLayout(params_layout)
        left_layout.addWidget(params_group)
        # --- Coût ---
        cout_group = QGroupBox("💰 Paramètres de Coût")
        cout_layout = QFormLayout()
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
        self.spin_cout_danger = QDoubleSpinBox()
        self.spin_cout_danger.setRange(0, 500)
        self.spin_cout_danger.setValue(50)
        self.spin_cout_danger.setSuffix(" TND/niveau")
        self.spin_cout_danger.setSingleStep(10)
        cout_layout.addRow("Coût du risque:", self.spin_cout_danger)
        self.spin_danger_max = QSpinBox()
        self.spin_danger_max.setRange(1, 10)
        self.spin_danger_max.setValue(8)
        self.spin_danger_max.setSpecialValueText("Pas de limite")
        cout_layout.addRow("Danger max autorisé:", self.spin_danger_max)
        cout_group.setLayout(cout_layout)
        left_layout.addWidget(cout_group)
        # --- Onglets (Agences, Distances, Danger) ---
        tabs = QTabWidget()
        # Agences
        tab_agences = QWidget()
        tab_agences_layout = QVBoxLayout(tab_agences)
        self.table_agences = QTableWidget()
        self.table_agences.setColumnCount(6)
        self.table_agences.setHorizontalHeaderLabels([
            "Nom", "Demande (TND)", "X (km)", "Y (km)", "Ouverture", "Fermeture"
        ])
        self.table_agences.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tab_agences_layout.addWidget(self.table_agences)
        tabs.addTab(tab_agences, "🏢 Agences")
        # Distances
        tab_distances = QWidget()
        tab_distances_layout = QVBoxLayout(tab_distances)
        self.table_distances = QTableWidget()
        tab_distances_layout.addWidget(self.table_distances)
        btn_calc_distances = QPushButton("📐 Calculer distances")
        btn_calc_distances.clicked.connect(self.calculer_distances)
        tab_distances_layout.addWidget(btn_calc_distances)
        tabs.addTab(tab_distances, "📏 Distances")
        # Danger
        tab_danger = QWidget()
        tab_danger_layout = QVBoxLayout(tab_danger)
        lbl_danger_info = QLabel("Niveau de danger: 0 (sûr) à 10 (très dangereux)")
        lbl_danger_info.setStyleSheet("color: #666; font-style: italic;")
        tab_danger_layout.addWidget(lbl_danger_info)
        self.table_danger = QTableWidget()
        tab_danger_layout.addWidget(self.table_danger)
        tabs.addTab(tab_danger, "🚨 Danger")
        left_layout.addWidget(tabs)
        # Boutons
        buttons_layout = QHBoxLayout()
        self.btn_resoudre = QPushButton("🚀 RÉSOUDRE")
        self.btn_resoudre.clicked.connect(self.lancer_optimisation)
        buttons_layout.addWidget(self.btn_resoudre)
        btn_reset = QPushButton("🔄 Réinitialiser")
        btn_reset.clicked.connect(self.charger_donnees_exemple)
        buttons_layout.addWidget(btn_reset)
        left_layout.addLayout(buttons_layout)
        self.label_validation = QLabel("")
        self.label_validation.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(self.label_validation)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        left_layout.addWidget(self.progress_bar)
        # ---- Panneau droit (visualisation, résultats)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
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
        splitter.setSizes([450, 850])
        main_layout.addWidget(splitter)
    # (Toutes les autres méthodes comme update_tables_size, charger_donnees_exemple, calculer_distances, get_danger_matrix...)
    # ... Inchangées, replacer ici depuis ta version précédente ou demander le code complet ...
    # --- Seule la différence dans get_data_from_tables() ---
    def get_data_from_tables(self):
        n = self.spin_clients.value()
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
        return {
            'n_clients': n,
            'n_vehicules': self.spin_vehicules.value(),
            'capacite_vehicule': self.spin_capacite.value(),
            'demandes': demandes,
            'distances': distances,
            'fenetres_temps': fenetres,
            'temps_service': [15] * n,
            'noms_clients': noms,
            'niveaux_danger': self.get_danger_matrix(),
            'cout_fixe_vehicule': self.spin_cout_fixe.value(),  # <-- AJOUT !
            'cout_km': self.spin_cout_km.value(),
            'cout_danger': self.spin_cout_danger.value(),
            'poids_distance': 1.0,
            'poids_danger': 1.0,
            'danger_max_autorise': self.spin_danger_max.value() if self.spin_danger_max.value() < 10 else None
        }
    # ...autres méthodes...
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
            text += f"💵 Coût fixe véhicule (chauffeur, assurance, amortissement): {solution.get('cout_fixe_vehicule', '-'):.2f} TND par véhicule utilisé\n"
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
                    text += f"   💵 Charge: {charge: ,.0f} TND\n"
                    if k in solution.get('stats_tournees', {}):
                        stats = solution['stats_tournees'][k]
                        text += f"   📏 Distance: {stats['distance']:.1f} km\n"
                        text += f"   🚨 Danger moyen: {stats['danger_moyen']:.1f}/10\n"
                        text += f"   💲 Coût variable tournée: {stats['cout_variable']:.2f} TND\n"
                        text += f"   💲 Coût fixe véhicule: {stats['cout_fixe']:.2f} TND\n"
                        text += f"   💲 Coût total tournée: {stats['cout_total']:.2f} TND\n"
                    used_camion += 1
            self.label_validation.setText("✅ Solution trouvée!")
            self.label_validation.setStyleSheet("color: green; font-weight: bold;")
            self.canvas.plot_solution(solution, self.positions, noms_complets, params['niveaux_danger'])
        else:
            text = "=" * 55 + "\n"
            text += "  ❌ AUCUNE SOLUTION TROUVÉE\n"
            text += "=" * 55 + "\n\n"
            text += solution.get('message', 'Infeasible')
            self.label_validation.setText("❌ Problème infaisable")
            self.label_validation.setStyleSheet("color: red; font-weight: bold;")
            self.canvas.plot_solution(None, self.positions, noms_complets)
        self.text_results.setText(text)
    # ...methods for error, update, distances, etc. (à recopier de ta version précédente)...
    # Entrypoint
    def lancer_optimisation(self):
        erreurs = self.valider_donnees()
        if erreurs:
            message = "ERREURS:\n\n" + "\n".join(f"• {e}" for e in erreurs)
            self.label_validation.setText("❌ Erreurs détectées")
            self.label_validation.setStyleSheet("color: red; font-weight: bold;")
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
        self.label_validation.setStyleSheet("color: red; font-weight: bold;")
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