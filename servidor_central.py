import socket
import cv2
import numpy as np
import threading
import queue
import time
import json
import os
import tempfile

BROKER_HOST = '0.0.0.0'
BROKER_PORT = 8080
MAX_PAYLOAD_SIZE = 10 * 1024 * 1024
BUFFER_SIZE = 4096
QUEUE_TIMEOUT = 1.0

cola_frames_entrada = queue.Queue()
sesiones_clientes = {}
lock_sesiones = threading.Lock()
nodos_disponibles = []
lock_nodos = threading.Lock()

def log(level, message):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] [{level}] {message}")

def recibir_bytes_exactos(conn, num_bytes):
    data = b""
    while len(data) < num_bytes:
        try:
            packet = conn.recv(num_bytes - len(data))
            if not packet:
                return None
            data += packet
        except Exception as e:
            log("ERROR", f"Error recibiendo bytes: {e}")
            return None
    return data

def recibir_paquete(conn):
    try:
        size_data = recibir_bytes_exactos(conn, 4)
        if not size_data:
            return None
        
        frame_size = int.from_bytes(size_data, byteorder='big')
        
        if frame_size > MAX_PAYLOAD_SIZE:
            log("WARNING", f"Payload demasiado grande: {frame_size} bytes")
            return None
        
        payload = b""
        while len(payload) < frame_size:
            packet = conn.recv(min(BUFFER_SIZE, frame_size - len(payload)))
            if not packet:
                return None
            payload += packet
            
        return payload
    except Exception as e:
        log("ERROR", f"Error al recibir paquete: {e}")
        return None

def enviar_paquete(conn, payload):
    try:
        size_bytes = len(payload).to_bytes(4, byteorder='big')
        conn.sendall(size_bytes + payload)
        return True
    except Exception as e:
        log("ERROR", f"Error al enviar paquete: {e}")
        return False

def ensamblar_video(frames_dict, fps, width, height, cliente_id):
    try:
        log("INFO", f"Ensamblando video para cliente {cliente_id}: {len(frames_dict)} frames")
        
        output_path = f"/tmp/video_procesado_{cliente_id}_{int(time.time())}.mp4"
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        if not out.isOpened():
            log("ERROR", "No se pudo crear VideoWriter")
            return None
        
        frame_ids = sorted(frames_dict.keys())
        for frame_id in frame_ids:
            frame = frames_dict[frame_id]
            out.write(frame)
        
        out.release()
        log("INFO", f"Video ensamblado exitosamente: {output_path}")
        
        with open(output_path, 'rb') as f:
            video_bytes = f.read()
        
        os.unlink(output_path)
        
        log("INFO", f"Video para cliente {cliente_id} listo ({len(video_bytes)} bytes)")
        return video_bytes
        
    except Exception as e:
        log("ERROR", f"Error ensamblando video: {e}")
        return None

def manejar_cliente(conn, addr):
    cliente_id = f"{addr[0]}:{addr[1]}"
    log("INFO", f"Cliente conectado: {cliente_id}")
    
    try:
        metadata_payload = recibir_paquete(conn)
        if not metadata_payload:
            log("ERROR", f"No se recibió metadata de {cliente_id}")
            return
        
        metadata = json.loads(metadata_payload.decode('utf-8'))
        total_frames = metadata['total_frames']
        fps = metadata['fps']
        width = metadata['width']
        height = metadata['height']
        
        log("INFO", f"Metadata recibida de {cliente_id}: {total_frames} frames, {fps} fps, {width}x{height}")
        
        with lock_sesiones:
            sesiones_clientes[cliente_id] = {
                'conn': conn,
                'metadata': metadata,
                'frames': {},
                'procesados': set()
            }
        
        frames_recibidos = 0
        while frames_recibidos < total_frames:
            payload = recibir_paquete(conn)
            if payload is None:
                log("ERROR", f"Error recibiendo frame {frames_recibidos} de {cliente_id}")
                break
            
            cola_frames_entrada.put((cliente_id, payload))
            frames_recibidos += 1
            
            if frames_recibidos % 10 == 0:
                log("INFO", f"Cliente {cliente_id}: {frames_recibidos}/{total_frames} frames recibidos")
        
        log("INFO", f"Cliente {cliente_id}: Todos los frames recibidos ({frames_recibidos}/{total_frames})")
        
        log("INFO", f"Esperando procesamiento completo para {cliente_id}...")
        while True:
            with lock_sesiones:
                if cliente_id not in sesiones_clientes:
                    log("ERROR", f"Sesión de {cliente_id} eliminada prematuramente")
                    return
                
                procesados = len(sesiones_clientes[cliente_id]['procesados'])
                
            if procesados >= total_frames:
                log("INFO", f"Todos los frames de {cliente_id} han sido procesados ({procesados}/{total_frames})")
                break
            
            time.sleep(0.5)
        
        with lock_sesiones:
            frames_dict = sesiones_clientes[cliente_id]['frames']
        
        video_bytes = ensamblar_video(frames_dict, fps, width, height, cliente_id)
        
        if video_bytes is None:
            log("ERROR", f"Error ensamblando video para {cliente_id}")
            error_msg = json.dumps({'status': 'error', 'message': 'Error ensamblando video'}).encode('utf-8')
            enviar_paquete(conn, error_msg)
            return
        
        ready_msg = json.dumps({'status': 'ready', 'size': len(video_bytes)}).encode('utf-8')
        if not enviar_paquete(conn, ready_msg):
            log("ERROR", f"Error enviando mensaje READY a {cliente_id}")
            return
        
        log("INFO", f"Enviando video completo a {cliente_id}...")
        if not enviar_paquete(conn, video_bytes):
            log("ERROR", f"Error enviando video a {cliente_id}")
            return
        
        log("INFO", f"Video enviado exitosamente a {cliente_id}")
        
    except Exception as e:
        log("ERROR", f"Error manejando cliente {cliente_id}: {e}")
    finally:
        with lock_sesiones:
            if cliente_id in sesiones_clientes:
                del sesiones_clientes[cliente_id]
        conn.close()
        log("INFO", f"Cliente {cliente_id} desconectado")

def manejar_nodo(conn, addr):
    nodo_id = f"{addr[0]}:{addr[1]}"
    log("INFO", f"Nodo conectado: {nodo_id}")
    
    with lock_nodos:
        nodos_disponibles.append(conn)
    
    frames_procesados = 0
    
    try:
        while True:
            try:
                cliente_id, payload = cola_frames_entrada.get(timeout=QUEUE_TIMEOUT)
            except queue.Empty:
                continue
            
            if not enviar_paquete(conn, payload):
                log("ERROR", f"Error enviando frame a nodo {nodo_id}")
                cola_frames_entrada.put((cliente_id, payload))
                break
            
            payload_procesado = recibir_paquete(conn)
            if payload_procesado is None:
                log("ERROR", f"Nodo {nodo_id} no respondió")
                cola_frames_entrada.put((cliente_id, payload))
                break
            
            frame_id = int.from_bytes(payload_procesado[:4], byteorder='big')
            img_data = payload_procesado[4:]
            nparr = np.frombuffer(img_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            with lock_sesiones:
                if cliente_id in sesiones_clientes:
                    sesiones_clientes[cliente_id]['frames'][frame_id] = frame
                    sesiones_clientes[cliente_id]['procesados'].add(frame_id)
                    frames_procesados += 1
            
            if frames_procesados % 10 == 0:
                log("INFO", f"Nodo {nodo_id}: {frames_procesados} frames procesados")
            
    except Exception as e:
        log("ERROR", f"Error con nodo {nodo_id}: {e}")
    finally:
        with lock_nodos:
            if conn in nodos_disponibles:
                nodos_disponibles.remove(conn)
        conn.close()
        log("INFO", f"Nodo {nodo_id} desconectado (procesó {frames_procesados} frames)")

def aceptar_conexiones():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((BROKER_HOST, BROKER_PORT))
    server_socket.listen(5)
    
    log("INFO", f"Servidor central escuchando en {BROKER_HOST}:{BROKER_PORT}")
    
    while True:
        try:
            conn, addr = server_socket.accept()
            
            identificacion = recibir_bytes_exactos(conn, 10)
            if not identificacion:
                conn.close()
                continue
                
            id_str = identificacion.decode('utf-8').strip()
            
            if id_str == "CLIENTE":
                t = threading.Thread(target=manejar_cliente, args=(conn, addr), daemon=True)
                t.start()
            elif id_str == "NODO":
                t = threading.Thread(target=manejar_nodo, args=(conn, addr), daemon=True)
                t.start()
            else:
                log("WARNING", f"ID desconocida: {id_str}")
                conn.close()
                
        except Exception as e:
            log("ERROR", f"Error aceptando conexión: {e}")

def main():
    log("INFO", "=== Sistema Distribuido de Procesamiento de Video ===")
    log("INFO", "Iniciando servidor central...")
    
    t = threading.Thread(target=aceptar_conexiones, daemon=True)
    t.start()
    
    try:
        while True:
            time.sleep(10)
            with lock_sesiones:
                num_clientes = len(sesiones_clientes)
            with lock_nodos:
                num_nodos = len(nodos_disponibles)
            
            log("INFO", f"Estadísticas: {num_clientes} clientes activos, {num_nodos} nodos disponibles")
    except KeyboardInterrupt:
        log("INFO", "Servidor detenido por usuario")

if __name__ == "__main__":
    main()