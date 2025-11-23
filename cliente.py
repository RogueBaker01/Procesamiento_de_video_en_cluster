import streamlit as st
import socket
import cv2
import numpy as np
import tempfile
import os

SERVER_HOST = 'localhost'
SERVER_PORT = 8080

def enviar_frame(conn, frame):
    try:
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        data = buffer.tobytes()
        
        size_bytes = len(data).to_bytes(4, byteorder='big')
        conn.sendall(size_bytes + data)
        return True
    except Exception as e:
        st.error(f"Error al enviar frame: {e}")
        return False

def recibir_frame(conn):
    try:
        size_data = b""
        while len(size_data) < 4:
            packet = conn.recv(4 - len(size_data))
            if not packet:
                return None
            size_data += packet
        
        frame_size = int.from_bytes(size_data, byteorder='big')
        
        frame_data = b""
        while len(frame_data) < frame_size:
            packet = conn.recv(min(4096, frame_size - len(frame_data)))
            if not packet:
                return None
            frame_data += packet
        
        nparr = np.frombuffer(frame_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        return frame
    except Exception as e:
        st.error(f"Error al recibir frame: {e}")
        return None

def procesar_video(video_path, progress_bar, status_text, video_placeholder):
    sock = None
    frames_procesados = []
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((SERVER_HOST, SERVER_PORT))
        
        sock.sendall(b"CLIENTE")
        status_text.text("Conectado al servidor")
        
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        status_text.text(f"Procesando video: {total_frames} frames a {fps:.2f} FPS")
        
        frame_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if not enviar_frame(sock, frame):
                st.error("Error al enviar frame al servidor")
                break
            
            frame_procesado = recibir_frame(sock)
            if frame_procesado is None:
                st.error("Error al recibir frame procesado")
                break
            
            frames_procesados.append(frame_procesado)
            frame_count += 1
            
            progress = frame_count / total_frames
            progress_bar.progress(progress)
            status_text.text(f"Procesando: {frame_count}/{total_frames} frames ({progress*100:.1f}%)")
            
            if frame_count % 10 == 0:
                frame_rgb = cv2.cvtColor(frame_procesado, cv2.COLOR_BGR2RGB)
                video_placeholder.image(frame_rgb, caption=f"Frame {frame_count}", use_container_width=True)
        
        cap.release()
        status_text.text(f"Procesamiento completado: {frame_count} frames")
        
        return frames_procesados, fps
        
    except Exception as e:
        st.error(f"Error durante el procesamiento: {e}")
        return None, None
    finally:
        if sock:
            sock.close()

def guardar_video(frames, fps, output_path):
    if not frames:
        return False
    
    height, width = frames[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*'mp4v') #type: ignore
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    for frame in frames:
        out.write(frame)
    
    out.release()
    return True

def main():
    st.set_page_config(
        page_title="Cliente de Procesamiento de Video",
        layout="wide"
    )
    
    st.title("Procesamiento de Video")
    st.markdown("---")
    
    global SERVER_HOST, SERVER_PORT
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Subir Video")
        uploaded_file = st.file_uploader(
            "Selecciona un archivo de video",
            type=['mp4', 'avi', 'mov', 'mkv'],
            help="Sube el video que deseas procesar con filtro cinemático"
        )
        
        if uploaded_file is not None:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
                tmp_file.write(uploaded_file.read())
                video_path = tmp_file.name
            
            st.success(f"Video cargado: {uploaded_file.name}")
            
            cap = cv2.VideoCapture(video_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = total_frames / fps if fps > 0 else 0
            cap.release()
            
            st.info(f"""
            **Información del Video:**
            - Resolución: {width}x{height}
            - FPS: {fps:.2f}
            - Duración: {duration:.2f} segundos
            - Frames totales: {total_frames}
            """)
            
            if st.button("Procesar Video", type="primary", use_container_width=True):
                with col2:
                    st.subheader("Procesamiento")
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    video_placeholder = st.empty()
                    
                    frames_procesados, fps_out = procesar_video(
                        video_path, 
                        progress_bar, 
                        status_text, 
                        video_placeholder
                    )
                    
                    if frames_procesados:
                        output_path = tempfile.mktemp(suffix='_procesado.mp4')
                        
                        with st.spinner("Guardando video procesado..."):
                            if guardar_video(frames_procesados, fps_out, output_path):
                                st.success("Video procesado exitosamente!")
                                
                                with open(output_path, 'rb') as f:
                                    st.download_button(
                                        label="Descargar Video Procesado",
                                        data=f,
                                        file_name=f"procesado_{uploaded_file.name}",
                                        mime="video/mp4",
                                        use_container_width=True
                                    )
                                
                                os.unlink(output_path)
                    
                    os.unlink(video_path)
    
    with col2:
        if uploaded_file is None:
            st.subheader("Comienza subiendo un video")
            st.info("Sube un video en la columna izquierda para comenzar el procesamiento.")

if __name__ == "__main__":
    main()
