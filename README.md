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
│  │  Ensamblador │   │ ← **NUEVO**
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

### Ventajas de la Nueva Arquitectura

- ✅ **Cliente más ligero**: No necesita OpenCV para ensamblar video
- ✅ **Menos tráfico de red**: Un solo video vs múltiples frames
- ✅ **Control centralizado**: El servidor gestiona la calidad final
- ✅ **Mejor escalabilidad**: Clientes con recursos limitados

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

Para ejecutar en red local, modifica las IPs en el código.

## 📊 Formatos Soportados

- MP4
- AVI
- MOV
- MKV

## ✨ Características de la Nueva Versión

### Interfaz de Usuario Mejorada
- 🎨 Diseño moderno con gradientes y colores atractivos
- 📊 Métricas en tiempo real (frames enviados, velocidad)
- 📈 Barra de progreso detallada
- ✅ Mensajes de estado informativos con emojis
- 🎬 Previsualización de video antes y después

### Mejoras de Código
- 📝 Documentación completa con docstrings
- 🔒 Manejo robusto de errores con excepciones específicas
- 📋 Logging estructurado con timestamps
- 🧹 Limpieza automática de archivos temporales
- ⚙️ Constantes de configuración bien organizadas

### Mejoras de Arquitectura
- 🎯 Servidor ensambla el video (lógica centralizada)
- 📦 Protocolo JSON para metadata
- 🔄 Gestión de sesiones por cliente
- 🚀 Mejor escalabilidad y rendimiento

## ⚠️ Notas Importantes

- Los nodos deben estar conectados antes de procesar un video
- La calidad de compresión JPEG está configurada al 90%
- El sistema usa sockets TCP para comunicación confiable
- Los frames se transmiten como imágenes JPEG codificadas
- El video final se ensambla en el servidor, no en el cliente

## 🐛 Solución de Problemas

### El cliente no se conecta al servidor
- Verifica que el servidor central esté ejecutándose
- Confirma que el puerto 8080 no esté en uso por otra aplicación
- Revisa la configuración de firewall
- Verifica que la IP del servidor sea correcta en `cliente.py`

### Los nodos no procesan frames
- Asegúrate de tener al menos un nodo conectado antes de enviar el video
- Verifica que los nodos se hayan conectado correctamente al servidor
- Revisa los logs del servidor para ver si hay errores

### El video procesado no se descarga
- Revisa los permisos de escritura en el directorio temporal
- Verifica que haya suficiente espacio en disco
- Comprueba que el servidor haya ensamblado correctamente el video

### Error "Tiempo de conexión agotado"
- Verifica que el servidor esté ejecutándose
- Comprueba la conectividad de red
- Aumenta `CONNECTION_TIMEOUT` si la red es lenta

## 📝 Registro de Cambios

### v2.0 (Diciembre 2025)
- ✅ Nueva arquitectura: servidor ensambla el video
- ✅ Interfaz de usuario moderna y amigable
- ✅ Logging mejorado con timestamps
- ✅ Documentación completa en código
- ✅ Manejo robusto de errores
- ✅ Validación de archivos
- ✅ Limpieza automática de temporales

### v1.0 (Inicial)
- Arquitectura básica cliente-servidor-nodo
- Procesamiento distribuido de frames
- Filtros cinemáticos básicos

## 👥 Autores

Proyecto desarrollado para el curso de Sistemas Distribuidos - 5to Semestre

## 📝 Licencia

Este proyecto es de uso educativo.

