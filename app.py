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

st.title("⛽ Localizador Nexa")
st.markdown("Calcula tu ruta y encuentra la gasolinera sostenible más conveniente.")

# --- INICIALIZAR MEMORIA (SESSION STATE) ---
# Esto evita que el mapa desaparezca al interactuar con él
if 'mapa_actual' not in st.session_state:
    st.session_state.mapa_actual = None
if 'mensaje_resultado' not in st.session_state:
    st.session_state.mensaje_resultado = None
if 'tipo_mensaje' not in st.session_state:
    st.session_state.tipo_mensaje = None

# --- CARGA DE DATOS ---
@st.cache_data
def cargar_datos():
    try:
        df = pd.read_excel("Estaciones_Nexa_Listas.xlsx")
        return df
    except:
        return None

df = cargar_datos()

if df is None:
    st.error("⚠️ No encuentro el archivo 'Estaciones_Nexa_Listas.xlsx'. Súbelo al repositorio de GitHub.")
    st.stop()

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("📍 Configura tu viaje")
    origen = st.text_input("Origen", "Madrid")
    destino = st.text_input("Destino", "Valencia")
    distancia_max = st.slider("Desvío máx. (km)", 1, 20, 5)
    
    # El botón activa el cálculo
    boton_buscar = st.button("🔍 Buscar Ruta")

# --- LÓGICA DE CÁLCULO (Solo se ejecuta si pulsas el botón) ---
if boton_buscar:
    with st.spinner('Calculando ruta y buscando gasolineras...'):
        geolocator = Nominatim(user_agent="nexa_app_st_fix", timeout=10)
        try:
            # 1. Geolocalizar
            loc_org = geolocator.geocode(origen + ", España")
            loc_des = geolocator.geocode(destino + ", España")
            
            if not loc_org or not loc_des:
                st.session_state.tipo_mensaje = "error"
                st.session_state.mensaje_resultado = "❌ No encuentro esa ciudad. Prueba a añadir la provincia."
                st.session_state.mapa_actual = None # Borramos mapa anterior si hay error
            
            else:
                # 2. Obtener Ruta OSRM
                url = f"http://router.project-osrm.org/route/v1/driving/{loc_org.longitude},{loc_org.latitude};{loc_des.longitude},{loc_des.latitude}?overview=full"
                r = requests.get(url).json()
                
                if 'routes' not in r:
                    st.session_state.tipo_mensaje = "error"
                    st.session_state.mensaje_resultado = "❌ No hay ruta por carretera posible entre estos puntos."
                    st.session_state.mapa_actual = None
                else:
                    trayecto = polyline.decode(r['routes'][0]['geometry'])
                    punto_medio = trayecto[len(trayecto)//2]

                    # 3. Crear el Mapa (Objeto Folium)
                    m = folium.Map(location=punto_medio, zoom_start=6)
                    folium.PolyLine(trayecto, color="#4285F4", weight=6, opacity=0.7).add_to(m)
                    
                    folium.Marker([loc_org.latitude, loc_org.longitude], popup="Salida", icon=folium.Icon(color='blue', icon='play')).add_to(m)
                    folium.Marker([loc_des.latitude, loc_des.longitude], popup="Destino", icon=folium.Icon(color='red', icon='flag')).add_to(m)

                    # 4. Buscar Gasolineras
                    c_lat, c_lon = 'LATITUD', 'LONGITUD'
                    cols_txt = df.select_dtypes(include=['object']).columns
                    c_nom = cols_txt[0] 
                    c_dir = cols_txt[1]

                    count = 0
                    puntos_ruta = trayecto[::30] 

                    # Pre-calculamos strings de URL para velocidad
                    orig_s = urllib.parse.quote(origen)
                    dest_s = urllib.parse.quote(destino)

                    for _, fila in df.iterrows():
                        pos_gas = (fila[c_lat], fila[c_lon])
                        
                        # Filtro distancia
                        cerca = False
                        for p in puntos_ruta:
                            if geodesic(pos_gas, p).km < distancia_max:
                                cerca = True
                                break
                        
                        if cerca:
                            count += 1
                            
                            # Link Google Maps Universal
                            params = {
                                'origin': origen,
                                'destination': destino,
                                'waypoints': f"{fila[c_lat]},{fila[c_lon]}",
                                'travelmode': 'driving'
                            }
                            link_gmaps = f"https://www.google.com/maps/dir/?api=1?{urllib.parse.urlencode(params)}"

                            html_popup = f"""
                            <div style='font-family:sans-serif; width:200px;'>
                                <b style='color:#2E7D32'>{fila[c_nom]}</b><br>
                                <span style='font-size:12px'>{fila[c_dir]}</span><br><br>
                                <a href='{link_gmaps}' target='_blank' 
                                   style='background-color:#1a73e8; color:white; padding:8px 15px; 
                                          text-decoration:none; border-radius:20px; display:block; text-align:center; font-weight:bold;'>
                                   🚀 NAVEGAR
                                </a>
                            </div>
                            """
                            
                            folium.Marker(
                                location=pos_gas,
                                popup=folium.Popup(html_popup, max_width=250),
                                icon=folium.Icon(color='green', icon='leaf', prefix='fa')
                            ).add_to(m)

                    # 5. GUARDAR TODO EN MEMORIA (SESSION STATE)
                    st.session_state.mapa_actual = m
                    
                    if count > 0:
                        st.session_state.tipo_mensaje = "success"
                        st.session_state.mensaje_resultado = f"✅ Ruta calculada: {count} estaciones Nexa encontradas."
                    else:
                        st.session_state.tipo_mensaje = "warning"
                        st.session_state.mensaje_resultado = f"⚠️ Ruta calculada, pero no hay gasolineras a menos de {distancia_max} km."

        except Exception as e:
            st.session_state.tipo_mensaje = "error"
            st.session_state.mensaje_resultado = f"Error inesperado: {str(e)}"

# --- VISUALIZACIÓN FINAL (Se ejecuta siempre, leyendo de la memoria) ---

# 1. Mostrar mensajes si existen
if st.session_state.mensaje_resultado:
    if st.session_state.tipo_mensaje == "error":
        st.error(st.session_state.mensaje_resultado)
    elif st.session_state.tipo_mensaje == "warning":
        st.warning(st.session_state.mensaje_resultado)
    else:
        st.success(st.session_state.mensaje_resultado)

# 2. Mostrar mapa si existe en memoria
if st.session_state.mapa_actual is not None:
    st_folium(st.session_state.mapa_actual, width=700, height=500)