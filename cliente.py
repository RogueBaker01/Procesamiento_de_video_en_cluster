import streamlit as st
import socket
import cv2
import numpy as np
import tempfile
import os
import time
import json
import atexit

SERVER_HOST = '148.220.211.237'
SERVER_PORT = 8080
CONNECTION_TIMEOUT = 30
JPEG_QUALITY = 90
MAX_FILE_SIZE_MB = 500

temp_files = []

def cleanup_temp_files():
    for f in temp_files:
        try:
            if os.path.exists(f):
                os.unlink(f)
        except Exception:
            pass

atexit.register(cleanup_temp_files)

def enviar_paquete(sock, payload):
    try:
        size_bytes = len(payload).to_bytes(4, byteorder='big')
        sock.sendall(size_bytes + payload)
        return True
    except Exception as e:
        st.error(f"Error enviando paquete: {e}")
        return False

def recibir_bytes_exactos(sock, num_bytes):
    data = b""
    while len(data) < num_bytes:
        try:
            packet = sock.recv(num_bytes - len(data))
            if not packet:
                return None
            data += packet
        except Exception as e:
            st.error(f"Error recibiendo datos: {e}")
            return None
    return data

def recibir_paquete(sock):
    size_data = recibir_bytes_exactos(sock, 4)
    if not size_data:
        return None
    
    total_size = int.from_bytes(size_data, byteorder='big')
    
    payload = b""
    while len(payload) < total_size:
        packet = sock.recv(min(4096, total_size - len(payload)))
        if not packet:
            return None
        payload += packet
    
    return payload

def validar_video(video_path):
    try:
        file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            return False, f"El archivo es demasiado grande ({file_size_mb:.1f} MB). Máximo: {MAX_FILE_SIZE_MB} MB"
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return False, "No se puede abrir el video. Formato no soportado."
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames == 0:
            return False, "El video no contiene frames."
        
        cap.release()
        return True, "OK"
        
    except Exception as e:
        return False, f"Error validando video: {e}"

def procesar_video(video_path, progress_container):
    sock = None
    
    try:
        with progress_container:
            status_text = st.empty()
            progress_bar = st.progress(0)
            stats_col1, stats_col2, stats_col3 = st.columns(3)
            
            with stats_col1:
                st.metric("Estado", "Conectando...")
            with stats_col2:
                frames_metric = st.empty()
                frames_metric.metric("Frames Enviados", "0")
            with stats_col3:
                speed_metric = st.empty()
                speed_metric.metric("Velocidad", "0 fps")
        
        status_text.info("🔌 Conectando al servidor...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(CONNECTION_TIMEOUT)
        sock.connect((SERVER_HOST, SERVER_PORT))
        
        sock.sendall(b"CLIENTE".ljust(10))
        
        with stats_col1:
            st.metric("Estado", "Conectado ✅")
        status_text.success("✅ Conectado al cluster de procesamiento")
        time.sleep(0.5)
        
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        status_text.info("📋 Enviando metadata del video...")
        metadata = {
            'total_frames': total_frames,
            'fps': fps,
            'width': width,
            'height': height
        }
        metadata_json = json.dumps(metadata).encode('utf-8')
        
        if not enviar_paquete(sock, metadata_json):
            st.error("❌ Error enviando metadata")
            return None
        
        status_text.info(f"📤 Enviando {total_frames} frames al cluster...")
        
        start_time = time.time()
        for frame_id in range(total_frames):
            ret, frame = cap.read()
            if not ret:
                break
            
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            img_bytes = buffer.tobytes()
            
            id_bytes = frame_id.to_bytes(4, byteorder='big')
            payload = id_bytes + img_bytes
            
            if not enviar_paquete(sock, payload):
                st.error(f"❌ Error enviando frame {frame_id}")
                return None
            
            if frame_id % 5 == 0 or frame_id == total_frames - 1:
                progreso = (frame_id + 1) / total_frames
                progress_bar.progress(progreso)
                
                elapsed = time.time() - start_time
                speed = (frame_id + 1) / elapsed if elapsed > 0 else 0
                
                frames_metric.metric("Frames Enviados", f"{frame_id + 1}/{total_frames}")
                speed_metric.metric("Velocidad", f"{speed:.1f} fps")
        
        cap.release()
        
        with stats_col1:
            st.metric("Estado", "Procesando...")
        status_text.warning("⚙️ Procesando video en el cluster... Esto puede tomar unos momentos.")
        progress_bar.progress(1.0)
        
        status_text.info("⏳ Esperando video procesado del servidor...")
        
        response_payload = recibir_paquete(sock)
        if not response_payload:
            st.error("❌ Error recibiendo respuesta del servidor")
            return None
        
        response = json.loads(response_payload.decode('utf-8'))
        
        if response['status'] != 'ready':
            st.error(f"❌ Error del servidor: {response.get('message', 'Desconocido')}")
            return None
        
        video_size = response['size']
        status_text.info(f"📥 Descargando video procesado ({video_size / (1024*1024):.1f} MB)...")
        
        video_bytes = recibir_paquete(sock)
        if not video_bytes:
            st.error("❌ Error recibiendo video procesado")
            return None
        
        with stats_col1:
            st.metric("Estado", "Completado ✅")
        status_text.success("🎉 ¡Video procesado exitosamente!")
        
        return video_bytes
        
    except socket.timeout:
        st.error("❌ Tiempo de conexión agotado. Verifica que el servidor esté ejecutándose.")
        return None
    except ConnectionRefusedError:
        st.error("❌ No se pudo conectar al servidor. Verifica la dirección y puerto.")
        return None
    except Exception as e:
        st.error(f"❌ Error inesperado: {e}")
        return None
    finally:
        if sock:
            sock.close()

def main():
    st.set_page_config(
        page_title="🎬 Cluster Video Processor",
        page_icon="🎬",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    st.markdown("""
        <style>
        .main-header {
            font-size: 3rem;
            font-weight: 700;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-align: center;
            margin-bottom: 1rem;
        }
        .subtitle {
            text-align: center;
            color: #718096;
            font-size: 1.2rem;
            margin-bottom: 2rem;
        }
        .info-card {
            background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
            padding: 1.5rem;
            border-radius: 10px;
            border-left: 4px solid #667eea;
            margin: 1rem 0;
        }
        .stButton>button {
            width: 100%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-size: 1.1rem;
            padding: 0.75rem 2rem;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            transition: transform 0.2s;
        }
        .stButton>button:hover {
            transform: translateY(-2px);
            box-shadow: 0 7px 14px rgba(50,50,93,.1), 0 3px 6px rgba(0,0,0,.08);
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<h1 class="main-header">🎬 Procesador de Video Distribuido</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Aplica filtros cinemáticos profesionales usando procesamiento en cluster</p>', unsafe_allow_html=True)
    
    with st.expander("ℹ️ Acerca del Sistema", expanded=False):
        st.markdown("""
        ### 🎨 Efectos Aplicados
        - **Filtro Teal-Orange**: Color grading cinematográfico profesional
        - **Curva de Contraste S**: Mejora el contraste dinámico
        - **Viñeta**: Oscurecimiento gradual en los bordes
        - **Barras Cinemáticas**: Formato panorámico (letterbox)
        
        ### ⚙️ Tecnología
        - **Procesamiento Distribuido**: Múltiples nodos trabajan en paralelo
        - **Alta Calidad**: Compresión JPEG al 90%
        - **Formatos Soportados**: MP4, AVI, MOV, MKV
        """)
    
    st.markdown("---")
    
    col_upload, col_spacer, col_preview = st.columns([1, 0.1, 1])
    
    with col_upload:
        st.markdown("### 📁 Cargar Video")
        
        uploaded_file = st.file_uploader(
            "Selecciona tu video",
            type=['mp4', 'avi', 'mov', 'mkv'],
            help=f"Tamaño máximo: {MAX_FILE_SIZE_MB} MB"
        )
        
        if uploaded_file:
            file_size_mb = uploaded_file.size / (1024 * 1024)
            
            st.markdown('<div class="info-card">', unsafe_allow_html=True)
            st.markdown(f"**📄 Archivo:** {uploaded_file.name}")
            st.markdown(f"**💾 Tamaño:** {file_size_mb:.2f} MB")
            st.markdown('</div>', unsafe_allow_html=True)
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
                tmp.write(uploaded_file.read())
                video_path = tmp.name
                temp_files.append(video_path)
            
            es_valido, mensaje = validar_video(video_path)
            
            if not es_valido:
                st.error(f"❌ {mensaje}")
            else:
                st.video(video_path)
                
                if st.button("🚀 Iniciar Procesamiento en Cluster", type="primary"):
                    with col_preview:
                        st.markdown("### 📊 Progreso del Procesamiento")
                        progress_container = st.container()
                        
                        video_bytes = procesar_video(video_path, progress_container)
                        
                        if video_bytes:
                            output_path = tempfile.mktemp(suffix='_procesado.mp4')
                            temp_files.append(output_path)
                            
                            with open(output_path, 'wb') as f:
                                f.write(video_bytes)
                            
                            st.markdown("---")
                            st.markdown("### 🎉 Resultado")
                            st.success("✅ ¡Video procesado exitosamente!")
                            
                            st.video(output_path)
                            
                            with open(output_path, 'rb') as f:
                                st.download_button(
                                    label="⬇️ Descargar Video Procesado",
                                    data=f,
                                    file_name=f"procesado_{uploaded_file.name}",
                                    mime="video/mp4",
                                    type="primary"
                                )
    
    with col_preview:
        if not uploaded_file:
            st.markdown("### 👈 Comienza subiendo un video")
            st.info("""
            Sube un video en el panel izquierdo para comenzar el procesamiento distribuido.
            
            El sistema utilizará múltiples nodos de procesamiento en paralelo para aplicar
            filtros cinemáticos profesionales a tu video.
            """)
    
    st.markdown("---")
    st.markdown(
        "<p style='text-align: center; color: #718096;'>💡 Asegúrate de que el servidor central y los nodos de procesamiento estén ejecutándose</p>",
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()