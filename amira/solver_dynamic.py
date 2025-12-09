# solver_dynamic.py
import numpy as np
from gurobipy import Model, GRB
import pulp


    # cette fonction résout le problème dynamique avec la méthode des scénarios
    #paramètres:
    # A: matrice de couverture (n adresses x m hôpitaux)
    # p: probabilités d'indisponibilité pour chaque hôpital 
    # capacities: liste des capacités maximales pour chaque hôpital 
    # K: contrainte sur le nombre total d'ambulances à déployer 

def solve_dynamic_expected(A, p, capacities=None, K=None):
    
    n, m = A.shape #renvoie les dimensions de la matrice

    #Initialisation d'un modèle Gurobi vide
    model = Model('dynamic_expected') 

    #variables de decision: x: nombre d'ambulances à placer à chaque hôpital
    x = model.addVars(m, vtype=GRB.INTEGER, lb=0, name='x')  #on impose le type entier car cest un plne

    # Objectif : Minimiser le nombre total d'ambulances
    model.setObjective(sum(x[j] for j in range(m)), GRB.MINIMIZE)
    

    # Contraintes 
    for i in range(n): #contraintes de couverture
        model.addConstr(sum(A[i,j] * (1-p[j]) * x[j] for j in range(m)) >= 1, name=f'cov_{i}')

        # Contraintes de capacité si fournies
    if capacities is not None:
        for j in range(m):
            model.addConstr(x[j] <= capacities[j], name=f'cap_{j}')
    if K is not None:
        model.addConstr(sum(x[j] for j in range(m)) <= K, name='totalK')
    
    # Résolution du modèle
    model.optimize()

    #recupération de la solution
    if model.status == GRB.OPTIMAL:
        x_sol = [int(x[j].x) for j in range(m)]
        return x_sol, int(model.objVal)
    else:
     return None, None
    
    #Si une solution optimale est trouvée,
    #  on extrait les valeurs pour savoir combien d'ambulances placer dans chaque hôpital
    #  et on renvoie le résultat. Sinon, on signale l'échec. 
   