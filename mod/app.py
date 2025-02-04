import os
import json
import random
import time
import cv2
import numpy as np
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

# ----------------------------------------------------------
# 1. Load Google Maps API Key (opsional) dari .env
load_dotenv()
DEFAULT_GMAP_API_KEY = os.getenv("GMAP_API_KEY", "")

# URL IP Kamera (sesuai dengan IP Webcam HP Anda)
IP_CAMERA_URL = "http://192.168.0.100:8080/video"  # URL live feed kamera HP

# ----------------------------------------------------------
# 2. Inisialisasi Session State
if "path" not in st.session_state:
    st.session_state.path = []

# Default koordinat:
DEFAULT_START_LAT = -6.553863223990267
DEFAULT_START_LON = 107.75965109951137
DEFAULT_END_LAT = -6.55838447945851
DEFAULT_END_LON = 107.75965109951137

# Koordinat Start/End untuk rute
if "route_start_lat" not in st.session_state:
    st.session_state.route_start_lat = DEFAULT_START_LAT
if "route_start_lon" not in st.session_state:
    st.session_state.route_start_lon = DEFAULT_START_LON
if "route_end_lat" not in st.session_state:
    st.session_state.route_end_lat = DEFAULT_END_LAT
if "route_end_lon" not in st.session_state:
    st.session_state.route_end_lon = DEFAULT_END_LON

# route_index: menandakan kita sedang di segmen ke-berapa
if "route_index" not in st.session_state:
    st.session_state.route_index = 0

# Menyimpan foto kamera terakhir (jika diambil dari kamera lokal)
if "latest_camera_image" not in st.session_state:
    st.session_state.latest_camera_image = None

# Inisialisasi untuk streaming IP Camera (dari snippet kedua)
if "camera_active" not in st.session_state:
    st.session_state.camera_active = False

# ----------------------------------------------------------
# 3. Parameter lain
NUM_SEGMENTS = 10

# ----------------------------------------------------------
# 4. Fungsi menghitung koordinat interpolasi Start→End
def get_next_route_point(index, total_segments, start_lat, start_lon, end_lat, end_lon):
    """
    index = 0..(total_segments - 1)
    Mengembalikan (lat, lon) untuk segmen ke-index.
    """
    if total_segments <= 1:
        return start_lat, start_lon

    frac = index / (total_segments - 1.0)
    lat = start_lat + frac * (end_lat - start_lat)
    lon = start_lon + frac * (end_lon - start_lon)
    return lat, lon

# ----------------------------------------------------------
# 5. Fungsi membuat HTML Google Maps
def generate_gmap_html(api_key, path, route_coords):
    """
    path: list of {lat, lon, rating}
    route_coords: [ {lat, lon}, {lat, lon} ] => (Start, End)

    Menampilkan:
      - Garis ungu rute Start→End
      - Tiap segmen path diwarnai sesuai rating (hitam, merah, kuning, hijau)
      - Marker untuk tiap titik, label = rating
    """
    path_json = json.dumps(path)
    route_json = json.dumps(route_coords)

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <title>Peta dengan Traffic-like Lines</title>
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
          var map = new google.maps.Map(document.getElementById('map'), {{
            zoom: 5,
            center: {{ lat: -2.5489, lng: 118.0149 }} // Center of Indonesia
          }});

          var pathData = {path_json}; // array of {{ lat, lon, rating }}
          var routeData = {route_json}; // [ {{lat, lon}}, {{lat, lon}} ]

          // Garis ungu (Start->End)
          if (routeData.length === 2) {{
            var routePath = routeData.map(function(pt) {{
              return {{ lat: pt.lat, lng: pt.lon }};
            }});
            var startEndPolyline = new google.maps.Polyline({{
              path: routePath,
              geodesic: true,
              strokeColor: '#FF00FF',
              strokeOpacity: 0.8,
              strokeWeight: 6
            }});
            startEndPolyline.setMap(map);

            // Marker Start (S)
            new google.maps.Marker({{
              position: routePath[0],
              map: map,
              label: {{ text: "S", color: 'white' }},
              icon: {{
                path: google.maps.SymbolPath.BACKWARD_CLOSED_ARROW,
                scale: 5,
                fillColor: "#00BFFF",
                fillOpacity: 1,
                strokeWeight: 1,
                strokeColor: 'white'
              }}
            }});

            // Marker End (E)
            new google.maps.Marker({{
              position: routePath[1],
              map: map,
              label: {{ text: "E", color: 'white' }},
              icon: {{
                path: google.maps.SymbolPath.FORWARD_CLOSED_ARROW,
                scale: 5,
                fillColor: "#FF1493",
                fillOpacity: 1,
                strokeWeight: 1,
                strokeColor: 'white'
              }}
            }});
          }}

          // Fungsi penentu warna segmen
          function getColor(score) {{
            if (score < 2) return "black";    // sangat jelek
            else if (score < 5) return "red"; // jelek
            else if (score < 8) return "yellow"; // lumayan
            else return "green";              // bagus
          }}

          // Polyline per segmen path (p1-p2)
          for (var i = 0; i < pathData.length - 1; i++) {{
            var p1 = pathData[i];
            var p2 = pathData[i+1];
            // rating segmen => rata2
            var segRating = (p1.rating + p2.rating) / 2.0;
            var color = getColor(segRating);

            var segmentPolyline = new google.maps.Polyline({{
              path: [
                {{ lat: p1.lat, lng: p1.lon }},
                {{ lat: p2.lat, lng: p2.lon }}
              ],
              geodesic: true,
              strokeColor: color,
              strokeOpacity: 1.0,
              strokeWeight: 7
            }});
            segmentPolyline.setMap(map);
          }}

          // Marker tiap titik
          for (var i = 0; i < pathData.length; i++) {{
            var p = pathData[i];
            var markerColor = getColor(p.rating);

            new google.maps.Marker({{
              position: {{ lat: p.lat, lng: p.lon }},
              map: map,
              label: {{
                text: p.rating.toFixed(1),
                color: 'white'
              }},
              icon: {{
                path: google.maps.SymbolPath.CIRCLE,
                scale: 8,
                fillColor: markerColor,
                fillOpacity: 1,
                strokeWeight: 1,
                strokeColor: 'white'
              }}
            }});
          }}

          // Auto-fit bounds
          var bounds = new google.maps.LatLngBounds();
          if (routeData.length === 2) {{
            bounds.extend(new google.maps.LatLng(routeData[0].lat, routeData[0].lon));
            bounds.extend(new google.maps.LatLng(routeData[1].lat, routeData[1].lon));
          }}
          for (var i = 0; i < pathData.length; i++) {{
            bounds.extend(new google.maps.LatLng(pathData[i].lat, pathData[i].lon));
          }}
          if (routeData.length === 2 || pathData.length > 0) {{
            map.fitBounds(bounds);
          }}
        }}
      </script>
      <script async
        src="https://maps.googleapis.com/maps/api/js?key={api_key}&callback=initMap">
      </script>
    </body>
    </html>
    """
    return html_code

# ----------------------------------------------------------
# 6. Fungsi klasifikasi kondisi jalan (berdasarkan brightness)
def classify_road_condition(frame: np.ndarray) -> str:
    """
    Contoh sederhana klasifikasi kondisi jalan.
    Di sini hanya didasarkan pada tingkat brightness (rata-rata nilai pixel).
    Semakin gelap -> semakin buruk.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    avg_brightness = np.mean(gray)
    if avg_brightness > 180:
        return "good"
    elif avg_brightness > 120:
        return "satisfactory"
    elif avg_brightness > 60:
        return "poor"
    else:
        return "very poor"

# ----------------------------------------------------------
# 7. Halaman Utama
def main():
    st.title("Demo Rute + Kamera Input (Traffic-like Line)")

    # -- Sidebar: Google Maps API Key
    st.sidebar.header("Google Maps API Key")
    gmap_api_key = st.sidebar.text_input("Google Maps API Key", value=DEFAULT_GMAP_API_KEY)
    if not gmap_api_key:
        st.sidebar.warning("Masukkan API Key agar peta bisa tampil.")

    # -- Sidebar: Input Koordinat Rute (dengan default)
    st.sidebar.header("Rute: Start - End")
    start_lat_in = st.sidebar.text_input("Start Lat", value=str(st.session_state.route_start_lat))
    start_lon_in = st.sidebar.text_input("Start Lon", value=str(st.session_state.route_start_lon))
    end_lat_in = st.sidebar.text_input("End Lat", value=str(st.session_state.route_end_lat))
    end_lon_in = st.sidebar.text_input("End Lon", value=str(st.session_state.route_end_lon))

    if st.sidebar.button("Simpan Rute"):
        try:
            st.session_state.route_start_lat = float(start_lat_in)
            st.session_state.route_start_lon = float(start_lon_in)
            st.session_state.route_end_lat = float(end_lat_in)
            st.session_state.route_end_lon = float(end_lon_in)

            # Reset path & index jika rute berubah
            st.session_state.path.clear()
            st.session_state.route_index = 0
            st.sidebar.success("Koordinat rute disimpan & path direset.")
        except ValueError:
            st.sidebar.error("Koordinat rute tidak valid (pastikan isian berupa angka).")

    st.markdown("---")

    # -- BAGIAN STREAMING IP CAMERA (disesuaikan dengan kode di bawah)
    st.subheader("Video Streaming dari IP Webcam")
    FRAME_WINDOW = st.empty()

    if st.session_state.camera_active:
        cap = cv2.VideoCapture(IP_CAMERA_URL)
        ret, frame = cap.read()
        if ret:
            # Klasifikasi kondisi jalan berdasarkan brightness (opsional)
            road_condition = classify_road_condition(frame)
            st.write(f"Kondisi jalan berdasarkan brightness: {road_condition}")

            # Tampilkan frame
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            FRAME_WINDOW.image(frame_rgb, channels="RGB")
        else:
            st.error("Tidak dapat mengakses kamera IP Webcam.")
        cap.release()
    else:
        st.info("Kamera tidak aktif.")

    # Tombol untuk mengaktifkan/mematikan kamera IP Webcam
    col_cam1, col_cam2 = st.columns(2)
    with col_cam1:
        if st.button("Aktifkan Kamera"):
            st.session_state.camera_active = True
    with col_cam2:
        if st.button("Matikan Kamera"):
            st.session_state.camera_active = False

    st.markdown("---")

    # -- Bagian Kamera Lokal (Opsional): Ambil Foto dari Kamera Lokal
    st.header("Ambil Foto dari Kamera Lokal (Opsional)")
    camera_image = st.camera_input("Klik/tap di sini untuk mengambil foto dari kamera lokal")
    if camera_image is not None:
        # Simpan ke session state agar tetap ada setelah reload
        st.session_state.latest_camera_image = camera_image
        st.image(camera_image, caption="Foto Terbaru dari Kamera Lokal")
    elif st.session_state.latest_camera_image is not None:
        st.image(st.session_state.latest_camera_image, caption="Foto Terakhir dari Kamera Lokal")

    st.markdown("---")

    # -- Tombol "Capture Data" untuk mensimulasikan capture data dengan score dummy
    st.header("Capture Data di Titik Berikutnya (Score Dummy)")
    st.write(f"Total segmen rute: {NUM_SEGMENTS}")
    st.write(f"Sudah direkam: {len(st.session_state.path)} titik.")

    if st.button("Capture Data (Score)"):
        # Pastikan rute valid
        if (st.session_state.route_start_lat is None or
            st.session_state.route_start_lon is None or
            st.session_state.route_end_lat is None or
            st.session_state.route_end_lon is None):
            st.warning("Set koordinat Start & End di sidebar terlebih dahulu.")
        else:
            if st.session_state.route_index < NUM_SEGMENTS:
                # Hitung titik ke-(route_index)
                lat, lon = get_next_route_point(
                    index=st.session_state.route_index,
                    total_segments=NUM_SEGMENTS,
                    start_lat=st.session_state.route_start_lat,
                    start_lon=st.session_state.route_start_lon,
                    end_lat=st.session_state.route_end_lat,
                    end_lon=st.session_state.route_end_lon
                )
                # Score dummy (acak antara 0 dan 10)
                score = random.uniform(0, 10)

                # Simpan ke path
                st.session_state.path.append({
                    "lat": lat,
                    "lon": lon,
                    "rating": score
                })
                st.session_state.route_index += 1

                st.success(
                    f"Titik ke-{st.session_state.route_index} direkam: "
                    f"({lat:.5f}, {lon:.5f}), score = {score:.2f}"
                )
            else:
                st.info("Sudah mencapai segmen terakhir (End).")

    st.markdown("---")

    # -- Tampilkan Peta dengan Google Maps
    st.header("Peta Rute dengan Garis 'Traffic-like'")
    route_coords = []
    if (st.session_state.route_start_lat is not None and
        st.session_state.route_start_lon is not None and
        st.session_state.route_end_lat is not None and
        st.session_state.route_end_lon is not None):
        route_coords = [
            {"lat": st.session_state.route_start_lat, "lon": st.session_state.route_start_lon},
            {"lat": st.session_state.route_end_lat, "lon": st.session_state.route_end_lon},
        ]

    if gmap_api_key:
        html_map = generate_gmap_html(gmap_api_key, st.session_state.path, route_coords)
        components.html(html_map, height=600)
    else:
        st.warning("Masukkan Google Maps API Key untuk melihat peta.")

if __name__ == "__main__":
    main()
