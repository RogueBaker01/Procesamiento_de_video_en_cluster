import socket
import cv2
import numpy as np

ip_address_servidor_central = '192.168.1.170'
port_Servidor_Central = 8080

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
            lut[i][0] = v
        return lut

    def _create_vignette_mask(self, width, height):
        sigma = 0.6
        kernel_x = cv2.getGaussianKernel(width, width * sigma)
        kernel_y = cv2.getGaussianKernel(height, height * sigma)
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
        
        bar_height = int(self.height * 0.12)
        cv2.rectangle(frame_final, (0, 0), (self.width, bar_height), (0, 0, 0), -1)
        cv2.rectangle(frame_final, (0, self.height - bar_height), (self.width, self.height), (0, 0, 0), -1)
        return frame_final

def recibir_paquete_con_id(conn):
    size_data = b""
    while len(size_data) < 4:
        packet = conn.recv(4 - len(size_data))
        if not packet: return None, None
        size_data += packet
    total_size = int.from_bytes(size_data, byteorder='big')
    
    payload = b""
    while len(payload) < total_size:
        packet = conn.recv(min(4096, total_size - len(payload)))
        if not packet: return None, None
        payload += packet
        
    frame_id = int.from_bytes(payload[:4], byteorder='big')
    img_data = payload[4:]
    
    nparr = np.frombuffer(img_data, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    return frame_id, frame

def enviar_paquete_con_id(conn, frame_id, frame):
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    img_bytes = buffer.tobytes()
    
    id_bytes = frame_id.to_bytes(4, byteorder='big')
    payload = id_bytes + img_bytes
    
    size_bytes = len(payload).to_bytes(4, byteorder='big')
    conn.sendall(size_bytes + payload)

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((ip_address_servidor_central, port_Servidor_Central))
        
        sock.sendall(b"NODO".ljust(10))
        print(f"Conectado al servidor {ip_address_servidor_central}")
        
        cine_filter = None
        
        while True:
            frame_id, frame = recibir_paquete_con_id(sock)
            
            if frame is None:
                print("Servidor cerró conexión")
                break
            
            if cine_filter is None:
                h, w = frame.shape[:2]
                cine_filter = CineFilter(w, h)
                print(f"Configurado filtro para {w}x{h}")
            
            frame_proc = cine_filter.apply_cinematic_style(frame)
            
            enviar_paquete_con_id(sock, frame_id, frame_proc)
            print(f"Procesado Frame ID: {frame_id}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    main()