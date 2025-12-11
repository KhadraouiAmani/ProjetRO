"""
Projet RO : Optimisation des Tournées de Transport de Fonds Bancaires
Modèle VRP avec coût fixe par véhicule utilisé (chauffeur inclus)
"""

import numpy as np
from typing import List, Tuple, Dict
import gurobipy as gp
from gurobipy import GRB

class VRPTransportFonds:
    """
    Modèle VRP avec coût fixe par véhicule utilisé (chauffeur inclus)
    Fonction objectif = coût variable (distance, risque) + coût fixe véhicule utilisé
    """
    def __init__(self):
        self.model = None
        self.solution = None
        self.status = None

    def resoudre(self,
                 n_clients: int,
                 n_vehicules: int,
                 capacite_vehicule: float,
                 demandes: List[float],
                 distances: np.ndarray,
                 fenetres_temps: List[Tuple[float, float]],
                 temps_service: List[float],
                 noms_clients: List[str] = None,
                 niveaux_danger: np.ndarray = None,
                 cout_km: float = 0.8,
                 cout_danger: float = 50.0,
                 cout_fixe_vehicule: float = 350.0,
                 poids_distance: float = 1.0,
                 poids_danger: float = 1.0,
                 danger_max_autorise: float = None
    ) -> Dict:

        self.model = gp.Model("VRP_Transport_Fonds_Tunisie")
        self.model.Params.OutputFlag = 1

        n = n_clients
        K = n_vehicules
        Q = capacite_vehicule

        V = range(n + 1)
        C = range(1, n + 1)
        Vehicules = range(K)

        if niveaux_danger is None:
            niveaux_danger = np.zeros((n + 1, n + 1))

        M = 10000

        couts = np.zeros((n + 1, n + 1))
        for i in V:
            for j in V:
                cout_dist = distances[i][j] * cout_km * poids_distance
                cout_risk = niveaux_danger[i][j] * cout_danger * poids_danger
                couts[i][j] = cout_dist + cout_risk

        x = self.model.addVars(V, V, Vehicules, vtype=GRB.BINARY, name="x")
        t = self.model.addVars(V, vtype=GRB.CONTINUOUS, lb=0, name="t")
        y = self.model.addVars(Vehicules, vtype=GRB.BINARY, name="y")

        self.model.setObjective(
            gp.quicksum(couts[i][j] * x[i, j, k]
                        for i in V for j in V for k in Vehicules if i != j)
            + gp.quicksum(cout_fixe_vehicule * y[k] for k in Vehicules),
            GRB.MINIMIZE
        )

        for i in C:
            self.model.addConstr(
                gp.quicksum(x[i, j, k] for j in V for k in Vehicules if j != i) == 1,
                name=f"visite_unique_{i}"
            )

        for k in Vehicules:
            for i in V:
                self.model.addConstr(
                    gp.quicksum(x[i, j, k] for j in V if j != i) ==
                    gp.quicksum(x[j, i, k] for j in V if j != i),
                    name=f"flux_{k}_{i}"
                )

        for k in Vehicules:
            self.model.addConstr(y[k] >= gp.quicksum(x[0, j, k] for j in C) / n, name=f"utilisation_{k}")
            self.model.addConstr(gp.quicksum(x[0, j, k] for j in C) <= n * y[k], name=f"limite_part_{k}")
            self.model.addConstr(gp.quicksum(x[0, j, k] for j in C) <= 1, name=f"depart_depot_{k}")
            self.model.addConstr(gp.quicksum(x[i, 0, k] for i in C) <= 1, name=f"retour_depot_{k}")
            self.model.addConstr(
                gp.quicksum(demandes[i - 1] * gp.quicksum(x[i, j, k] for j in V if j != i)
                            for i in C) <= Q,
                name=f"capacite_{k}"
            )

        for i in C:
            a_i, b_i = fenetres_temps[i - 1]
            self.model.addConstr(t[i] >= a_i, name=f"fenetre_min_{i}")
            self.model.addConstr(t[i] <= b_i, name=f"fenetre_max_{i}")

        vitesse_moyenne = 50
        for i in V:
            for j in C:
                if i != j:
                    for k in Vehicules:
                        temps_trajet = distances[i][j] / vitesse_moyenne * 60
                        service_i = temps_service[i - 1] if i > 0 else 0
                        self.model.addConstr(
                            t[j] >= t[i] + service_i + temps_trajet - M * (1 - x[i, j, k]),
                            name=f"temps_{i}_{j}_{k}"
                        )
        for i in V:
            for k in Vehicules:
                self.model.addConstr(x[i, i, k] == 0, name=f"no_loop_{i}_{k}")

        if danger_max_autorise is not None:
            for i in V:
                for j in V:
                    if i != j and niveaux_danger[i][j] > danger_max_autorise:
                        for k in Vehicules:
                            self.model.addConstr(x[i, j, k] == 0, name=f"danger_interdit_{i}_{j}_{k}")

        self.model.optimize()

        if self.model.Status == GRB.OPTIMAL:
            self.status = "OPTIMAL"
            tournees = {k: [] for k in Vehicules}
            for k in Vehicules:
                current = 0
                route = [0]
                visited = set([0])
                while True:
                    next_node = None
                    for j in V:
                        if j not in visited and x[current, j, k].X > 0.5:
                            next_node = j
                            break
                    if next_node is None:
                        route.append(0)
                        break
                    route.append(next_node)
                    visited.add(next_node)
                    current = next_node
                if len(route) > 2:
                    tournees[k] = route

            stats_tournees = {}
            for k, route in tournees.items():
                if len(route) > 2:
                    dist_totale = sum(distances[route[i]][route[i+1]] for i in range(len(route)-1))
                    danger_total = sum(niveaux_danger[route[i]][route[i+1]] for i in range(len(route)-1))
                    cout_variable = sum(couts[route[i]][route[i+1]] for i in range(len(route)-1))
                    stats_tournees[k] = {
                        'distance': dist_totale,
                        'danger_moyen': danger_total / (len(route) - 1),
                        'danger_total': danger_total,
                        'cout_variable': cout_variable,
                        'cout_fixe': cout_fixe_vehicule,
                        'cout_total': cout_variable + cout_fixe_vehicule
                    }

            self.solution = {
                'status': 'OPTIMAL',
                'cout_total': self.model.ObjVal,
                'tournees': tournees,
                'stats_tournees': stats_tournees,
                'vehicules_utilises': sum(1 for k in Vehicules if len(tournees[k]) > 2),
                'noms_clients': noms_clients or [f"Agence_{i}" for i in range(1, n + 1)],
                'cout_fixe_vehicule': cout_fixe_vehicule,
            }
        elif self.model.Status == GRB.INFEASIBLE:
            self.status = "INFEASIBLE"
            self.solution = {
                'status': 'INFAISABLE',
                'message': 'Aucune solution trouvée – contraintes impossibles à satisfaire'
            }
        else:
            self.status = "AUTRE"
            self.solution = {'status': 'ERREUR', 'message': f"Status Gurobi: {self.model.Status}"}

        return self.solution

# Optionnel : bloc de test ici si tu veux exécuter ce fichier en standalone
if __name__ == "__main__":
    print("Ce module s'utilise avec l'interface graphique (interface_vrp_tunisie.py)")