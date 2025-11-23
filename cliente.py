import streamlit as st
import socket
import cv2
import numpy as np
import tempfile
import os
import threading
import time

SERVER_HOST = 'localhost'
SERVER_PORT = 8080

buffer_recepcion = {}
lock_recepcion = threading.Lock()

def enviar_hilo(sock, cap, stop_event):
    frame_id = 0
    while not stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            break
        
        try:
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            img_bytes = buffer.tobytes()
            
            id_bytes = frame_id.to_bytes(4, byteorder='big')
            payload = id_bytes + img_bytes
            size_bytes = len(payload).to_bytes(4, byteorder='big')
            
            sock.sendall(size_bytes + payload)
            frame_id += 1
            
            time.sleep(0.001)
        except Exception as e:
            print(f"Error enviando frame {frame_id}: {e}")
            break
    print("Fin de envío de frames")

def recibir_hilo(sock, stop_event, total_frames):
    frames_cnt = 0
    while frames_cnt < total_frames and not stop_event.is_set():
        try:
            size_data = b""
            while len(size_data) < 4:
                packet = sock.recv(4 - len(size_data))
                if not packet: return
                size_data += packet
            total_size = int.from_bytes(size_data, byteorder='big')
            
            payload = b""
            while len(payload) < total_size:
                packet = sock.recv(min(4096, total_size - len(payload)))
                if not packet: return
                payload += packet
            
            f_id = int.from_bytes(payload[:4], byteorder='big')
            img_data = payload[4:]
            nparr = np.frombuffer(img_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            with lock_recepcion:
                buffer_recepcion[f_id] = frame
            
            frames_cnt += 1
        except Exception as e:
            print(f"Error recibiendo: {e}")
            break
    print("Fin de recepción de frames")

def procesar_video_async(video_path, progress_bar, status_text, video_placeholder):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    frames_finales = []
    
    try:
        sock.connect((SERVER_HOST, SERVER_PORT))
        sock.sendall(b"CLIENTE".ljust(10))
        status_text.text("Conectado al Cluster...")
        
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        global buffer_recepcion
        buffer_recepcion = {}
        
        stop_event = threading.Event()
        
        t_recv = threading.Thread(target=recibir_hilo, args=(sock, stop_event, total_frames))
        t_send = threading.Thread(target=enviar_hilo, args=(sock, cap, stop_event))
        
        t_recv.start()
        t_send.start()
        
        next_frame_needed = 0
        
        while next_frame_needed < total_frames:
            frame_listo = None
            
            with lock_recepcion:
                if next_frame_needed in buffer_recepcion:
                    frame_listo = buffer_recepcion.pop(next_frame_needed)
            
            if frame_listo is not None:
                frames_finales.append(frame_listo)
                
                if next_frame_needed % 5 == 0:
                    progreso = next_frame_needed / total_frames
                    progress_bar.progress(progreso)
                    status_text.text(f"Procesando: {next_frame_needed}/{total_frames} (Cluster Activo)")
                    
                    frame_rgb = cv2.cvtColor(frame_listo, cv2.COLOR_BGR2RGB)
                    video_placeholder.image(frame_rgb, use_container_width=True)
                
                next_frame_needed += 1
            else:
                time.sleep(0.01)
                if not t_recv.is_alive() and len(buffer_recepcion) == 0:
                    st.error("Se perdió conexión o finalizó inesperadamente.")
                    break
        
        stop_event.set()
        t_send.join()
        t_recv.join()
        
        return frames_finales, fps
        
    except Exception as e:
        st.error(f"Error: {e}")
        return None, None
    finally:
        sock.close()

def guardar_video(frames, fps, output_path):
    if not frames: return False
    height, width = frames[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*'mp4v') #type: ignore
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    for frame in frames:
        out.write(frame)
    out.release()
    return True

def main():
    st.set_page_config(page_title="Cluster Video Processor", layout="wide")
    st.title("Procesamiento Distribuido en Cluster")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        uploaded_file = st.file_uploader("Subir Video", type=['mp4', 'avi', 'mov'])
        if uploaded_file:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
                tmp.write(uploaded_file.read())
                video_path = tmp.name
            
            if st.button("Iniciar Procesamiento en Cluster", type="primary"):
                with col2:
                    st.subheader("Progreso en Tiempo Real")
                    p_bar = st.progress(0)
                    status = st.empty()
                    v_place = st.empty()
                    
                    frames, fps = procesar_video_async(video_path, p_bar, status, v_place)
                    
                    if frames:
                        out_path = tempfile.mktemp(suffix='_proc.mp4')
                        guardar_video(frames, fps, out_path)
                        st.success("¡Procesamiento Completado!")
                        with open(out_path, 'rb') as f:
                            st.download_button("Descargar Video", f, file_name="cluster_result.mp4")
                        os.unlink(out_path)
            os.unlink(video_path)

if __name__ == "__main__":
    main()