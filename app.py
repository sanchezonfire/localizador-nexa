import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import polyline
import requests
import urllib.parse
from geopy.geocoders import ArcGIS 
from geopy.distance import geodesic

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Ruta Nexa", page_icon="⛽", layout="wide")

st.title("⛽ Localizador Nexa")

# --- CARGA DE DATOS ---
@st.cache_data
def cargar_datos():
    # CAMBIA ESTO POR EL NOMBRE DE TU NUEVO ARCHIVO
    archivo = "Estaciones_Nexa_CORREGIDAS.xlsx" 
    try:
        df = pd.read_excel(archivo)
        # Limpieza robusta de coordenadas
        df['LATITUD'] = pd.to_numeric(df['LATITUD'], errors='coerce')
        df['LONGITUD'] = pd.to_numeric(df['LONGITUD'], errors='coerce')
        df = df.dropna(subset=['LATITUD', 'LONGITUD'])
        return df
    except FileNotFoundError:
        st.error(f"⚠️ No encuentro el archivo '{archivo}'. Súbelo al repositorio.")
        return None

df = cargar_datos()

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("📍 Tu Viaje")
    origen = st.text_input("Origen", "Madrid")
    destino = st.text_input("Destino", "Valencia")
    distancia_max = st.slider("Desvío máx. (km)", 1, 50, 10, help="Distancia máxima desde la carretera a la gasolinera")
    buscar = st.button("🔍 Buscar Ruta", type="primary")

# --- LÓGICA ---
if buscar and df is not None:
    with st.spinner('Calculando ruta óptima...'):
        geolocator = ArcGIS(timeout=10)
        
        # 1. Geolocalizar puntos
        try:
            loc_org = geolocator.geocode(origen + ", España")
            loc_des = geolocator.geocode(destino + ", España")
            
            if not loc_org or not loc_des:
                st.error("❌ No encuentro una de las ciudades. Intenta ser más específico.")
                st.stop()

            # 2. Obtener Ruta (OSRM)
            url = f"http://router.project-osrm.org/route/v1/driving/{loc_org.longitude},{loc_org.latitude};{loc_des.longitude},{loc_des.latitude}?overview=full"
            r = requests.get(url, headers={'User-Agent': 'NexaApp/1.0'}).json()
            
            if 'routes' not in r:
                st.error("❌ No se encontró ruta por carretera.")
                st.stop()

            trayecto = polyline.decode(r['routes'][0]['geometry'])
            
            # 3. Filtrar Gasolineras
            # Optimizacion: Creamos una lista de puntos de la ruta para comparar
            # Reducimos la resolución de la ruta para que el cálculo sea rápido (1 de cada 20 puntos)
            puntos_ruta_simplificados = trayecto[::20] 
            
            gasolineras_validas = []
            
            for _, fila in df.iterrows():
                coords_gas = (fila['LATITUD'], fila['LONGITUD'])
                
                # Comprobar si está cerca de ALGÚN punto de la ruta
                # Usamos una lógica rápida: primero descartamos por "caja" (lat/lon) y luego calculamos distancia real
                es_valida = False
                for p in puntos_ruta_simplificados:
                    # Cálculo rápido aproximado antes de hacer el geodésico exacto
                    if abs(coords_gas[0] - p[0]) < 0.5 and abs(coords_gas[1] - p[1]) < 0.5:
                        if geodesic(coords_gas, p).km <= distancia_max:
                            es_valida = True
                            break
                
                if es_valida:
                    gasolineras_validas.append(fila)
            
            # 4. Pintar Mapa
            # Centramos el mapa para ver todo el trayecto
            m = folium.Map(location=[loc_org.latitude, loc_org.longitude], zoom_start=6)
            folium.PolyLine(trayecto, color="#3b82f6", weight=5, opacity=0.7).add_to(m)
            
            # Marcadores Inicio/Fin
            folium.Marker([loc_org.latitude, loc_org.longitude], icon=folium.Icon(color='blue', icon='play'), popup="Origen").add_to(m)
            folium.Marker([loc_des.latitude, loc_des.longitude], icon=folium.Icon(color='red', icon='flag'), popup="Destino").add_to(m)

            # Marcadores Gasolineras
            for fila in gasolineras_validas:
                # Link Google Maps
                gmaps_link = f"https://www.google.com/maps/dir/?api=1&origin={urllib.parse.quote(origen)}&destination={urllib.parse.quote(destino)}&waypoints={fila['LATITUD']},{fila['LONGITUD']}&travelmode=driving"
                
                html = f"""
                <div style="font-family:sans-serif; width:200px">
                    <b>{fila.get('Nombre Estación', 'Gasolinera Nexa')}</b><br>
                    <span style="font-size:12px">{fila.get('Dirección', '')}</span><br>
                    <a href="{gmaps_link}" target="_blank" style="display:block; background:#16a34a; color:white; text-align:center; padding:5px; border-radius:5px; margin-top:5px; text-decoration:none;">🚀 Navegar</a>
                </div>
                """
                
                folium.Marker(
                    [fila['LATITUD'], fila['LONGITUD']],
                    popup=folium.Popup(html, max_width=250),
                    icon=folium.Icon(color='green', icon='leaf', prefix='fa')
                ).add_to(m)

            # Ajustar zoom para ver todos los puntos
            puntos_a_mostrar = [[loc_org.latitude, loc_org.longitude], [loc_des.latitude, loc_des.longitude]]
            if gasolineras_validas:
                puntos_a_mostrar.extend([[g['LATITUD'], g['LONGITUD']] for g in gasolineras_validas])
            m.fit_bounds(puntos_a_mostrar)

            # Mostrar resultados
            st.success(f"✅ Encontradas {len(gasolineras_validas)} gasolineras en tu ruta.")
            folium_static(m, width=None, height=500)

        except Exception as e:
            st.error(f"Error: {e}")
