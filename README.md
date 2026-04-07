# 📦 Respaldo Puerto Bot

Sistema automatizado de respaldo de fotografías para contenedores, diseñado para optimizar el flujo de trabajo en operaciones portuarias. Este bot permite la captura, validación y almacenamiento organizado tanto en local (servidor de oficina) como en la nube (Telegram).

## 🚀 Características Principales

* **Validación con Regex:** Filtra códigos de contenedores bajo el formato estándar (4 letras y 7 números).
* **Gestión de Concurrencia:** Implementación de `threading.Lock` para evitar condiciones de carrera (Race Conditions) al recibir múltiples fotos en ráfaga.
* **Almacenamiento Organizado:** Creación automática de directorios por Año/Mes/Código_Contenedor.
* **Sistema de Debounce:** Uso de `threading.Timer` para enviar una única confirmación al usuario tras finalizar la carga masiva de archivos.
* **Seguridad:** Gestión de credenciales mediante variables de entorno (`.env`).

## 🛠️ Tecnologías Utilizadas

* **Lenguaje:** Python 3.x
* **Librería API:** `pyTelegramBotAPI` (Telebot)
* **Concurrencia:** `threading`
* **Variables de Entorno:** `python-dotenv`

## 📋 Requisitos Previos

Antes de ejecutar el proyecto, asegúrate de tener instalado:
* Python 3.10 o superior
* Un bot de Telegram (creado vía @BotFather)
* Un canal de Telegram donde el bot sea administrador

## ⚙️ Instalación y Configuración

1. **Clona el repositorio:**
   ```
   git clone [https://github.com/VitoNez5198/Respaldo_Puerto_Bot.git](https://github.com/VitoNez5198/Respaldo_Puerto_Bot)
   cd Respaldo_Puerto_Bot

2. **Crea y activa un entorno virtual:**

```
python -m venv venv
source venv/Scripts/activate  # En Windows
```

3. **Instala las dependencias:**

```
pip install -r requirements.txt
```

4. **Configura tus credenciales:**
Crea un archivo .env en la raíz del proyecto con el siguiente formato:

```bash
TOKEN_TELEGRAM=tu_token_aqui
ID_CANAL=tu_id_de_canal
RUTA_BASE=D:\Ruta\Hacia\Tus\Archivos
```

## 🖥️ Uso

1. Ejecuta el bot: `python bot.py`

2. Envía el código del contenedor al chat privado del bot (Ej: `ABCD1234560`).

3. Envía las fotografías (individuales o en grupo).

4. El bot responderá con una confirmación final cuando todos los archivos hayan sido procesados y respaldados.

Proyecto desarrollado como parte de la formación en Ingeniería en Informática.