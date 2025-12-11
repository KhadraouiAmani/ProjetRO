# solver_dynamic.py
import numpy as np
from gurobipy import Model, GRB, quicksum
import pulp

# cette fonction résout le problème dynamique avec une approche ROBUSTE (Soft Constraints)
# paramètres:
# A: matrice de couverture (n adresses x m hôpitaux)
# p: probabilités d'indisponibilité pour chaque ambulance 
# budget: Montant total disponible pour l'achat des ambulances 
# cost_per_amb: Coût unitaire d'une ambulance
# min_per_hop: Minimum souhaité d'ambulances par hôpital (défaut=1)

def solve_dynamic_expected(A, p, budget=None, cost_per_amb=None, min_per_hop=1):
    
    n, m = A.shape #renvoie les dimensions de la matrice

    # Initialisation d'un modèle Gurobi vide
    model = Model('dynamic_expected_robust') 
    model.setParam('OutputFlag', 0) # Désactive le blabla technique dans la console

    # Variables de décision

    # x: nombre d'ambulances à placer à chaque hôpital
    #  On remet lb=0 ici car si le budget est trop serré, 
    # le solveur doit avoir le droit de laisser un hôpital vide (x=0) en payant une pénalité,
    # plutôt que de dire "Impossible".
    x = model.addVars(m, vtype=GRB.INTEGER, lb=0, name='x') 

    # u (Uncovered): Variable binaire de pénalité. 
    # Vaut 1 si une adresse n'est PAS couverte (faute de budget).
    u = model.addVars(n, vtype=GRB.BINARY, name='u')

    # e (Empty): Variable binaire de pénalité.
    # Vaut 1 si un hôpital est VIDE== ne possede pas d ambulance 
    e = model.addVars(m, vtype=GRB.BINARY, name='e')

    # fonction objective

    # Objectif : Minimiser le nombre total d'ambulances + les Pénalités
    # On donne un poids très lourd (M1=1000) au fait de ne pas couvrir un patient.
    # On donne un poids moyen (M2=10) au fait de laisser un hôpital vide.
    M1 = 1000
    M2 = 10

    objective = quicksum(x[j] for j in range(m)) + \
                (M1 * quicksum(u[i] for i in range(n))) + \
                (M2 * quicksum(e[j] for j in range(m)))

    model.setObjective(objective, GRB.MINIMIZE)
    #quicksum est une fonction de Gurobi pour sommer des expressions linéaires
    

    #CONTRAINTES 

    # A. Contrainte de Couverture 
    for i in range(n): 
        # La capacité doit être >= 1, SAUF si u[i]=1 (pénalité payée)
        #la capacité est la somme des ambulances placées dans les hôpitaux qui couvrent l'adresse i
        # Si u[i]=1, alors (1 - u[i]) = 0, donc la contrainte disparait.

        model.addConstr(sum(A[i,j] * (1-p[j]) * x[j] for j in range(m)) >= 1 - u[i], name=f'cov_{i}')

    # B. Contrainte de Minimum par Hôpital 
    if min_per_hop > 0:
        for j in range(m):
            # x[j] doit être >= 1, SAUF si e[j]=1 (pénalité payée).
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
        # On renvoie x_sol et le nombre total d'ambulances (sans les pénalités mathématiques)
        return x_sol, int(sum(x_sol))
    else:
        return None, None
    
    # Si une solution optimale est trouvée (même dégradée par manque de budget),
    # on extrait les valeurs pour savoir combien d'ambulances placer dans chaque hôpital
    # et on renvoie le résultat.