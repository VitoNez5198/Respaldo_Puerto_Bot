import os
import re
import telebot
import io
import time
import requests
import textwrap
import logging
from datetime import datetime
from threading import Lock, Timer 
from dotenv import load_dotenv
from telebot import apihelper
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from PIL import Image, ImageDraw, ImageFont

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
memoria_contenedores = {} 

# ==========================================
# 📩 FUNCIONES DE APOYO
# ==========================================

def preguntar_fin_fotos(chat_id, codigo):
    """Pregunta al usuario si ya terminó de enviar fotos tras una pausa."""
    if chat_id in estado_usuarios and estado_usuarios[chat_id]['codigo'] == codigo:
        if estado_usuarios[chat_id].get('paso') != 'fotos':
            return
        
        if estado_usuarios[chat_id].get('avisado', False):
            return
            
        estado_usuarios[chat_id]['avisado'] = True
            
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("✅ Sí, ya terminé", callback_data="fin_si"),
            InlineKeyboardButton("📸 No, enviaré más", callback_data="fin_no")
        )
        
        try:
            mensaje_enviado = bot.send_message(
                chat_id, 
                f"⏳ Han pasado unos segundos...\n¿Terminaste de enviar las fotos para el contenedor **{codigo}**?",
                reply_markup=markup,
                parse_mode="Markdown"
            )
            estado_usuarios[chat_id]['id_pregunta'] = mensaje_enviado.message_id
        except Exception as e:
            print(f"❌ Error al enviar pregunta de cierre: {e}")

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

    if estado.get('paso') == 'nave':
        nombre_nave = message.text.strip().upper()
        estado_usuarios[id_chat]['nave'] = nombre_nave
        estado_usuarios[id_chat]['paso'] = 'fotos' 
        
        codigo_actual = estado['codigo']
        memoria_contenedores[codigo_actual] = {
            'cliente': estado['cliente'],
            'nave': nombre_nave
        }
        
        bot.reply_to(message, f"✅ Datos completos.\n\n📸 Ahora sí, **envíame todas las fotos** del contenedor {codigo_actual}.", parse_mode="Markdown")
        return

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
                'nave': datos_previos['nave']
            }
            bot.reply_to(message, f"🔄 Retomando contenedor: {codigo_limpio}\n*(Cliente: {datos_previos['cliente']} | Nave: {datos_previos['nave']})*\n\n📸 Envíame las fotos extra.")
        else:
            estado_usuarios[id_chat] = {
                'codigo': codigo_limpio,
                'contador': 1,
                'avisado': False,
                'paso': 'cliente', 
                'cliente': None,
                'nave': None
            }
            bot.reply_to(message, f"✅ Código validado: {codigo_limpio}\n\n¿A qué cliente pertenece?", reply_markup=generar_menu_clientes())
    else:
        bot.reply_to(message, "❌ Código inválido. Recuerda: 4 letras seguidas de 7 números.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('cliente_'))
def procesar_seleccion_cliente(call):
    id_chat = call.message.chat.id
    cliente_seleccionado = call.data.replace("cliente_", "") 
    if id_chat in estado_usuarios:
        estado_usuarios[id_chat]['cliente'] = cliente_seleccionado
        estado_usuarios[id_chat]['paso'] = 'nave' 
    bot.answer_callback_query(call.id) 
    bot.edit_message_text(
        chat_id=id_chat,
        message_id=call.message.message_id,
        text=f"✅ Cliente seleccionado: **{cliente_seleccionado}**",
        parse_mode="Markdown"
    )
    bot.send_message(id_chat, "🚢 Ahora, por favor escribe el nombre de la nave:")
    
@bot.callback_query_handler(func=lambda call: call.data in ['fin_si', 'fin_no'])
def procesar_fin_fotos(call):
    id_chat = call.message.chat.id
    if id_chat not in estado_usuarios:
        bot.answer_callback_query(call.id)
        return
    if call.data == 'fin_si':
        codigo = estado_usuarios[id_chat]['codigo']
        estado_usuarios[id_chat]['paso'] = 'completado' 
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            chat_id=id_chat,
            message_id=call.message.message_id,
            text=f"✅ **Contenedor {codigo} cerrado exitosamente.**\n\n*(💡 Nota: Si necesitas agregar más fotos más tarde, simplemente vuelve a escribir el código {codigo} y el bot lo retomará de inmediato sin pedirte los datos de nuevo)*",
            parse_mode="Markdown"
        )
    elif call.data == 'fin_no':
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            chat_id=id_chat,
            message_id=call.message.message_id,
            text="📸 Entendido. Sigo a la espera de las demás fotos...",
            parse_mode="Markdown"
        )

@bot.message_handler(content_types=['photo'])
def recibir_fotos(message):
    id_chat = message.chat.id
    if id_chat not in estado_usuarios or estado_usuarios[id_chat].get('paso') != 'fotos':
        bot.reply_to(message, "⚠️ Por favor, completa los datos del contenedor antes de enviar fotos.")
        return
    
    id_pregunta = estado_usuarios[id_chat].get('id_pregunta')
    if id_pregunta:
        try:
            bot.delete_message(id_chat, id_pregunta)
            estado_usuarios[id_chat]['id_pregunta'] = None
        except:
            pass

    with semaforo:
        estado_usuarios[id_chat]['avisado'] = False 
        codigo_actual = estado_usuarios[id_chat]['codigo']
        contador_actual = estado_usuarios[id_chat]['contador']
        cliente_actual = estado_usuarios[id_chat]['cliente']
        nave_actual = estado_usuarios[id_chat]['nave']
        
        try:
            ahora = datetime.now()
            ruta_carpeta_final = os.path.join(RUTA_BASE, ahora.strftime("%Y"), ahora.strftime("%m"), codigo_actual)
            os.makedirs(ruta_carpeta_final, exist_ok=True)
            
            file_info = bot.get_file(message.photo[-1].file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            imagen = Image.open(io.BytesIO(downloaded_file))
            dibujar = ImageDraw.Draw(imagen, "RGBA")
            nave_formateada = textwrap.fill(nave_actual, width=25, break_long_words=True)
            texto_marca = f"Cod. Cont.: {codigo_actual}\nCliente: {cliente_actual}\nNave: {nave_formateada}"
            
            try:
                fuente = ImageFont.truetype("arial.ttf", 38)
            except IOError:
                fuente = ImageFont.load_default()

            pos_x, pos_y = 30, 30
            caja_texto = dibujar.textbbox((pos_x, pos_y), texto_marca, font=fuente)
            margen = 20
            coordenadas_fondo = (caja_texto[0]-margen, caja_texto[1]-margen, caja_texto[2]+margen, caja_texto[3]+margen)
            dibujar.rectangle(coordenadas_fondo, fill=(0, 0, 0, 180)) 
            dibujar.text((pos_x, pos_y), texto_marca, fill=(255, 255, 255, 255), font=fuente)

            timestamp = ahora.strftime("%Y%m%d_%H%M%S")
            nombre_archivo = f"{codigo_actual}_{timestamp}.jpg"
            ruta_archivo = os.path.join(ruta_carpeta_final, nombre_archivo)
            
            imagen.save(ruta_archivo, "JPEG")
            estado_usuarios[id_chat]['contador'] += 1
            print(f"[LOCAL] {nombre_archivo} guardado.")
            
        except Exception as e:
            print(f"❌ Error Local: {e}")
            return

    try:
        id_canal_limpio = int(str(ID_CANAL).strip())
        with open(ruta_archivo, 'rb') as foto_editada:
            bot.send_photo(id_canal_limpio, foto_editada, caption=f"📦 {codigo_actual} - Foto {contador_actual}")
    except Exception as e:
        print(f"❌ Error Nube: {e}")

    if id_chat in timers_usuarios:
        timers_usuarios[id_chat].cancel()

    # --- CAMBIO: 30 segundos de espera antes de preguntar ---
    t = Timer(30.0, preguntar_fin_fotos, args=[id_chat, codigo_actual])
    timers_usuarios[id_chat] = t
    t.start()

# ==========================================
# LANZAMIENTO
# ==========================================
if __name__ == "__main__":
    print("✅ Bot conectado. Esperando mensajes...")
    # timeout: le da 20 seg a las fotos pesadas antes de fallar
    # long_polling_timeout: mantiene la conexión estable
    bot.infinity_polling(timeout=20, long_polling_timeout=10)