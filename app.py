import os
import cv2
import numpy as np
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

# 1. Load environment variables (opsional, untuk Google Maps API Key)
load_dotenv()
DEFAULT_GMAP_API_KEY = os.getenv("GMAP_API_KEY", "")

# 2. Set default session state
if "camera_active" not in st.session_state:
    st.session_state.camera_active = False
if "last_frame_rating" not in st.session_state:
    st.session_state.last_frame_rating = 5.0  # Dummy rating awal
if "current_lat" not in st.session_state:
    st.session_state.current_lat = -6.1753924  # Default Monas
if "current_lon" not in st.session_state:
    st.session_state.current_lon = 106.827153

# 3. Fungsi: Dummy klasifikasi jalan
def classify_road_condition(frame: np.ndarray) -> float:
    """Kembalikan rating 0..10 berdasarkan brightness rata-rata frame."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    avg_brightness = np.mean(gray)
    rating = (avg_brightness / 255) * 10
    return rating

# 4. Fungsi: Generate HTML peta Google Maps
def generate_gmap_html(lat, lon, rating, api_key):
    """Kembalikan HTML Google Maps dengan marker warna tergantung rating."""
    color = "red" if rating < 5 else "green"
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Road Condition Map</title>
        <style>
          #map {{
            height: 100%;
            width: 100%;
          }}
          html, body {{
            height: 100%;
            margin: 0;
            padding: 0;
          }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        <script>
          function initMap() {{
            var myLatLng = {{lat: {lat}, lng: {lon}}};
            var map = new google.maps.Map(document.getElementById('map'), {{
              zoom: 17,
              center: myLatLng
            }});
            
            var rating = {rating:.2f};
            var color = '{color}';

            var marker = new google.maps.Marker({{
                position: myLatLng,
                map: map,
                label: {{
                  text: rating.toFixed(1),
                  color: 'white'
                }},
                icon: {{
                    path: google.maps.SymbolPath.CIRCLE,
                    scale: 12,
                    fillColor: color,
                    fillOpacity: 1,
                    strokeWeight: 2,
                    strokeColor: 'white'
                }}
            }});
          }}
        </script>
        <script async
        src="https://maps.googleapis.com/maps/api/js?key={api_key}&callback=initMap">
        </script>
    </body>
    </html>
    """
    return html_code

# 5. Tombol kamera
def start_camera():
    st.session_state.camera_active = True

def stop_camera():
    st.session_state.camera_active = False

# 6. Main aplikasi Streamlit
def main():
    st.title("Demo/Prototipe - AI Klasifikasi Jalan Subang")

    # -- Sidebar untuk input API Key
    st.sidebar.header("Konfigurasi API Key")
    gmap_api_key = st.sidebar.text_input("Google Maps API Key", value=DEFAULT_GMAP_API_KEY)
    if not gmap_api_key:
        st.sidebar.warning("Masukkan API Key agar peta dapat ditampilkan.")

    # -- Input koordinat manual
    st.markdown("### Input Lokasi (Latitude & Longitude)")
    lat_input = st.text_input("Latitude", value=str(st.session_state.current_lat))
    lon_input = st.text_input("Longitude", value=str(st.session_state.current_lon))

    # -- Update koordinat saat tombol ditekan
    if st.button("Update Lokasi"):
        try:
            st.session_state.current_lat = float(lat_input)
            st.session_state.current_lon = float(lon_input)
            st.success(f"Lokasi berhasil diperbarui ke: lat={lat_input}, lon={lon_input}")
        except ValueError:
            st.error("Latitude atau Longitude tidak valid. Masukkan angka desimal yang benar.")

    # -- Tombol Start/Stop Kamera
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.button("Start Kamera", on_click=start_camera, key="start_btn")
    with col2:
        st.button("Stop Kamera", on_click=stop_camera, key="stop_btn")

    # -- Tampilkan video kamera (jika aktif)
    FRAME_WINDOW = st.empty()
    snapshot = st.checkbox("Tangkap Snapshot")

    if st.session_state.camera_active:
        cap = cv2.VideoCapture(0)
        ret, frame = cap.read()
        if ret:
            frame = cv2.flip(frame, 1)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            FRAME_WINDOW.image(frame_rgb, channels="RGB")

            if snapshot:
                rating = classify_road_condition(frame)
                st.session_state.last_frame_rating = rating
                st.success(f"Rating jalan (snapshot): {rating:.2f}")
        else:
            st.error("Tidak dapat mengakses kamera.")
        cap.release()
    else:
        st.info("Kamera tidak aktif.")

    # -- Tampilkan peta Google Maps
    st.markdown("---")
    st.header("Peta Kondisi Jalan")
    if gmap_api_key:
        rating_val = st.session_state.last_frame_rating
        map_html = generate_gmap_html(
            st.session_state.current_lat,
            st.session_state.current_lon,
            rating_val,
            gmap_api_key,
        )
        components.html(map_html, height=500)
    else:
        st.warning("Masukkan API Key untuk memunculkan peta.")

if __name__ == "__main__":
    main()
