# build_A_dynamic.py

#Rôle global :
# transforme des coordonnées GPS brutes (Latitude/Longitude) en matrices mathématiques exploitables 

import numpy as np           #pour les calculs matriciels
import pandas as pd          #pour la lecture des fichiers CSV
from math import radians, sin, cos, sqrt, atan2
R = 6371.0  # rayon de la Terre en km


#
def haversine_km(lat1, lon1, lat2, lon2):
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    # formule haversine
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c



#charge les données 
#et extrait les coordonnées GPS sous forme de liste.
def read_coords_csv(path):
    df = pd.read_csv(path, header=None)
    if df.shape[1] >= 3:
       coords = [(float(r[1]), float(r[2])) for _, r in df.iterrows()] # liste de tuples (lat, lon)
    else:
        raise ValueError('CSV doit avoir au moins 3 colonnes: id, lat, lon')
    return coords




#construit les matrices A, dist, times
def build_matrices(addrs, hospitals, vmax_kmh=40, Tmax_min=10):
    n = len(addrs)  #nombre d'adresses
    m = len(hospitals)   #nombre d'hôpitaux
    dist = np.zeros((n,m), dtype=float) # matrice des distances en km
    times = np.zeros((n,m), dtype=float)  # matrice des temps en minutes
    A = np.zeros((n,m), dtype=int)    # matrice de couverture binaire
    for i,(la,lo) in enumerate(addrs):
      for j,(hs_la,hs_lo) in enumerate(hospitals):
         d = haversine_km(la, lo, hs_la, hs_lo)
         t = (d / vmax_kmh) * 60.0  # temps en minutes
         dist[i,j] = d
         times[i,j] = t
         A[i,j] = 1 if t <= Tmax_min else 0
    return A, dist, times




def save_matrices(A, dist, times, prefix='output'):   #sauvegarde les matrices dans des fichiers CSV
    np.savetxt(f'{prefix}_A.csv', A, fmt='%d', delimiter=',')
    np.savetxt(f'{prefix}_dist.csv', dist, fmt='%.6f', delimiter=',')
    np.savetxt(f'{prefix}_times.csv', times, fmt='%.6f', delimiter=',')




if __name__ == '__main__':
    addrs = read_coords_csv('sample_addresses.csv')
    hospitals = read_coords_csv('sample_hospitals.csv')
    A, dist, times = build_matrices(addrs, hospitals, vmax_kmh=40, Tmax_min=10)
    save_matrices(A, dist, times, prefix='A_output')
    print('Matrices saved: A_output_A.csv, A_output_dist.csv, A_output_times.csv')