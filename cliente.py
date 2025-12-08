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
        
        status_text.text("Conectando al servidor...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(CONNECTION_TIMEOUT)
        sock.connect((SERVER_HOST, SERVER_PORT))
        
        sock.sendall(b"CLIENTE".ljust(10))
        status_text.text("Conectado al servidor")
        
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        status_text.text("Enviando metadata...")
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
        
        status_text.text(f"Enviando {total_frames} frames...")
        
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
                
                stats_text.text(f"Progreso: {frame_id + 1}/{total_frames} frames | {speed:.1f} fps")
        
        cap.release()
        
        status_text.text("Procesando en el servidor...")
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
        status_text.text(f"Descargando video procesado ({video_size / (1024*1024):.1f} MB)...")
        
        video_bytes = recibir_paquete(sock)
        if not video_bytes:
            st.error("Error recibiendo video procesado")
            return None
        
        status_text.text("Procesamiento completado")
        
        return video_bytes
        
    except socket.timeout:
        st.error("Tiempo de conexión agotado")
        return None
    except ConnectionRefusedError:
        st.error("No se pudo conectar al servidor")
        return None
    except Exception as e:
        st.error(f"Error: {e}")
        return None
    finally:
        if sock:
            sock.close()

def main():
    st.set_page_config(
        page_title="Procesador de Video",
        page_icon="▶",
        layout="wide"
    )
    
    st.markdown("""
        <style>
        .stApp {
            background-color: #1a1a1a;
        }
        .stMarkdown, .stText {
            color: #e0e0e0;
        }
        h1, h2, h3 {
            color: #ffffff;
        }
        .stButton>button {
            background-color: #2d2d2d;
            color: #ffffff;
            border: 1px solid #444444;
        }
        .stButton>button:hover {
            background-color: #3d3d3d;
            border-color: #555555;
        }
        .stProgress > div > div {
            background-color: #4a4a4a;
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.title("Procesador de Video Distribuido")
    st.markdown("---")
    
    uploaded_file = st.file_uploader(
        "Seleccionar video",
        type=['mp4', 'avi', 'mov', 'mkv']
    )
    
    if uploaded_file:
        file_size_mb = uploaded_file.size / (1024 * 1024)
        
        st.text(f"Archivo: {uploaded_file.name}")
        st.text(f"Tamaño: {file_size_mb:.2f} MB")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
            tmp.write(uploaded_file.read())
            video_path = tmp.name
            temp_files.append(video_path)
        
        es_valido, mensaje = validar_video(video_path)
        
        if not es_valido:
            st.error(mensaje)
        else:
            st.video(video_path)
            
            if st.button("Procesar Video"):
                st.markdown("---")
                progress_container = st.container()
                
                video_bytes = procesar_video(video_path, progress_container)
                
                if video_bytes:
                    output_path = tempfile.mktemp(suffix='_procesado.mp4')
                    temp_files.append(output_path)
                    
                    with open(output_path, 'wb') as f:
                        f.write(video_bytes)
                    
                    st.markdown("---")
                    st.subheader("Video Procesado")
                    st.video(output_path)
                    
                    with open(output_path, 'rb') as f:
                        st.download_button(
                            label="Descargar Video",
                            data=f,
                            file_name=f"procesado_{uploaded_file.name}",
                            mime="video/mp4"
                        )

if __name__ == "__main__":
    main()