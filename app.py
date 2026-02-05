import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import polyline
import requests
import urllib.parse
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Ruta Nexa", page_icon="⛽", layout="centered")

# Título y Logo
st.title("⛽ Localizador Nexa")
st.markdown("Calcula tu ruta y encuentra la gasolinera sostenible más conveniente.")

# --- CARGA DE DATOS (Con caché para que vaya rápido) ---
@st.cache_data
def cargar_datos():
    # Asegúrate de que el archivo Excel esté en la misma carpeta que este script
    try:
        df = pd.read_excel("Estaciones_Nexa_Listas.xlsx")
        return df
    except:
        return None

df = cargar_datos()

if df is None:
    st.error("⚠️ No encuentro el archivo 'Estaciones_Nexa_Listas.xlsx'. Súbelo al repositorio.")
    st.stop()

# --- BARRA LATERAL (Inputs) ---
with st.sidebar:
    st.header("📍 Configura tu viaje")
    origen = st.text_input("Origen", "Madrid")
    destino = st.text_input("Destino", "Valencia")
    distancia_max = st.slider("Desvío máx. (km)", 1, 20, 5)
    buscar = st.button("🔍 Buscar Ruta")

# --- LÓGICA PRINCIPAL ---
if buscar:
    with st.spinner('Calculando ruta óptima...'):
        # 1. Geolocalización
        geolocator = Nominatim(user_agent="nexa_app_st", timeout=10)
        try:
            loc_org = geolocator.geocode(origen + ", España")
            loc_des = geolocator.geocode(destino + ", España")
            
            if not loc_org or not loc_des:
                st.error("❌ No encuentro esa ciudad. Intenta ser más específico.")
                st.stop()

            # 2. Ruta OSRM
            url = f"http://router.project-osrm.org/route/v1/driving/{loc_org.longitude},{loc_org.latitude};{loc_des.longitude},{loc_des.latitude}?overview=full"
            r = requests.get(url).json()
            
            if 'routes' not in r:
                 st.error("❌ No hay ruta por carretera posible.")
                 st.stop()

            trayecto = polyline.decode(r['routes'][0]['geometry'])
            punto_medio = trayecto[len(trayecto)//2]

            # 3. Crear Mapa
            m = folium.Map(location=punto_medio, zoom_start=6)
            folium.PolyLine(trayecto, color="#4285F4", weight=6, opacity=0.7).add_to(m)
            
            # Marcadores Origen/Destino
            folium.Marker([loc_org.latitude, loc_org.longitude], icon=folium.Icon(color='blue', icon='play')).add_to(m)
            folium.Marker([loc_des.latitude, loc_des.longitude], icon=folium.Icon(color='red', icon='flag')).add_to(m)

            # 4. Buscar Gasolineras
            c_lat, c_lon = 'LATITUD', 'LONGITUD'
            cols_txt = df.select_dtypes(include=['object']).columns
            c_nom = cols_txt[0] 
            c_dir = cols_txt[1]

            gasolineras_encontradas = 0
            puntos_ruta = trayecto[::30] 

            for _, fila in df.iterrows():
                pos_gas = (fila[c_lat], fila[c_lon])
                
                # Comprobar cercanía
                cerca = False
                for p in puntos_ruta:
                    if geodesic(pos_gas, p).km < distancia_max:
                        cerca = True
                        break
                
                if cerca:
                    gasolineras_encontradas += 1
                    
                    # Generar Link Google Maps
                    params = {
                        'origin': origen,
                        'destination': destino,
                        'waypoints': f"{fila[c_lat]},{fila[c_lon]}",
                        'travelmode': 'driving'
                    }
                    link_gmaps = f"https://www.google.com/maps/dir/?api=1&{urllib.parse.urlencode(params)}"

                    # Popup HTML con botón
                    html_popup = f"""
                    <div style='font-family:sans-serif; width:200px;'>
                        <b style='color:#2E7D32'>{fila[c_nom]}</b><br>
                        <span style='font-size:12px'>{fila[c_dir]}</span><br><br>
                        <a href='{link_gmaps}' target='_blank' 
                           style='background-color:#1a73e8; color:white; padding:8px; 
                                  text-decoration:none; border-radius:5px; display:block; text-align:center;'>
                           🚀 NAVEGAR
                        </a>
                    </div>
                    """
                    
                    folium.Marker(
                        location=pos_gas,
                        popup=folium.Popup(html_popup, max_width=250),
                        icon=folium.Icon(color='green', icon='leaf', prefix='fa')
                    ).add_to(m)

            # 5. Mostrar Resultados
            if gasolineras_encontradas > 0:
                st.success(f"✅ Se han encontrado {gasolineras_encontradas} estaciones Nexa en tu ruta.")
                # Renderizar mapa en Streamlit
                st_folium(m, width=700, height=500)
            else:
                st.warning(f"⚠️ No hay gasolineras a menos de {distancia_max} km de tu ruta.")
                st_folium(m, width=700, height=500)

        except Exception as e:
            st.error(f"Error: {e}")