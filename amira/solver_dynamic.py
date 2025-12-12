import numpy as np
from gurobipy import Model, GRB, quicksum
import pulp

# cette fonction résout le problème dynamique avec une approche STRICTE sur la couverture
# mais SOUPLE sur l'ouverture des hôpitaux (pour économiser le budget).
# paramètres:
# A: matrice de couverture (n adresses x m hôpitaux)
# p: probabilités d'indisponibilité pour chaque ambulance 
# budget: Montant total disponible pour l'achat des ambulances 
# cost_per_amb: Coût unitaire d'une ambulance
# min_per_hop: Minimum souhaité d'ambulances par hôpital (défaut=1)

def solve_dynamic_expected(A, p, budget=None, cost_per_amb=None, min_per_hop=1):
    
    n, m = A.shape #renvoie les dimensions de la matrice

    # Initialisation d'un modèle Gurobi vide
    model = Model('dynamic_expected_strict_coverage') 
    model.setParam('OutputFlag', 0) # Désactive le blabla technique dans la console

    # Variables de décision

    # x: nombre d'ambulances à placer à chaque hôpital
    # On remet lb=0 ici car si le budget est trop serré, 
    # le solveur doit avoir le droit de laisser un hôpital vide (x=0) en payant une pénalité.
    x = model.addVars(m, vtype=GRB.INTEGER, lb=0, name='x') 

    # e (Empty): Variable binaire de pénalité.
    # Vaut 1 si un hôpital est VIDE (ne possède pas d'ambulance).
    # Cela permet de "sacrifier" un hôpital pour respecter le budget.
    e = model.addVars(m, vtype=GRB.BINARY, name='e')

    # NOTE : La variable 'u' (non couvert) a été RETIRÉE.
    # La couverture est maintenant une contrainte stricte (Hard Constraint).

    # fonction objective

    # Objectif : Minimiser le nombre total d'ambulances + les Pénalités d'hôpitaux vides
    # On ne met plus de pénalité de couverture car la non-couverture est interdite.
    M2 = 10 # Poids moyen pour la pénalité "hôpital vide" (équité)

    objective = quicksum(x[j] for j in range(m)) + \
                (M2 * quicksum(e[j] for j in range(m)))

    model.setObjective(objective, GRB.MINIMIZE)
    # quicksum est une fonction de Gurobi pour sommer des expressions linéaires
    

    # CONTRAINTES 

    # A. Contrainte de Couverture (STRICTE)
    for i in range(n): 
        # La capacité doit être >= 1. Pas de "- u[i]".
        # C'est une obligation absolue de sécurité.
        # la capacité est la somme des ambulances placées dans les hôpitaux qui couvrent l'adresse i
        model.addConstr(sum(A[i,j] * (1-p[j]) * x[j] for j in range(m)) >= 1, name=f'cov_{i}')

    # B. Contrainte de Minimum par Hôpital (SOUPLE)
    if min_per_hop > 0:
        for j in range(m):
            # x[j] doit être >= 1, SAUF si e[j]=1 (pénalité payée).
            # Cela permet de fermer un hôpital si nécessaire.
            model.addConstr(x[j] >= min_per_hop - e[j], name=f'min_h_{j}')

    # C. Contrainte de Budget (STRICTE)
    # C'est la seule contrainte qu'on ne peut pas violer (on n'a pas l'argent magique).
    if budget is not None and cost_per_amb is not None and cost_per_amb > 0:
        total_cost = sum(x[j] * cost_per_amb for j in range(m))
        model.addConstr(total_cost <= budget, name='Budget_Limit')
    
    # Résolution du modèle
    model.optimize()

    # Recupération de la solution
    if model.status == GRB.OPTIMAL:
        # On récupère les valeurs de x
        x_sol = [int(x[j].x) for j in range(m)]
        # On renvoie x_sol et le nombre total d'ambulances
        return x_sol, int(sum(x_sol))
    else:
        # Si aucune solution n'est trouvée (Budget insuffisant pour couverture stricte)
        return None, None
    
    # Si une solution optimale est trouvée,
    # on extrait les valeurs pour savoir combien d'ambulances placer dans chaque hôpital
    # et on renvoie le résultat. Sinon, on signale l'échec.