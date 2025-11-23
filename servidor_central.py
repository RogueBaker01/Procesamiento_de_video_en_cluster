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

def recibir_bytes_exactos(conn, num_bytes):
    data = b""
    while len(data) < num_bytes:
        packet = conn.recv(num_bytes - len(data))
        if not packet:
            return None
        data += packet
    return data

def recibir_paquete(conn):
    try:
        size_data = recibir_bytes_exactos(conn, 4)
        if not size_data: return None
        
        frame_size = int.from_bytes(size_data, byteorder='big')
        
        payload = b""
        while len(payload) < frame_size:
            packet = conn.recv(min(4096, frame_size - len(payload)))
            if not packet: return None
            payload += packet
            
        return payload
    except Exception as e:
        print(f"Error al recibir paquete: {e}")
        return None

def enviar_paquete_generico(conn, payload):
    try:
        size_bytes = len(payload).to_bytes(4, byteorder='big')
        conn.sendall(size_bytes + payload)
        return True
    except Exception as e:
        print(f"Error al enviar paquete: {e}")
        return False

def manejar_cliente(conn, addr):
    print(f"Cliente conectado desde {addr}")
    with lock_clientes:
        clientes_conectados.append(conn)
    
    try:
        while True:
            payload = recibir_paquete(conn)
            if payload is None:
                print(f"Cliente {addr} desconectado o fin de transmisión")
                break
            
            cola_frames_entrada.put(payload)
            
            try:
                while not cola_frames_procesados.empty():
                    payload_procesado = cola_frames_procesados.get_nowait()
                    if not enviar_paquete_generico(conn, payload_procesado):
                        return
            except:
                pass
                
    except Exception as e:
        print(f"Error con cliente {addr}: {e}")
    finally:
        with lock_clientes:
            if conn in clientes_conectados: clientes_conectados.remove(conn)
        conn.close()

def manejar_nodo(conn, addr):
    print(f"Nodo conectado desde {addr}")
    with lock_nodos:
        nodos_disponibles.append(conn)
    
    try:
        while True:
            try:
                payload = cola_frames_entrada.get(timeout=1)
            except queue.Empty:
                continue
            
            if not enviar_paquete_generico(conn, payload):
                print(f"Error enviando a nodo {addr}")
                cola_frames_entrada.put(payload)
                break
            
            payload_procesado = recibir_paquete(conn)
            if payload_procesado is None:
                print(f"Nodo {addr} desconectado esperando respuesta")
                cola_frames_entrada.put(payload)
                break
            
            cola_frames_procesados.put(payload_procesado)
            print(f"Frame procesado recibido del nodo {addr}")
            
    except Exception as e:
        print(f"Error con nodo {addr}: {e}")
    finally:
        with lock_nodos:
            if conn in nodos_disponibles: nodos_disponibles.remove(conn)
        conn.close()

def aceptar_conexiones():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((Broker_host, Broker_port))
    server_socket.listen(5)
    
    print(f"Servidor central escuchando en {Broker_host}:{Broker_port}")
    
    while True:
        conn, addr = server_socket.accept()
        
        try:
            identificacion = recibir_bytes_exactos(conn, 10)
            if not identificacion:
                conn.close()
                continue
                
            id_str = identificacion.decode('utf-8').strip()
            
            if id_str == "CLIENTE":
                t = threading.Thread(target=manejar_cliente, args=(conn, addr))
                t.daemon = True
                t.start()
            elif id_str == "NODO":
                t = threading.Thread(target=manejar_nodo, args=(conn, addr))
                t.daemon = True
                t.start()
            else:
                print(f"ID desconocida: {id_str}")
                conn.close()
        except Exception as e:
            print(f"Error en handshake: {e}")
            conn.close()

def main():
    t = threading.Thread(target=aceptar_conexiones)
    t.daemon = True
    t.start()
    
    while True:
        try:
            if clientes_conectados and not cola_frames_procesados.empty():
                payload = cola_frames_procesados.get(timeout=0.1)
                if not enviar_paquete_generico(clientes_conectados[0], payload):
                    cola_frames_procesados.put(payload)
            else:
                time.sleep(0.01)
        except:
            pass

if __name__ == "__main__":
    main()