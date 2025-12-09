# map_utils.py
import folium
from folium.plugins import MarkerCluster


def create_map(addrs, hospitals, x_sol, missions=None, mapfile='map.html'):
    center = addrs[0] if addrs else (0,0)
    m = folium.Map(location=center, zoom_start=13)
    mc = MarkerCluster().add_to(m)
    for i,(la,lo) in enumerate(addrs):
        folium.Marker((la,lo), popup=f'Adresse {i}', icon=folium.Icon(color='blue', icon='home')).add_to(mc)
    for j,(hla,hlo) in enumerate(hospitals):
        folium.Marker((hla,hlo), popup=f'Hôpital {j} ({x_sol[j]} ambulances)', icon=folium.Icon(color='red', icon='plus-sign')).add_to(m)
    if missions:
        for mission in missions:
            folium.PolyLine(mission['path']).add_to(m)
    m.save(mapfile)
    return mapfile