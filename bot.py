import json
import os
from uuid import uuid4
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler
)

# --- Configuración ---
# Usar variables de entorno para mayor seguridad
BOT_TOKEN = os.getenv("BOT_TOKEN", "8002658257:AAHxJYxhdrxi2FF9hqgc9AfRRhbdhgBTy3k")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7312942188"))
PORT = os.getenv("PORT", "8000")

# Fichero de cola - usar /tmp en Render para persistencia temporal
COLA_PATH = "/tmp/cola.json"

# Estados de conversación para solicitar canción
ESPERANDO_CANCION = range(1)

# --- Funciones de Utilidad ---

def cargar_cola():
    """Carga la cola de canciones desde el fichero JSON."""
    if not os.path.exists(COLA_PATH):
        return []
    try:
        with open(COLA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def guardar_cola(cola):
    """Guarda la cola de canciones en el fichero JSON."""
    try:
        # Crear directorio si no existe
        os.makedirs(os.path.dirname(COLA_PATH), exist_ok=True)
        with open(COLA_PATH, "w", encoding="utf-8") as f:
            json.dump(cola, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error al guardar cola: {e}")

def formatear_peticion(peticion):
    """Formatea una única petición para mostrarla en la cola."""
    return f"🎶 *{peticion['cancion']}*\n👤 {peticion['usuario']}"

def teclado_principal():
    """Crea y devuelve el teclado con los botones principales."""
    botones = [
        ["🥡 Pedir canción"],
        ["🎤 Cómo pedir", "ℹ️ Información"]
    ]
    return ReplyKeyboardMarkup(botones, resize_keyboard=True)

def teclado_admin():
    """Crea y devuelve el teclado con botones adicionales para admin."""
    botones = [
        ["🥡 Pedir canción"],
        ["📋 Ver Cola", "🔧 Admin Panel"],
        ["🎤 Cómo pedir", "ℹ️ Información"]
    ]
    return ReplyKeyboardMarkup(botones, resize_keyboard=True)

# --- Funciones de Administrador ---

def es_admin(user_id):
    """Verifica si el usuario es administrador."""
    return user_id == ADMIN_ID

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el panel de administración."""
    if not es_admin(update.effective_user.id):
        await update.message.reply_text("❌ No tienes permisos de administrador.")
        return
    
    cola = cargar_cola()
    total_peticiones = len(cola)
    
    botones_admin = [
        ["🗑️ Limpiar Cola", "📊 Estadísticas"],
        ["📋 Ver Cola Completa", "🔄 Reiniciar Bot"],
        ["🚫 Eliminar Última", "🔙 Menú Principal"]
    ]
    
    mensaje = (
        f"🔧 *Panel de Administración*\n\n"
        f"📊 Peticiones en cola: {total_peticiones}\n"
        f"👤 Admin: {update.effective_user.first_name}\n\n"
        f"Selecciona una opción:"
    )
    
    teclado_admin_panel = ReplyKeyboardMarkup(botones_admin, resize_keyboard=True)
    await update.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=teclado_admin_panel)

async def limpiar_cola(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Limpia completamente la cola de peticiones."""
    if not es_admin(update.effective_user.id):
        await update.message.reply_text("❌ No tienes permisos de administrador.")
        return
    
    cola = cargar_cola()
    total_eliminadas = len(cola)
    
    # Limpiar la cola
    guardar_cola([])
    
    mensaje = f"🗑️ ✅ Cola limpiada exitosamente.\n📊 Se eliminaron {total_eliminadas} peticiones."
    await update.message.reply_text(mensaje, reply_markup=teclado_admin())

async def eliminar_ultima(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Elimina la última petición de la cola."""
    if not es_admin(update.effective_user.id):
        await update.message.reply_text("❌ No tienes permisos de administrador.")
        return
    
    cola = cargar_cola()
    
    if not cola:
        await update.message.reply_text("📭 La cola ya está vacía.", reply_markup=teclado_admin())
        return
    
    ultima_peticion = cola.pop()
    guardar_cola(cola)
    
    mensaje = (
        f"🚫 ✅ Última petición eliminada:\n\n"
        f"🎶 *{ultima_peticion['cancion']}*\n"
        f"👤 {ultima_peticion['usuario']}\n"
        f"💬 {ultima_peticion['grupo']}"
    )
    
    await update.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=teclado_admin())

async def estadisticas_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra estadísticas detalladas de la cola."""
    if not es_admin(update.effective_user.id):
        await update.message.reply_text("❌ No tienes permisos de administrador.")
        return
    
    cola = cargar_cola()
    
    if not cola:
        await update.message.reply_text("📊 No hay estadísticas disponibles. La cola está vacía.", reply_markup=teclado_admin())
        return
    
    # Contar peticiones por usuario
    usuarios = {}
    grupos = {}
    
    for peticion in cola:
        usuario = peticion['usuario']
        grupo = peticion['grupo']
        
        usuarios[usuario] = usuarios.get(usuario, 0) + 1
        grupos[grupo] = grupos.get(grupo, 0) + 1
    
    # Top 5 usuarios más activos
    top_usuarios = sorted(usuarios.items(), key=lambda x: x[1], reverse=True)[:5]
    top_grupos = sorted(grupos.items(), key=lambda x: x[1], reverse=True)[:3]
    
    mensaje = f"📊 *Estadísticas de la Cola*\n\n"
    mensaje += f"📈 Total de peticiones: {len(cola)}\n"
    mensaje += f"👥 Usuarios únicos: {len(usuarios)}\n"
    mensaje += f"💬 Grupos activos: {len(grupos)}\n\n"
    
    mensaje += "🏆 *Top Usuarios:*\n"
    for i, (usuario, cantidad) in enumerate(top_usuarios, 1):
        mensaje += f"{i}. {usuario}: {cantidad} peticiones\n"
    
    mensaje += "\n💬 *Grupos más activos:*\n"
    for i, (grupo, cantidad) in enumerate(top_grupos, 1):
        grupo_corto = grupo[:30] + "..." if len(grupo) > 30 else grupo
        mensaje += f"{i}. {grupo_corto}: {cantidad} peticiones\n"
    
    await update.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=teclado_admin())

async def ver_cola_completa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra toda la cola sin límite (solo para admin)."""
    if not es_admin(update.effective_user.id):
        await update.message.reply_text("❌ No tienes permisos de administrador.")
        return
    
    cola = cargar_cola()
    if not cola:
        await update.message.reply_text("📭 La cola de peticiones está vacía.", reply_markup=teclado_admin())
        return
    
    # Dividir en mensajes si es muy larga
    peticiones_por_mensaje = 8
    total_mensajes = (len(cola) + peticiones_por_mensaje - 1) // peticiones_por_mensaje
    
    for i in range(0, len(cola), peticiones_por_mensaje):
        grupo_peticiones = cola[i:i + peticiones_por_mensaje]
        numero_mensaje = (i // peticiones_por_mensaje) + 1
        
        lista_texto = []
        for j, peticion in enumerate(grupo_peticiones, i + 1):
            texto_peticion = (
                f"{j}. 🎶 *{peticion['cancion']}*\n"
                f"   👤 {peticion['usuario']} (@{peticion['username']})\n"
                f"   💬 {peticion['grupo'][:25]}{'...' if len(peticion['grupo']) > 25 else ''}"
            )
            lista_texto.append(texto_peticion)
        
        mensaje = f"📋 *Cola Completa ({numero_mensaje}/{total_mensajes})*\n\n" + "\n\n".join(lista_texto)
        
        if numero_mensaje == total_mensajes:
            await update.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=teclado_admin())
        else:
            await update.message.reply_text(mensaje, parse_mode="Markdown")

# --- Comandos y Botones ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /start y muestra el menú principal."""
    user_id = update.effective_user.id
    
    if es_admin(user_id):
        bienvenida = (
            "¡Hola Admin! 👑\n\n"
            "Bienvenido al Bot de Peticiones Musicales 🎶\n\n"
            "Como administrador, tienes acceso a funciones especiales:\n"
            "• 📋 Ver Cola - Ver todas las peticiones\n"
            "• 🔧 Admin Panel - Panel de administración completo\n"
            "• Usa /admin para acceso rápido al panel\n\n"
            "¡Usa los botones para navegar!"
        )
        await update.message.reply_text(bienvenida, reply_markup=teclado_admin())
    else:
        bienvenida = (
            "¡Hola! 👋\n\n"
            "Bienvenido al Bot de Peticiones Musicales 🎶\n\n"
            "Aquí puedes pedir canciones fácilmente. Tu petición será enviada directamente al administrador.\n\n"
            "🔒 Las peticiones son privadas - solo el admin las puede ver.\n\n"
            "¡Usa los botones para navegar!"
        )
        await update.message.reply_text(bienvenida, reply_markup=teclado_principal())

async def ver_cola(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra las últimas 10 canciones en la cola (SOLO ADMIN)."""
    if not es_admin(update.effective_user.id):
        await update.message.reply_text(
            "🔒 Esta función es solo para administradores.\n"
            "Tu petición será vista por el admin cuando la envíes.",
            reply_markup=teclado_principal()
        )
        return
    
    cola = cargar_cola()
    if not cola:
        await update.message.reply_text("📭 La cola de peticiones está vacía.", reply_markup=teclado_admin())
    else:
        # Mostramos solo las últimas 10 para no saturar el chat
        ultimas_peticiones = cola[-10:]
        lista_texto = [f"{i+1}. {formatear_peticion(p)}" for i, p in enumerate(ultimas_peticiones)]
        mensaje = "📋 *Últimas canciones solicitadas:*\n\n" + "\n\n".join(lista_texto)
        await update.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=teclado_admin())

async def como_pedir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra instrucciones sobre cómo pedir una canción."""
    user_id = update.effective_user.id
    teclado = teclado_admin() if es_admin(user_id) else teclado_principal()
    
    mensaje = (
        "🎤 *¿Cómo pedir una canción?*\n\n"
        "1. Pulsa el botón '🥡 Pedir canción'.\n"
        "2. Escribe el nombre de la canción y el artista (si lo sabes).\n"
        "3. ¡Envíalo y listo! Tu petición llegará directamente al admin.\n\n"
        "🔒 *Privacidad:* Solo el administrador puede ver las peticiones."
    )
    await update.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=teclado)

async def informacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra información sobre el bot."""
    user_id = update.effective_user.id
    teclado = teclado_admin() if es_admin(user_id) else teclado_principal()
    
    mensaje = (
        "ℹ️ *Información del Bot*\n\n"
        "Este bot fue creado para gestionar peticiones musicales de forma privada.\n\n"
        "🔒 *Privacidad:* Solo el administrador puede ver las peticiones de todos los usuarios.\n"
        "📝 *Función:* Envía tu petición directamente al admin de forma organizada."
    )
    await update.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=teclado)

# --- Proceso de Solicitud de Canción (Conversación) ---

async def iniciar_solicitud(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia la conversación para solicitar una canción."""
    await update.message.reply_text("🎵 Escribe el nombre de la canción que deseas solicitar:", reply_markup=ReplyKeyboardRemove())
    return ESPERANDO_CANCION

async def recibir_cancion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe el nombre de la canción, la guarda y notifica al admin."""
    cancion = update.message.text
    user = update.effective_user
    chat = update.effective_chat
    user_id = update.effective_user.id

    peticion = {
        "id": str(uuid4()),
        "usuario": user.first_name,
        "username": user.username or "anonimo",
        "cancion": cancion,
        "grupo": chat.title or "Chat Privado"
    }

    cola = cargar_cola()
    cola.append(peticion)
    guardar_cola(cola)

    # Determinar teclado según tipo de usuario
    teclado = teclado_admin() if es_admin(user_id) else teclado_principal()
    
    await update.message.reply_text(
        f"✅ ¡Tu solicitud para *{cancion}* ha sido enviada al administrador!\n\n"
        f"🔒 Tu petición es privada y solo el admin la puede ver.",
        parse_mode="Markdown", 
        reply_markup=teclado
    )

    # Notificar al admin
    try:
        mensaje_admin = (
            f"📥 Nueva solicitud de canción\n"
            f"👤 *Usuario:* {user.first_name} (@{user.username or 'anonimo'})\n"
            f"🎶 *Canción:* {cancion}\n"
            f"💬 *Chat:* {chat.title or 'Privado'}"
        )
        await context.bot.send_message(chat_id=ADMIN_ID, text=mensaje_admin, parse_mode="Markdown")
    except Exception as e:
        print(f"Error al notificar al admin: {e}")

    return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela la operación actual (solicitud de canción)."""
    user_id = update.effective_user.id
    teclado = teclado_admin() if es_admin(user_id) else teclado_principal()
    await update.message.reply_text("❌ Solicitud cancelada.", reply_markup=teclado)
    return ConversationHandler.END

# --- Lanzador del Bot ---

def main():
    """Construye y lanza el bot."""
    print(f"🚀 Iniciando bot en puerto {PORT}")
    print(f"🔑 Token configurado: {'✅' if BOT_TOKEN else '❌'}")
    print(f"👤 Admin ID: {ADMIN_ID}")
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Conversación para solicitar canciones
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^🥡 Pedir canción$'), iniciar_solicitud)],
        states={
            ESPERANDO_CANCION: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_cancion)]
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

    # Agregar handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.Regex('^📋 Ver Cola$'), ver_cola))
    app.add_handler(MessageHandler(filters.Regex('^🔧 Admin Panel$'), admin_panel))
    app.add_handler(MessageHandler(filters.Regex('^🎤 Cómo pedir$'), como_pedir))
    app.add_handler(MessageHandler(filters.Regex('^ℹ️ Información$'), informacion))
    
    # Handlers de administrador
    app.add_handler(MessageHandler(filters.Regex('^🗑️ Limpiar Cola$'), limpiar_cola))
    app.add_handler(MessageHandler(filters.Regex('^📊 Estadísticas$'), estadisticas_admin))
    app.add_handler(MessageHandler(filters.Regex('^📋 Ver Cola Completa$'), ver_cola_completa))
    app.add_handler(MessageHandler(filters.Regex('^🚫 Eliminar Última$'), eliminar_ultima))
    app.add_handler(MessageHandler(filters.Regex('^🔙 Menú Principal$'), start))

    print("🤖 El bot se ha iniciado y está listo.")
    
    # Verificar si estamos en Render (tiene variables de entorno específicas)
    if os.getenv("RENDER"):
        # Usar webhooks en Render
        print("🌐 Usando webhooks para Render...")
        webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/{BOT_TOKEN}"
        app.run_webhook(
            listen="0.0.0.0",
            port=int(PORT),
            url_path=BOT_TOKEN,
            webhook_url=webhook_url
        )
    else:
        # Usar polling en desarrollo local
        print("🔄 Usando polling para desarrollo local...")
        app.run_polling()

if __name__ == "__main__":
    main()