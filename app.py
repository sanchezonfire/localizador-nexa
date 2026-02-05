import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import polyline
import requests
import urllib.parse
from geopy.geocoders import ArcGIS 
from geopy.distance import geodesic

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Ruta Nexa", page_icon="⛽", layout="centered")

st.title("⛽ Localizador Nexa")
st.markdown("Calcula tu ruta y encuentra la gasolinera sostenible más conveniente.")

# --- MEMORIA (SESSION STATE) ---
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
        
        # --- CORRECCIÓN CRÍTICA DE COORDENADAS ---
        # 1. Buscamos columnas de latitud/longitud
        c_lat = next((c for c in df.columns if 'LAT' in c.upper()), 'LATITUD')
        c_lon = next((c for c in df.columns if 'LON' in c.upper()), 'LONGITUD')
        
        # 2. Forzamos a que sean números puros (eliminamos errores)
        df[c_lat] = pd.to_numeric(df[c_lat], errors='coerce')
        df[c_lon] = pd.to_numeric(df[c_lon], errors='coerce')
        
        # 3. Eliminamos filas vacías
        df = df.dropna(subset=[c_lat, c_lon])
        
        return df, c_lat, c_lon
    except Exception as e:
        return None, None, None

df, c_lat, c_lon = cargar_datos()

if df is None:
    st.error("⚠️ Error cargando 'Estaciones_Nexa_Listas.xlsx'. Revisa que el archivo esté en GitHub.")
    st.stop()

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("📍 Configura tu viaje")
    origen = st.text_input("Origen", "Madrid")
    destino = st.text_input("Destino", "Valencia")
    distancia_max = st.slider("Desvío máx. (km)", 1, 20, 5)
    boton_buscar = st.button("🔍 Buscar Ruta")

# --- LÓGICA PRINCIPAL ---
if boton_buscar:
    with st.spinner('Calculando ruta...'):
        geolocator = ArcGIS(timeout=10)
        
        try:
            # 1. Geolocalizar
            loc_org = geolocator.geocode(origen + ", España")
            loc_des = geolocator.geocode(destino + ", España")
            
            if not loc_org or not loc_des:
                st.session_state.tipo_mensaje = "error"
                st.session_state.mensaje_resultado = "❌ No encuentro esa ciudad."
                st.session_state.mapa_actual = None
            
            else:
                # 2. Ruta OSRM
                url = f"http://router.project-osrm.org/route/v1/driving/{loc_org.longitude},{loc_org.latitude};{loc_des.longitude},{loc_des.latitude}?overview=full"
                headers = {'User-Agent': 'NexaLocatorApp/1.0'}
                
                try:
                    r = requests.get(url, headers=headers).json()
                except:
                     r = {} 
                
                if 'routes' not in r:
                    st.session_state.tipo_mensaje = "error"
                    st.session_state.mensaje_resultado = "❌ No hay ruta por carretera."
                    st.session_state.mapa_actual = None
                else:
                    trayecto = polyline.decode(r['routes'][0]['geometry'])
                    
                    # 3. Crear el Mapa (Centrado automático)
                    m = folium.Map(location=[loc_org.latitude, loc_org.longitude], zoom_start=6)
                    
                    # Dibujar ruta
                    folium.PolyLine(trayecto, color="#4285F4", weight=6, opacity=0.7).add_to(m)
                    
                    # Marcadores Inicio/Fin
                    folium.Marker([loc_org.latitude, loc_org.longitude], popup="Salida", icon=folium.Icon(color='blue', icon='play')).add_to(m)
                    folium.Marker([loc_des.latitude, loc_des.longitude], popup="Destino", icon=folium.Icon(color='red', icon='flag')).add_to(m)

                    # 4. Buscar Gasolineras
                    cols_txt = df.select_dtypes(include=['object']).columns
                    c_nom = cols_txt[0] 
                    c_dir = cols_txt[1]

                    count = 0
                    puntos_ruta = trayecto[::30] 
                    
                    # Lista para auto-ajustar el zoom
                    puntos_interes = [[loc_org.latitude, loc_org.longitude], [loc_des.latitude, loc_des.longitude]]

                    for _, fila in df.iterrows():
                        # Aseguramos conversión a float puro de Python (clave para que se vean)
                        lat_gas = float(fila[c_lat])
                        lon_gas = float(fila[c_lon])
                        pos_gas = (lat_gas, lon_gas)
                        
                        cerca = False
                        for p in puntos_ruta:
                            if geodesic(pos_gas, p).km < distancia_max:
                                cerca = True
                                break
                        
                        if cerca:
                            count += 1
                            puntos_interes.append([lat_gas, lon_gas])
                            
                            # Enlace Google Maps
                            params = {
                                'origin': origen,
                                'destination': destino,
                                'waypoints': f"{lat_gas},{lon_gas}",
                                'travelmode': 'driving'
                            }
                            # Enlace formato universal
                            link_gmaps = f"https://www.google.com/maps/dir/?api=1?{urllib.parse.urlencode(params)}"

                            html_popup = f"""
                            <div style='font-family:sans-serif; width:200px;'>
                                <b style='color:#2E7D32'>{fila[c_nom]}</b><br>
                                <span style='font-size:12px'>{fila[c_dir]}</span><br><br>
                                <a href='{link_gmaps}' target='_blank' 
                                   style='background-color:#1a73e8; color:white; padding:8px 15px; 
                                          text-decoration:none; border-radius:8px; display:block; text-align:center; font-weight:bold;'>
                                   🚀 ABRIR EN MAPS
                                </a>
                            </div>
                            """
                            
                            folium.Marker(
                                location=[lat_gas, lon_gas],
                                popup=folium.Popup(html_popup, max_width=250),
                                icon=folium.Icon(color='green', icon='leaf', prefix='fa')
                            ).add_to(m)

                    # Auto-ajustar zoom para ver todo
                    if puntos_interes:
                        m.fit_bounds(puntos_interes)

                    st.session_state.mapa_actual = m
                    
                    if count > 0:
                        st.session_state.tipo_mensaje = "success"
                        st.session_state.mensaje_resultado = f"✅ Ruta calculada: {count} estaciones encontradas."
                    else:
                        st.session_state.tipo_mensaje = "warning"
                        st.session_state.mensaje_resultado = f"⚠️ No hay gasolineras a menos de {distancia_max} km."

        except Exception as e:
            st.session_state.tipo_mensaje = "error"
            st.session_state.mensaje_resultado = f"Error: {str(e)}"

# --- VISUALIZACIÓN FINAL ---
if st.session_state.mensaje_resultado:
    if st.session_state.tipo_mensaje == "error":
        st.error(st.session_state.mensaje_resultado)
    elif st.session_state.tipo_mensaje == "warning":
        st.warning(st.session_state.mensaje_resultado)
    else:
        st.success(st.session_state.mensaje_resultado)

if st.session_state.mapa_actual is not None:
    folium_static(st.session_state.mapa_actual, width=700, height=500)
