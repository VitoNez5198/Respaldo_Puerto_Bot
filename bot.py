import os
import re
import telebot
import threading
from datetime import datetime
from threading import Lock, Timer 
from dotenv import load_dotenv

# ==========================================
# ⚙️ CONFIGURACIÓN Y VARIABLES GLOBALES
# ==========================================
load_dotenv()

TOKEN = os.getenv('TOKEN_TELEGRAM')
ID_CANAL = os.getenv('ID_CANAL')
RUTA_BASE = os.getenv('RUTA_BASE')

bot = telebot.TeleBot(TOKEN)

# Control de estado y concurrencia
semaforo = Lock()
estado_usuarios = {}
timers_usuarios = {} 

print("🤖 Iniciando el servidor del bot...")

# ==========================================
# 📩 FUNCIONES DE APOYO
# ==========================================

def enviar_confirmacion_final(chat_id, codigo):
    """Envía un mensaje resumen tras una ráfaga de fotos."""
    if chat_id in estado_usuarios and estado_usuarios[chat_id]['codigo'] == codigo:
        # Si ya se envió un aviso para este proceso, no repetimos
        if estado_usuarios[chat_id].get('avisado', False):
            return
            
        bot.send_message(
            chat_id, 
            f"✅ ¡Todo listo!\nLa carpeta del contenedor **{codigo}** se ha guardado y respaldado con éxito."
        )
        print(f"[SISTEMA] Confirmación enviada para {codigo}")
        estado_usuarios[chat_id]['avisado'] = True

# ==========================================
# 🚀 RUTAS DEL BOT (Handlers)
# ==========================================

@bot.message_handler(commands=['start', 'ayuda'])
def enviar_bienvenida(message):
    texto = (
        "👋 ¡Hola! Soy tu bot de respaldos.\n\n"
        "Para empezar, escríbeme el código del contenedor.\n"
        "Formato: 4 letras y 7 números (Ej: ABCD1234560)."
    )
    bot.reply_to(message, texto)

@bot.message_handler(content_types=['text'])
def validar_codigo(message):
    id_chat = message.chat.id
    # Limpieza de entrada: mayúsculas y quita espacios/guiones
    codigo_limpio = message.text.strip().upper().replace("-", "").replace(" ", "")
    patron = r"^[A-Z]{4}\d{7}$"
    
    if re.match(patron, codigo_limpio):
        estado_usuarios[id_chat] = {
            'codigo': codigo_limpio,
            'contador': 1,
            'avisado': False
        }
        bot.reply_to(message, f"✅ Código validado: {codigo_limpio}\n\n📸 Ahora envíame las fotos de este contenedor.")
        print(f"[+] Preparado para recibir fotos de: {codigo_limpio}")
    else:
        bot.reply_to(message, "❌ Código inválido. Recuerda: 4 letras seguidas de 7 números.")

@bot.message_handler(content_types=['photo'])
def recibir_fotos(message):
    id_chat = message.chat.id
    
    if id_chat not in estado_usuarios:
        bot.reply_to(message, "⚠️ Primero escribe el código del contenedor.")
        return

    # --- INICIO DEL SEMÁFORO (Thread Safe) ---
    with semaforo:
        # Si llegan fotos nuevas, reseteamos el estado de 'avisado'
        estado_usuarios[id_chat]['avisado'] = False 
        
        codigo_actual = estado_usuarios[id_chat]['codigo']
        contador_actual = estado_usuarios[id_chat]['contador']
        
        try:
            # 1. Crear estructura de carpetas
            ahora = datetime.now()
            ruta_carpeta_final = os.path.join(RUTA_BASE, ahora.strftime("%Y"), ahora.strftime("%m"), codigo_actual)
            os.makedirs(ruta_carpeta_final, exist_ok=True)
            
            # 2. Descargar archivo
            file_info = bot.get_file(message.photo[-1].file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            # 3. Guardar en disco duro
            nombre_archivo = f"{codigo_actual}_{contador_actual}.jpg"
            ruta_archivo = os.path.join(ruta_carpeta_final, nombre_archivo)
            
            with open(ruta_archivo, 'wb') as new_file:
                new_file.write(downloaded_file)
            
            # Actualizamos contador para la siguiente foto
            estado_usuarios[id_chat]['contador'] += 1
            print(f"[LOCAL] {nombre_archivo} guardado con éxito.")
            
        except Exception as e:
            print(f"❌ Error Local: {e}")
            return
    # --- FIN DEL SEMÁFORO ---

    # --- RESPALDO EN LA NUBE (Independiente) ---
    try:
        # Limpiamos el ID por si acaso viene con espacios del .env
        id_canal_limpio = int(str(ID_CANAL).strip())
        bot.send_photo(
            id_canal_limpio, 
            message.photo[-1].file_id, 
            caption=f"📦 {codigo_actual} - Foto {contador_actual}"
        )
    except Exception as e:
        print(f"❌ Error Nube: {e}")

    # --- LÓGICA DE CONFIRMACIÓN (Debounce de 5 segundos) ---
    if id_chat in timers_usuarios:
        timers_usuarios[id_chat].cancel()

    t = Timer(5.0, enviar_confirmacion_final, args=[id_chat, codigo_actual])
    timers_usuarios[id_chat] = t
    t.start()

# ==========================================
# LANZAMIENTO
# ==========================================
if __name__ == "__main__":
    print("✅ Bot conectado. Esperando mensajes...")
    bot.infinity_polling()