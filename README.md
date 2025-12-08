# Sistema Distribuido de Procesamiento de Video

Sistema de procesamiento de video distribuido que aplica filtros cinemáticos a videos mediante una arquitectura cliente-servidor con nodos de procesamiento paralelo.

## 📋 Descripción

Este proyecto implementa un sistema distribuido para procesar videos aplicando efectos cinemáticos (filtro teal-orange, viñeta, barras cinemáticas). La arquitectura permite escalar el procesamiento mediante múltiples nodos de procesamiento que trabajan en paralelo.

### Componentes del Sistema

1. **Cliente (`cliente.py`)**: Interfaz web moderna con Streamlit para cargar videos y descargar resultados
2. **Servidor Central (`servidor_central.py`)**: Coordina la distribución de frames y ensambla el video final
3. **Nodo de Procesamiento (`Nodo_Procesamiento.py`)**: Aplica los filtros cinemáticos a cada frame

## 🎨 Efectos Aplicados

- **Filtro Teal-Orange**: Ajuste de colores cinematográfico profesional
- **Curva de Contraste S**: Mejora el contraste mediante curva S
- **Viñeta**: Oscurecimiento gradual en los bordes usando distribución gaussiana
- **Barras Cinemáticas**: Formato panorámico (letterbox)

## 🏗️ Arquitectura

### Nueva Arquitectura (v2.0)

```
┌─────────────┐
│   Cliente   │ (Streamlit UI)
│ (cliente.py)│
└──────┬──────┘
       │
       │ 1. Envía metadata + frames
       │ 2. Recibe video completo
       │
┌──────▼──────────────┐
│ Servidor Central    │
│(servidor_central.py)│
│                     │
│  Gestión Sesiones   │
│  ┌──────────────┐   │
│  │ Cola Entrada │   │
│  └──────┬───────┘   │
│         │           │
│  ┌──────▼───────┐   │
│  │  Ensamblador │   │
│  │  de Video    │   │
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

El servidor escuchará en `0.0.0.0:8080` y esperará conexiones de clientes y nodos.

**Salida esperada:**
```
[2025-12-07 21:00:00] [INFO] === Sistema Distribuido de Procesamiento de Video ===
[2025-12-07 21:00:00] [INFO] Iniciando servidor central...
[2025-12-07 21:00:00] [INFO] Servidor central escuchando en 0.0.0.0:8080
```

### 2. Iniciar Nodos de Procesamiento

Puedes iniciar múltiples nodos para procesamiento paralelo:

```bash
python Nodo_Procesamiento.py
```

Inicia tantos nodos como desees para aumentar la velocidad de procesamiento.

**Salida esperada:**
```
============================================================
Nodo de Procesamiento - Sistema Distribuido de Video
============================================================
[INFO] Conectando a 148.220.210.115:8080...
[INFO] Conectado exitosamente al servidor central
[INFO] Esperando frames para procesar...
```

### 3. Iniciar el Cliente

```bash
streamlit run cliente.py
```

Esto abrirá una interfaz web moderna en tu navegador (por defecto en `http://localhost:8501`).

## 📖 Flujo de Trabajo

1. El usuario carga un video a través de la interfaz Streamlit
2. El cliente envía **metadata** (fps, resolución, total de frames) al servidor
3. El cliente envía todos los frames al servidor central
4. El servidor distribuye los frames a los nodos disponibles
5. Los nodos aplican el filtro cinemático y devuelven los frames procesados
6. El servidor **ensambla el video completo** (MP4)
7. El servidor envía el video procesado completo al cliente
8. El cliente permite visualizar y descargar el video

## 🔧 Configuración

### Servidor Central
- **Host**: `0.0.0.0` (escucha en todas las interfaces)
- **Puerto**: `8080`
- **Max Payload Size**: `10 MB`
- **Buffer Size**: `4096 bytes`

### Cliente
- **SERVER_HOST**: `148.220.211.237` (configurable en código)
- **SERVER_PORT**: `8080`
- **JPEG_QUALITY**: `90`
- **MAX_FILE_SIZE_MB**: `500`

### Nodo de Procesamiento
- **SERVIDOR_HOST**: `148.220.210.115` (configurable en código)
- **SERVIDOR_PORT**: `8080`
- **JPEG_QUALITY**: `90`
- **VIGNETTE_SIGMA**: `0.6`

## 📊 Formatos Soportados

- MP4
- AVI
- MOV
- MKV

## ✨ Características de la Nueva Versión

## 📝 Licencia

Este proyecto es de uso educativo.


