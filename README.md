# Sistema Distribuido de Procesamiento de Video

Sistema de procesamiento de video distribuido que aplica filtros cinemáticos a videos mediante una arquitectura cliente-servidor con nodos de procesamiento paralelo.

## 📋 Descripción

Este proyecto implementa un sistema distribuido para procesar videos aplicando efectos cinemáticos (filtro teal-orange, viñeta, barras cinemáticas). La arquitectura permite escalar el procesamiento mediante múltiples nodos de procesamiento que trabajan en paralelo.

### Componentes del Sistema

1. **Cliente (`cliente.py`)**: Interfaz web con Streamlit para cargar videos y visualizar resultados
2. **Servidor Central (`servidor_central.py`)**: Coordina la distribución de frames entre clientes y nodos
3. **Nodo de Procesamiento (`Nodo_Procesamiento.py`)**: Aplica los filtros cinemáticos a cada frame

## 🎨 Efectos Aplicados

- **Filtro Teal-Orange**: Ajuste de colores cinematográfico
- **Curva de Contraste**: Mejora el contraste mediante curva S
- **Viñeta**: Oscurecimiento gradual en los bordes
- **Barras Cinemáticas**: Formato panorámico (letterbox)

## 🛠️ Requisitos

```txt
streamlit
opencv-python (cv2)
numpy
```

### Instalación

```bash
pip install streamlit opencv-python numpy
```

## 🚀 Uso

### 1. Iniciar el Servidor Central

```bash
python servidor_central.py
```

El servidor escuchará en `localhost:8080` y esperará conexiones de clientes y nodos.

### 2. Iniciar Nodos de Procesamiento

Puedes iniciar múltiples nodos para procesamiento paralelo:

```bash
python Nodo_Procesamiento.py
```

Inicia tantos nodos como desees para aumentar la velocidad de procesamiento.

### 3. Iniciar el Cliente

```bash
streamlit run cliente.py
```

Esto abrirá una interfaz web en tu navegador (por defecto en `http://localhost:8501`).

## 📖 Flujo de Trabajo

1. El usuario carga un video a través de la interfaz Streamlit
2. El cliente envía los frames al servidor central
3. El servidor distribuye los frames a los nodos disponibles
4. Los nodos aplican el filtro cinemático y devuelven los frames procesados
5. El servidor retorna los frames al cliente
6. El cliente reconstruye el video procesado y permite descargarlo

## 🏗️ Arquitectura

```
┌─────────────┐
│   Cliente   │ (Streamlit UI)
│ (cliente.py)│
└──────┬──────┘
       │
       │ Socket TCP
       │ (localhost:8080)
       │
┌──────▼──────────────┐
│ Servidor Central    │
│(servidor_central.py)│
│                     │
│  ┌──────────────┐   │
│  │ Cola Entrada │   │
│  └──────┬───────┘   │
│         │           │
│  ┌──────▼───────┐   │
│  │Cola Procesados│  │
│  └──────────────┘   │
└──────┬──────────────┘
       │
       │ Distribuye frames
       │
   ┌───┴───┬───────┬───────┐
   │       │       │       │
┌──▼──┐ ┌──▼──┐ ┌──▼──┐ ┌──▼──┐
│Nodo1│ │Nodo2│ │Nodo3│ │Nodo*│
└─────┘ └─────┘ └─────┘ └─────┘
```

## 🔧 Configuración

### Servidor Central
- **Host**: `0.0.0.0` (escucha en todas las interfaces)
- **Puerto**: `8080`

### Cliente
- **SERVER_HOST**: `localhost`
- **SERVER_PORT**: `8080`

### Nodo de Procesamiento
- **ip_address_servidor_central**: `localhost`
- **port_Servidor_Central**: `8080`

Para ejecutar en red, modifica `localhost` por la IP del servidor central.

## 📊 Formatos Soportados

- MP4
- AVI
- MOV
- MKV

## ⚠️ Notas Importantes

- Los nodos deben estar conectados antes de procesar un video
- La calidad de compresión JPEG está configurada al 90%
- El sistema usa sockets TCP para comunicación confiable
- Los frames se transmiten como imágenes JPEG codificadas

## 🐛 Solución de Problemas

### El cliente no se conecta al servidor
- Verifica que el servidor central esté ejecutándose
- Confirma que el puerto 8080 no esté en uso por otra aplicación
- Revisa la configuración de firewall

### Los nodos no procesan frames
- Asegúrate de tener al menos un nodo conectado antes de enviar el video
- Verifica que los nodos se hayan conectado correctamente al servidor

### El video procesado no se descarga
- Revisa los permisos de escritura en el directorio temporal
- Verifica que haya suficiente espacio en disco

## 👥 Autores

Proyecto desarrollado para el curso de Sistemas Distribuidos - 5to Semestre

## 📝 Licencia

Este proyecto es de uso educativo.
