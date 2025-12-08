import socket
import cv2
import numpy as np

SERVIDOR_HOST = 'localhost'
SERVIDOR_PORT = 8080
JPEG_QUALITY = 90
VIGNETTE_SIGMA = 0.6
BAR_HEIGHT_RATIO = 0.12

class CineFilter:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.vignette_mask = self._create_vignette_mask(width, height)
        self.lut_contrast = self._create_s_curve_lut()
    
    def _create_s_curve_lut(self):
        lut = np.zeros((256, 1), dtype='uint8')
        for i in range(256):
            v = 255.0 / (1 + np.exp(-((i - 128) / 32.0)))
            lut[i][0] = int(v)
        return lut
    
    def _create_vignette_mask(self, width, height):
        kernel_x = cv2.getGaussianKernel(width, width * VIGNETTE_SIGMA)
        kernel_y = cv2.getGaussianKernel(height, height * VIGNETTE_SIGMA)
        
        kernel = kernel_y * kernel_x.T
        mask = kernel / kernel.max()
        
        return mask
    
    def apply_teal_orange(self, frame):
        b, g, r = cv2.split(frame)
        
        b = b.astype(float) * 1.15
        r = r.astype(float) * 1.15
        g = g.astype(float) * 0.95
        
        merged = cv2.merge([b, g, r])
        merged = np.clip(merged, 0, 255).astype(np.uint8)
        
        return merged
    
    def apply_cinematic_style(self, frame):
        frame_colored = self.apply_teal_orange(frame)
        
        frame_contrast = cv2.LUT(frame_colored, self.lut_contrast)
        
        frame_float = frame_contrast.astype(float)
        frame_float[:, :, 0] *= self.vignette_mask
        frame_float[:, :, 1] *= self.vignette_mask
        frame_float[:, :, 2] *= self.vignette_mask
        frame_final = frame_float.astype(np.uint8)
        
        bar_height = int(self.height * BAR_HEIGHT_RATIO)
        cv2.rectangle(frame_final, (0, 0), (self.width, bar_height), (0, 0, 0), -1)
        cv2.rectangle(frame_final, (0, self.height - bar_height), (self.width, self.height), (0, 0, 0), -1)
        
        return frame_final

def recibir_bytes_exactos(conn, num_bytes):
    data = b""
    while len(data) < num_bytes:
        try:
            packet = conn.recv(num_bytes - len(data))
            if not packet:
                return None
            data += packet
        except Exception as e:
            print(f"[ERROR] Error recibiendo bytes: {e}")
            return None
    return data

def recibir_paquete_con_id(conn):
    try:
        size_data = recibir_bytes_exactos(conn, 4)
        if not size_data:
            return None, None
        total_size = int.from_bytes(size_data, byteorder='big')
        
        payload = b""
        while len(payload) < total_size:
            packet = conn.recv(min(4096, total_size - len(payload)))
            if not packet:
                return None, None
            payload += packet
        
        frame_id = int.from_bytes(payload[:4], byteorder='big')
        img_data = payload[4:]
        
        nparr = np.frombuffer(img_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            print(f"[ERROR] No se pudo decodificar frame ID {frame_id}")
            return None, None
        
        return frame_id, frame
        
    except Exception as e:
        print(f"[ERROR] Error recibiendo paquete: {e}")
        return None, None

def enviar_paquete_con_id(conn, frame_id, frame):
    try:
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        img_bytes = buffer.tobytes()
        
        id_bytes = frame_id.to_bytes(4, byteorder='big')
        payload = id_bytes + img_bytes
        
        size_bytes = len(payload).to_bytes(4, byteorder='big')
        conn.sendall(size_bytes + payload)
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Error enviando paquete: {e}")
        return False

def main():
    print("="*60)
    print("Nodo de Procesamiento - Sistema Distribuido de Video")
    print("="*60)
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        print(f"[INFO] Conectando a {SERVIDOR_HOST}:{SERVIDOR_PORT}...")
        sock.connect((SERVIDOR_HOST, SERVIDOR_PORT))
        
        sock.sendall(b"NODO".ljust(10))
        print(f"[INFO] Conectado exitosamente al servidor central")
        
        cine_filter = None
        frames_procesados = 0
        
        print("[INFO] Esperando frames para procesar...")
        
        while True:
            frame_id, frame = recibir_paquete_con_id(sock)
            
            if frame is None:
                print("[INFO] Servidor cerró la conexión")
                break
            
            if cine_filter is None:
                h, w = frame.shape[:2]
                cine_filter = CineFilter(w, h)
                print(f"[INFO] Filtro cinemático configurado para resolución {w}x{h}")
            
            print(f"[INFO] Procesando Frame ID: {frame_id}")
            frame_procesado = cine_filter.apply_cinematic_style(frame)
            
            if not enviar_paquete_con_id(sock, frame_id, frame_procesado):
                print(f"[ERROR] Error enviando frame ID {frame_id}")
                break
            
            frames_procesados += 1
            print(f"[INFO] Frame ID: {frame_id} completado (Total: {frames_procesados})")
        
        print(f"[INFO] Total de frames procesados: {frames_procesados}")
        
    except ConnectionRefusedError:
        print("[ERROR] Conexión rechazada. Verifica que el servidor esté ejecutándose.")
    except Exception as e:
        print(f"[ERROR] Error inesperado: {e}")
    finally:
        sock.close()
        print("[INFO] Desconectado del servidor")

if __name__ == "__main__":
    main()