import socket
import cv2
import numpy as np
import threading
import queue
import time

Broker_host = '0.0.0.0'
Broker_port = 8080

cola_frames_entrada = queue.Queue()
cola_frames_procesados = queue.Queue()

nodos_disponibles = []
clientes_conectados = []
lock_nodos = threading.Lock()
lock_clientes = threading.Lock()

fps = 30
video_writer = None
guardando_video = False


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
        print(f"Error al recibir frame: {e}")
        return None


def enviar_frame(conn, frame):
    try:
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        data = buffer.tobytes()
        
        size_bytes = len(data).to_bytes(4, byteorder='big')
        conn.sendall(size_bytes + data)
        return True
    except Exception as e:
        print(f"Error al enviar frame: {e}")
        return False


def manejar_cliente(conn, addr):
    print(f"Cliente conectado desde {addr}")
    
    with lock_clientes:
        clientes_conectados.append(conn)
    
    try:
        while True:
            frame = recibir_frame(conn)
            if frame is None:
                print(f"Cliente {addr} desconectado")
                break
            
            cola_frames_entrada.put(frame)
            print(f"Frame recibido del cliente {addr}, cola: {cola_frames_entrada.qsize()}")
            
            try:
                frame_procesado = cola_frames_procesados.get(timeout=5)
                if not enviar_frame(conn, frame_procesado):
                    break
            except queue.Empty:
                print("Timeout esperando frame procesado")
                
    except Exception as e:
        print(f"Error con cliente {addr}: {e}")
    finally:
        with lock_clientes:
            if conn in clientes_conectados:
                clientes_conectados.remove(conn)
        conn.close()


def manejar_nodo(conn, addr):
    """Maneja la conexión de un nodo de procesamiento"""
    print(f"Nodo de procesamiento conectado desde {addr}")
    
    with lock_nodos:
        nodos_disponibles.append(conn)
    
    try:
        while True:
            try:
                frame = cola_frames_entrada.get(timeout=1)
            except queue.Empty:
                continue
            
            if not enviar_frame(conn, frame):
                print(f"Error al enviar frame al nodo {addr}")
                break
            
            frame_procesado = recibir_frame(conn)
            if frame_procesado is None:
                print(f"Nodo {addr} desconectado")
                break
            
            cola_frames_procesados.put(frame_procesado)
            print(f"Frame procesado recibido del nodo {addr}")
            
    except Exception as e:
        print(f"Error con nodo {addr}: {e}")
    finally:
        with lock_nodos:
            if conn in nodos_disponibles:
                nodos_disponibles.remove(conn)
        conn.close()


def aceptar_conexiones():
    """Acepta conexiones entrantes y las clasifica (cliente o nodo)"""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((Broker_host, Broker_port))
    server_socket.listen(5)
    
    print(f"Servidor central escuchando en {Broker_host}:{Broker_port}")
    
    while True:
        conn, addr = server_socket.accept()
        
        # Recibir identificación (CLIENTE o NODO)
        identificacion = conn.recv(10).decode('utf-8').strip()
        
        if identificacion == "CLIENTE":
            thread = threading.Thread(target=manejar_cliente, args=(conn, addr))
            thread.daemon = True
            thread.start()
        elif identificacion == "NODO":
            thread = threading.Thread(target=manejar_nodo, args=(conn, addr))
            thread.daemon = True
            thread.start()
        else:
            print(f"Identificación desconocida de {addr}: {identificacion}")
            conn.close()


def procesar_frames_a_video():
    """Guarda los frames procesados en un archivo de video"""
    global video_writer, guardando_video
    
    output_filename = f"video_procesado_{int(time.time())}.mp4"
    fourcc = cv2.VideoWriter_fourcc(*'mp4v') #type: ignore
    
    print("Esperando frames para iniciar grabación...")
    
    frame = cola_frames_procesados.get()
    height, width = frame.shape[:2]
    
    video_writer = cv2.VideoWriter(output_filename, fourcc, fps, (width, height))
    guardando_video = True
    
    print(f"Iniciando grabación en {output_filename} ({width}x{height} @ {fps}fps)")
    
    video_writer.write(frame)
    frame_count = 1
    
    try:
        while guardando_video:
            try:
                frame = cola_frames_procesados.get(timeout=5)
                video_writer.write(frame)
                frame_count += 1
                
                if frame_count % 30 == 0: 
                    print(f"Frames guardados: {frame_count}")
                    
            except queue.Empty:
                print("Timeout esperando frames para guardar")
                continue
                
    except KeyboardInterrupt:
        print("\nDeteniendo grabación...")
    finally:
        if video_writer:
            video_writer.release()
        print(f"Video guardado: {output_filename} ({frame_count} frames)")


def enviar_frames_a_nodos():
    """Distribuye frames de la cola de entrada a los nodos disponibles"""
    print("Distribuidor de frames iniciado")
    while True:
        if not nodos_disponibles:
            time.sleep(0.1)
            continue
        
        try:
            frame = cola_frames_entrada.get(timeout=1)
            cola_frames_entrada.put(frame)
        except queue.Empty:
            continue



def main():
    print("=== SERVIDOR CENTRAL DE PROCESAMIENTO DE VIDEO ===")
    
    thread_conexiones = threading.Thread(target=aceptar_conexiones)
    thread_conexiones.daemon = True
    thread_conexiones.start()
    
    print("\nEsperando conexiones de clientes y nodos...")
    print("Presiona Ctrl+C para detener el servidor\n")
    
    try:
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\nCerrando servidor...")


if __name__ == "__main__":
    main()