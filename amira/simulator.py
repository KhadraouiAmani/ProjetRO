# simulator.py
import heapq #pour la gestion de la file d'événements
import random #pour la génération de nombres aléatoires
import numpy as np


class Mission:
    #Un simple objet pour stocker les infos d'un trajet (ID, heure début, heure fin)
    def __init__(self, id, addr_idx, hop_idx, start_time, end_time):
        self.id = id
        self.addr_idx = addr_idx
        self.hop_idx = hop_idx
        self.start_time = start_time
        self.end_time = end_time


class Simulator:
    #on intialise le simulateur avec les matrices A, dist, times, la solution initiale x_initial, et une graine aléatoire
    def __init__(self, A, dist_matrix, times_matrix, x_initial, seed=0):
        self.A = A
        self.dist = dist_matrix
        self.times = times_matrix
        self.x = list(x_initial)
        #l'état des stocks. Si x_initial (la solution de Gurobi) dit qu'il y a 2 ambulances à l'hôpital 0, available[0] sera [0, 1]
        self.available = [list(range(x_initial[j])) for j in range(len(x_initial))]
        self.busy = {j: {} for j in range(len(x_initial))}
        self.event_q = []  #file d'événements
        self.clock = 0.0  #horloge virtuelle du simulateur
        self.next_mission_id = 1  #ID unique pour chaque mission
        self.missions_log = []   #journal des missions
        random.seed(seed)    #initialisation de la graine aléatoire




    def schedule_event(self, time, func, *args):
        heapq.heappush(self.event_q, (time, func, args))
        #Cette fonction insère un événement futur dans la chronologie 
        # sans désordonner la file d'attente

#horizon représente la durée totale de la simulation.

#génération des Appels
#On simule l'arrivée des appels d'urgence selon une loi de Poisson,
#  ce qui est le standard pour modéliser des flux aléatoires d'événements indépendants.
    def generate_arrival(self, rate_lambda, horizon):
        t = 0.0  #on initialise l'horloge locale a 0
        while t < horizon:   #tant que l'horloge locale est inférieure à l'horizon
            u = random.random() #On tire un nombre aléatoire uniforme entre 0 et 1
            inter = -np.log(u) / rate_lambda
            t += inter #on calcule le temps d'attente jusqu'au prochain appel
            if t >= horizon: break #si on dépasse l'horizon, on arrête
            self.schedule_event(t, self.handle_arrival, None)


#traitement d'appel 
    def handle_arrival(self, _):
        n_addr = self.A.shape[0]
        #Choix d'une adresse 
        addr = random.randrange(n_addr)

        #Trouver les hôpitaux candidats disponibles
        candidates = []
        for j in range(self.A.shape[1]):
         # Condition A : L'hôpital couvre l'adresse (temps < Tmax)
          # Condition B : L'hôpital a au moins une ambulance libre
         if self.A[addr,j] == 1 and len(self.available[j]) > 0:
            t_reach = self.times[addr,j]
            candidates.append((t_reach, j))

            # Cas d'échec (Aucune ambulance dispo ou zone non couverte)
        if not candidates:
            self.missions_log.append({'time': self.clock, 'addr': addr, 'served': False})
            return
        
        # Choix du meilleur hôpital (plus proche en temps)
        candidates.sort()   #trie par temps croissant
        t_reach, chosen_hop = candidates[0]

        #allocation de l'ambulance et planification de la mission
        amb_id = self.available[chosen_hop].pop(0) #on retire la première ambulance dispo du stock
       
        #Calcul de la durée de service (Trajet Aller + Soins + Retour)
        service = random.expovariate(1/20.0)  

        end_time = self.clock + t_reach + service + t_reach #retour a l'hôpital

        mission = Mission(self.next_mission_id, addr, chosen_hop, self.clock, end_time)
        self.next_mission_id += 1 #ID unique pour la mission 
        # Marquer l'ambulance comme occupée
        self.busy[chosen_hop][amb_id] = mission

        # Planification de la libération de l'ambulance
        self.schedule_event(end_time, self.finish_mission, chosen_hop, amb_id, mission)
        self.missions_log.append({'time': self.clock, 'addr': addr, 'served': True, 'hop': chosen_hop, 'start': self.clock, 'expected_end': end_time})


#L'ambulance est libérée et redevient immédiatement disponible pour une nouvelle mission
    def finish_mission(self, hop_idx, amb_id, mission):
        del self.busy[hop_idx][amb_id]
        self.available[hop_idx].append(amb_id)
        self.missions_log.append({'time': self.clock, 'completed': True, 'mission_id': mission.id, 'hop': hop_idx})



#Tant qu'il y a des événements, on prend le prochain, 
# on avance l'heure (self.clock) à cet instant, et on exécute la fonction associée (handle_arrival ou finish_mission).
    def run(self, horizon):
        while self.event_q:
            time, func, args = heapq.heappop(self.event_q)
            self.clock = time
            func(*args)
        return self.missions_log