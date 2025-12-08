import streamlit as st
import socket
import cv2
import numpy as np
import tempfile
import os
import time
import json
import atexit

SERVER_HOST = 'localhost'
SERVER_PORT = 8080
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
            return False, f"Archivo demasiado grande ({file_size_mb:.1f} MB). Máximo: {MAX_FILE_SIZE_MB} MB"
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return False, "No se puede abrir el video"
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames == 0:
            return False, "El video no contiene frames"
        
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
            stats_text = st.empty()
        
        status_text.info("Conectando al servidor...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((SERVER_HOST, SERVER_PORT))
        
        sock.sendall(b"CLIENTE".ljust(10))
        status_text.success("Conectado al servidor")
        
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        status_text.info("Enviando metadata del video...")
        metadata = {
            'total_frames': total_frames,
            'fps': fps,
            'width': width,
            'height': height
        }
        metadata_json = json.dumps(metadata).encode('utf-8')
        
        if not enviar_paquete(sock, metadata_json):
            st.error("Error enviando metadata")
            return None
        
        status_text.info(f"Enviando {total_frames} frames al cluster...")
        
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
                st.error(f"Error enviando frame {frame_id}")
                return None
            
            if frame_id % 10 == 0 or frame_id == total_frames - 1:
                progreso = (frame_id + 1) / total_frames
                progress_bar.progress(progreso)
                
                elapsed = time.time() - start_time
                speed = (frame_id + 1) / elapsed if elapsed > 0 else 0
                
                stats_text.text(f"Progreso: {frame_id + 1}/{total_frames} frames | Velocidad: {speed:.1f} fps")
        
        cap.release()
        
        status_text.warning("Procesando video en el cluster...")
        progress_bar.progress(1.0)
        
        response_payload = recibir_paquete(sock)
        if not response_payload:
            st.error("Error recibiendo respuesta del servidor")
            return None
        
        response = json.loads(response_payload.decode('utf-8'))
        
        if response['status'] != 'ready':
            st.error(f"Error del servidor: {response.get('message', 'Desconocido')}")
            return None
        
        video_size = response['size']
        status_text.info(f"Descargando video procesado ({video_size / (1024*1024):.1f} MB)...")
        
        video_bytes = recibir_paquete(sock)
        if not video_bytes:
            st.error("Error recibiendo video procesado")
            return None
        
        status_text.success("Procesamiento completado exitosamente")
        
        return video_bytes
        
    except ConnectionRefusedError:
        st.error("No se pudo conectar al servidor. Verifica la dirección IP y puerto.")
        return None
    except Exception as e:
        st.error(f"Error inesperado: {e}")
        return None
    finally:
        if sock:
            sock.close()

def main():
    st.set_page_config(
        page_title="Procesador de Video por Cluster",
        layout="wide"
    )
    
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        * {
            font-family: 'Inter', sans-serif;
        }
        
        .stApp {
            background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
        }
        
        .main > div {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        
        h1 {
            color: #ffffff !important;
            font-weight: 700 !important;
            font-size: 2.5rem !important;
            letter-spacing: -0.02em !important;
            margin-bottom: 0.5rem !important;
            text-align: center !important;
        }
        
        hr {
            margin: 2rem 0 !important;
            border-color: #30363d !important;
        }
        
        .stMarkdown, .stText {
            color: #c9d1d9;
        }
        
        .info-box {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 1.5rem;
            margin: 1rem 0;
        }
        
        .info-row {
            display: flex;
            justify-content: space-between;
            margin: 0.5rem 0;
            color: #c9d1d9;
        }
        
        .info-label {
            color: #8b949e;
            font-weight: 500;
        }
        
        .info-value {
            color: #58a6ff;
            font-weight: 600;
        }
        
        .stFileUploader {
            background: #0d1117;
            border: 2px dashed #30363d;
            border-radius: 8px;
            padding: 2rem;
        }
        
        .stFileUploader:hover {
            border-color: #58a6ff;
        }
        
        .stButton>button {
            background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
            color: #ffffff;
            border: none;
            padding: 0.75rem 2rem;
            font-weight: 600;
            font-size: 1rem;
            border-radius: 6px;
            width: 100%;
            transition: all 0.2s;
        }
        
        .stButton>button:hover {
            background: linear-gradient(135deg, #2ea043 0%, #3fb950 100%);
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(46, 160, 67, 0.3);
        }
        
        .stProgress > div > div {
            background: linear-gradient(90deg, #238636 0%, #2ea043 100%);
        }
        
        .stProgress > div {
            background-color: #21262d;
        }
        
        .stVideo {
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid #30363d;
        }
        
        div[data-testid="stDownloadButton"] > button {
            background: linear-gradient(135deg, #1f6feb 0%, #388bfd 100%);
            color: #ffffff;
            border: none;
            padding: 0.75rem 2rem;
            font-weight: 600;
            font-size: 1rem;
            border-radius: 6px;
            width: 100%;
        }
        
        div[data-testid="stDownloadButton"] > button:hover {
            background: linear-gradient(135deg, #388bfd 0%, #58a6ff 100%);
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(88, 166, 255, 0.3);
        }
        
        .success-box {
            background: linear-gradient(135deg, #0d4429 0%, #0d1117 100%);
            border: 1px solid #238636;
            border-radius: 8px;
            padding: 1rem;
            margin: 1rem 0;
            text-align: center;
            color: #3fb950;
            font-weight: 600;
        }
        
        .subtitle {
            text-align: center;
            color: #8b949e;
            font-size: 1.1rem;
            margin-bottom: 2rem;
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<h1>Procesador de Video por Cluster</h1>", unsafe_allow_html=True)
    st.markdown("<p class='subtitle'>Procesamiento distribuido con filtros cinemáticos</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Cargar Video")
        uploaded_file = st.file_uploader(
            "Seleccionar archivo de video",
            type=['mp4', 'avi', 'mov', 'mkv'],
            label_visibility="collapsed"
        )
        
        if uploaded_file:
            file_size_mb = uploaded_file.size / (1024 * 1024)
            
            st.markdown(f"""
                <div class='info-box'>
                    <div class='info-row'>
                        <span class='info-label'>Archivo:</span>
                        <span class='info-value'>{uploaded_file.name}</span>
                    </div>
                    <div class='info-row'>
                        <span class='info-label'>Tamaño:</span>
                        <span class='info-value'>{file_size_mb:.2f} MB</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
                tmp.write(uploaded_file.read())
                video_path = tmp.name
                temp_files.append(video_path)
            
            es_valido, mensaje = validar_video(video_path)
            
            if not es_valido:
                st.error(mensaje)
            else:
                st.markdown("#### Video Original")
                st.video(video_path)
                
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Iniciar Procesamiento"):
                    with col2:
                        st.subheader("Procesamiento")
                        progress_container = st.container()
                        
                        video_bytes = procesar_video(video_path, progress_container)
                        
                        if video_bytes:
                            output_path = tempfile.mktemp(suffix='_procesado.mp4')
                            temp_files.append(output_path)
                            
                            with open(output_path, 'wb') as f:
                                f.write(video_bytes)
                            
                            st.markdown("<div class='success-box'>Video procesado exitosamente</div>", unsafe_allow_html=True)
                            
                            st.markdown("#### Video Procesado")
                            st.video(output_path)
                            
                            st.markdown("<br>", unsafe_allow_html=True)
                            with open(output_path, 'rb') as f:
                                st.download_button(
                                    label="Descargar Video Procesado",
                                    data=f,
                                    file_name=f"procesado_{uploaded_file.name}",
                                    mime="video/mp4"
                                )
    
    with col2:
        if not uploaded_file:
            st.markdown("""
                <div style='padding: 4rem 2rem; text-align: center; color: #8b949e;'>
                    <h3 style='color: #c9d1d9;'>Instrucciones</h3>
                    <p>1. Selecciona un archivo de video en el panel izquierdo</p>
                    <p>2. El sistema validará el archivo automáticamente</p>
                    <p>3. Presiona "Iniciar Procesamiento" para comenzar</p>
                    <p>4. El cluster aplicará filtros cinemáticos al video</p>
                    <p>5. Descarga el resultado cuando esté listo</p>
                </div>
            """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()