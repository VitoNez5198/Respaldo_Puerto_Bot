import os
import re
import telebot
from datetime import datetime
from threading import Lock, Timer 
from dotenv import load_dotenv
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

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
memoria_contenedores = {} # Memoria global para recordar contenedores

print("🤖 Iniciando el servidor del bot...")

# ==========================================
# 📩 FUNCIONES DE APOYO
# ==========================================

def pedir_cliente(chat_id, codigo):
    """Envía el menú de clientes o confirma si es un contenedor retomado."""
    if chat_id in estado_usuarios and estado_usuarios[chat_id]['codigo'] == codigo:
        # Evitamos mensajes duplicados
        if estado_usuarios[chat_id].get('avisado', False):
            return
            
        estado = estado_usuarios[chat_id]
        estado['avisado'] = True
        
        # --- LÓGICA DE OMISIÓN ---
        if estado.get('es_retome') == True:
            estado['paso'] = 'completado'
            bot.send_message(
                chat_id, 
                f"✅ ¡Fotos extra guardadas para el contenedor **{codigo}**!\n*(Se mantuvieron el cliente {estado['cliente']} y la nave {estado['nave']})*",
                parse_mode="Markdown"
            )
        else:
            # Flujo normal para contenedores nuevos
            bot.send_message(
                chat_id, 
                f"✅ ¡Fotos recibidas para el contenedor **{codigo}**!\n\n¿A qué cliente pertenece?",
                reply_markup=generar_menu_clientes(),
                parse_mode="Markdown"
            )
        print(f"[SISTEMA] Fin de ráfaga para {codigo}")
        
def generar_menu_clientes():
    markup = InlineKeyboardMarkup()
    
    b1 = InlineKeyboardButton("ARAUCO", callback_data="cliente_ARAUCO")
    b2 = InlineKeyboardButton("CMPC", callback_data="cliente_CMPC")
    b3 = InlineKeyboardButton("MASISA", callback_data="cliente_MASISA")
    b4 = InlineKeyboardButton("OCHOCO", callback_data="cliente_OCHOCO")
    b5 = InlineKeyboardButton("DAVISON", callback_data="cliente_DAVISON")
    
    markup.row(b1, b2)
    markup.row(b3, b4)
    markup.row(b5)
    
    return markup

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
def manejar_textos(message):
    id_chat = message.chat.id
    estado = estado_usuarios.get(id_chat, {})

    # --- LÓGICA 1: ESPERANDO NOMBRE DE LA NAVE ---
    if estado.get('paso') == 'nave':
        nombre_nave = message.text.strip().upper()
        estado_usuarios[id_chat]['nave'] = nombre_nave
        estado_usuarios[id_chat]['paso'] = 'completado' 
        
        codigo_actual = estado['codigo']
        # Guardamos en memoria global
        memoria_contenedores[codigo_actual] = {
            'cliente': estado['cliente'],
            'nave': nombre_nave
        }
        
        bot.reply_to(message, f"✅ ¡Todo guardado!\nContenedor: {codigo_actual}\nCliente: {estado['cliente']}\nNave: {nombre_nave}\n\n(Puedes ingresar un nuevo contenedor cuando quieras).")
        print(f"[+] Datos completos para {codigo_actual}")
        return

    # --- LÓGICA 2: ESPERANDO CÓDIGO DEL CONTENEDOR ---
    codigo_limpio = message.text.strip().upper().replace("-", "").replace(" ", "")
    patron = r"^[A-Z]{4}\d{7}$"
    
    if re.match(patron, codigo_limpio):
        datos_previos = memoria_contenedores.get(codigo_limpio)
        
        if datos_previos:
            estado_usuarios[id_chat] = {
                'codigo': codigo_limpio,
                'contador': 1,
                'avisado': False,
                'paso': 'fotos',
                'cliente': datos_previos['cliente'],
                'nave': datos_previos['nave'],
                'es_retome': True
            }
            bot.reply_to(message, f"🔄 Retomando contenedor: {codigo_limpio}\n*(Ya registrado con {datos_previos['cliente']} | Nave: {datos_previos['nave']})*\n\n📸 Envíame las fotos extra.")
        else:
            estado_usuarios[id_chat] = {
                'codigo': codigo_limpio,
                'contador': 1,
                'avisado': False,
                'paso': 'fotos',
                'cliente': None,
                'nave': None,
                'es_retome': False
            }
            bot.reply_to(message, f"✅ Código validado: {codigo_limpio}\n\n📸 Ahora envíame las fotos de este contenedor.")
    else:
        bot.reply_to(message, "❌ Código inválido. Recuerda: 4 letras seguidas de 7 números o verifica que no estés escribiendo la nave antes de tiempo.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('cliente_'))
def procesar_seleccion_cliente(call):
    id_chat = call.message.chat.id
    # Extraemos el nombre real quitando el prefijo interno
    cliente_seleccionado = call.data.replace("cliente_", "") 
    
    if id_chat in estado_usuarios:
        estado_usuarios[id_chat]['cliente'] = cliente_seleccionado
        estado_usuarios[id_chat]['paso'] = 'nave' 
        
    # Esto apaga el relojito de "cargando" en el botón
    bot.answer_callback_query(call.id) 
    
    bot.edit_message_text(
        chat_id=id_chat,
        message_id=call.message.message_id,
        text=f"✅ Seleccionaste: **{cliente_seleccionado}**",
        parse_mode="Markdown"
    )
    
    bot.send_message(id_chat, "🚢 Ahora, por favor escribe el nombre de la nave:")
    
@bot.message_handler(content_types=['photo'])
def recibir_fotos(message):
    id_chat = message.chat.id
    
    if id_chat not in estado_usuarios or estado_usuarios[id_chat].get('paso') != 'fotos':
        bot.reply_to(message, "⚠️ Primero escribe el código del contenedor.")
        return

    with semaforo:
        estado_usuarios[id_chat]['avisado'] = False 
        codigo_actual = estado_usuarios[id_chat]['codigo']
        contador_actual = estado_usuarios[id_chat]['contador']
        
        try:
            ahora = datetime.now()
            ruta_carpeta_final = os.path.join(RUTA_BASE, ahora.strftime("%Y"), ahora.strftime("%m"), codigo_actual)
            os.makedirs(ruta_carpeta_final, exist_ok=True)
            
            file_info = bot.get_file(message.photo[-1].file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            timestamp = ahora.strftime("%Y%m%d_%H%M%S")
            nombre_archivo = f"{codigo_actual}_{timestamp}.jpg"
            ruta_archivo = os.path.join(ruta_carpeta_final, nombre_archivo)
            
            with open(ruta_archivo, 'wb') as new_file:
                new_file.write(downloaded_file)
            
            estado_usuarios[id_chat]['contador'] += 1
            print(f"[LOCAL] {nombre_archivo} guardado con éxito.")
            
        except Exception as e:
            print(f"❌ Error Local: {e}")
            return

    try:
        id_canal_limpio = int(str(ID_CANAL).strip())
        bot.send_photo(
            id_canal_limpio, 
            message.photo[-1].file_id, 
            caption=f"📦 {codigo_actual} - Foto {contador_actual}"
        )
    except Exception as e:
        print(f"❌ Error Nube: {e}")

    if id_chat in timers_usuarios:
        timers_usuarios[id_chat].cancel()

    t = Timer(5.0, pedir_cliente, args=[id_chat, codigo_actual])
    timers_usuarios[id_chat] = t
    t.start()

# ==========================================
# LANZAMIENTO
# ==========================================
if __name__ == "__main__":
    print("✅ Bot conectado. Esperando mensajes...")
    bot.infinity_polling()