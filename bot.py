import os
import logging
import sqlite3
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен бота (будет установлен в переменных окружения)
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

# База данных
def init_db():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS witness_state
                 (chat_id INTEGER PRIMARY KEY, title TEXT, members TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS active_cycles
                 (chat_id INTEGER, user_id INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_profiles
                 (user_id INTEGER, username TEXT, first_name TEXT)''')
    conn.commit()
    conn.close()

# ===== КОНЦЕПЦИЯ 1: ЦИКЛ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ =====
def cycle_start(update: Update, context: CallbackContext):
    """Активирует цикл на пользователя"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        user_name = target_user.first_name
    else:
        target_user = user
        user_name = user.first_name

    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    # Сохраняем текущий профиль
    c.execute("INSERT OR REPLACE INTO user_profiles VALUES (?, ?, ?)",
              (target_user.id, target_user.username, target_user.first_name))
    
    # Активируем цикл
    c.execute("INSERT OR IGNORE INTO active_cycles VALUES (?, ?)", 
              (chat_id, target_user.id))
    
    conn.commit()
    conn.close()
    
    update.message.reply_text(
        f"🌀 Цикл активирован на пользователя {user_name}!\n"
        f"Любые изменения профиля будут 'откатываться' в памяти бота."
    )

def cycle_info(update: Update, context: CallbackContext):
    """Показывает оригинальное состояние пользователя"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    c.execute("SELECT username, first_name FROM user_profiles WHERE user_id = ?", (user.id,))
    result = c.fetchone()
    
    if result:
        original_username, original_name = result
        current_username = f"@{user.username}" if user.username else "не установлен"
        current_name = user.first_name
        
        message = (
            f"📊 Информация о цикле для {user.first_name}:\n"
            f"Исходное имя: {original_name}\n"
            f"Текущее имя: {current_name}\n"
            f"Исходный username: {original_username}\n"
            f"Текущий username: {current_username}\n"
            f"\nЦикл активен! Все изменения отслеживаются."
        )
    else:
        message = "Цикл не активирован на вас. Используйте /cycle_start"
    
    conn.close()
    update.message.reply_text(message)

# ===== КОНЦЕПЦИЯ 2: РЕЖИМ ПАРАДОКСОВ =====
def paradox_start(update: Update, context: CallbackContext):
    """Активирует режим парадоксов"""
    update.message.reply_text(
        "🔄 Режим ПАРАДОКСОВ активирован!\n"
        "Теперь я буду отслеживать обещания и условия в ваших сообщениях.\n"
        "Попробуйте написать: 'Если я отправлю это сообщение, то...'"
    )

def track_promises(update: Update, context: CallbackContext):
    """Отслеживает обещания и условия в сообщениях"""
    text = update.message.text.lower()
    
    responses = {
        'если': "🌀 Обнаружено условие 'если... то...'. Цикл предупреждает: последствие будет сброшено!",
        'обещаю': "🌀 Обещание зафиксировано! Нарушение приведет к парадоксу!",
        'клянусь': "🌀 Клятва принята! Цикл следит за исполнением...",
        'никогда': "🌀 'Никогда' - опасное слово! Цикл может проверить это утверждение!",
        'всегда': "🌀 'Всегда' создает временную петлю! Будьте осторожны!"
    }
    
    for trigger, response in responses.items():
        if trigger in text:
            update.message.reply_text(response)
            break

# ===== КОНЦЕПЦИЯ 3: РЕЖИМ СВИДЕТЕЛЯ =====
def witness_start(update: Update, context: CallbackContext):
    """Фиксирует текущее состояние чата"""
    chat = update.effective_chat
    chat_id = chat.id
    
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    # Сохраняем название чата и список участников (в реальности нужно API для получения списка)
    c.execute("INSERT OR REPLACE INTO witness_state VALUES (?, ?, ?)",
              (chat_id, chat.title, "Список участников зафиксирован"))
    
    conn.commit()
    conn.close()
    
    update.message.reply_text(
        f"📸 Свидетель активирован!\n"
        f"Состояние чата '{chat.title}' зафиксировано как исходное.\n"
        f"Любые изменения будут отслеживаться."
    )

def witness_status(update: Update, context: CallbackContext):
    """Показывает зафиксированное состояние"""
    chat_id = update.effective_chat.id
    
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    c.execute("SELECT title, members FROM witness_state WHERE chat_id = ?", (chat_id,))
    result = c.fetchone()
    
    if result:
        original_title, members = result
        current_title = update.effective_chat.title
        
        message = (
            f"📊 Свидетель сообщает:\n"
            f"Исходное название: {original_title}\n"
            f"Текущее название: {current_title}\n"
            f"Статус: {'ИЗМЕНЕНО! 🔄' if original_title != current_title else 'СОХРАНЕНО ✅'}\n"
            f"{members}"
        )
    else:
        message = "Режим свидетеля не активирован. Используйте /witness_start"
    
    conn.close()
    update.message.reply_text(message)

# ===== ОСНОВНЫЕ КОМАНДЫ =====
def start(update: Update, context: CallbackContext):
    """Приветственное сообщение"""
    help_text = """
🌀 *БОТ ЦИКЛ* активирован! 🌀

*Доступные команды:*

*🔄 ЦИКЛ (Концепция 1)*
/cycle_start - Активировать цикл на пользователя (ответьте на сообщение)
/cycle_info - Показать ваше "исходное состояние"

*🎭 ПАРАДОКС (Концепция 2)*
/paradox_start - Активировать режим парадоксов
(Просто пишите сообщения с словами: 'если', 'обещаю', 'клянусь')

*📸 СВИДЕТЕЛЬ (Концепция 3)*
/witness_start - Зафиксировать состояние чата
/witness_status - Показать изменения

*Пример использования:*
1. Ответьте на чье-то сообщение /cycle_start
2. Напишите "Я обещаю больше не спамить"
3. Используйте /witness_start чтобы зафиксировать чат
4. Наслаждайтесь реакцией бота! 😄

_Бот создан по мотивам способности из фэнтези книги_
    """
    update.message.reply_text(help_text, parse_mode='Markdown')

def error_handler(update: Update, context: CallbackContext):
    """Обработчик ошибок"""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def main():
    """Основная функция"""
    init_db()
    
    updater = Updater(TOKEN)
    dp = updater.dispatcher
    
    # Команды
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("cycle_start", cycle_start))
    dp.add_handler(CommandHandler("cycle_info", cycle_info))
    dp.add_handler(CommandHandler("paradox_start", paradox_start))
    dp.add_handler(CommandHandler("witness_start", witness_start))
    dp.add_handler(CommandHandler("witness_status", witness_status))
    
    # Обработчики сообщений
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, track_promises))
    
    # Обработчик ошибок
    dp.add_error_handler(error_handler)
    
    # Запуск бота
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
