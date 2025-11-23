import socket
import cv2
import numpy as np

ip_address_servidor_central = 'localhost'
port_Servidor_Central = 8080

socket_servidor_central = socket.socket(socket.AF_INET, socket.SOCK_STREAM)


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
        
        b = b.astype(float)
        g = g.astype(float)
        r = r.astype(float)
        
        b = b * 1.15 
        
        r = r * 1.15
        
        g = g * 0.95

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

def recibir_frame(conn):
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

def enviar_frame(conn, frame):
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    data = buffer.tobytes()
    
    size_bytes = len(data).to_bytes(4, byteorder='big')
    conn.sendall(size_bytes + data)

def main():
    try:
        socket_servidor_central.connect((ip_address_servidor_central, port_Servidor_Central))
        
        # Identificarse como NODO
        socket_servidor_central.sendall(b"NODO")
        
        print(f"Conectado al servidor central en {ip_address_servidor_central}:{port_Servidor_Central}")
        
        cine_filter = None
        
        while True:
            frame = recibir_frame(socket_servidor_central)
            
            if frame is None:
                print("Conexión cerrada por el servidor")
                break
            
            if cine_filter is None:
                height, width = frame.shape[:2]
                cine_filter = CineFilter(width, height)
                print(f"Filtro inicializado con dimensiones: {width}x{height}")
            
            frame_procesado = cine_filter.apply_cinematic_style(frame)
            
            enviar_frame(socket_servidor_central, frame_procesado)
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        socket_servidor_central.close()
        print("Conexión cerrada")

if __name__ == "__main__":
    main()