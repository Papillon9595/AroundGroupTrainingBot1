import time
import telebot
import os
from telebot import types
from dotenv import load_dotenv

import json

users = {}
users_file = "users.json"

try:
    with open(users_file, "r", encoding="utf-8") as f:
        users = json.load(f)
except FileNotFoundError:
    users = {}

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения")

bot = telebot.TeleBot(TOKEN)

logging.basicConfig(filename='bot_errors.log', level=logging.ERROR)

file_paths = {
    "product": "https://clck.ru/3NB2zY",
    "sales": "https://clck.ru/3NB2wX",
    "sticks": "https://clck.ru/3NB2ur",
    "accessories": "https://clck.ru/3NB3aW",
}

VIDEO_FILE_IDS = {
    "direct": "BAACAgIAAxkBAAIBZ2h457B6jJvSCJY7qYfqOZ_oSQjtAAIJeQACe2XJS73hNlvfZvP4NgQ",
    "reboot": "BAACAgIAAxkBAAICcGh56dNWrQEKhRKT1SWdBNPsqbCSAAIpdAACw5XRSzq54nCgfjqQNgQ",
    "intro": "BAACAgIAAxkBAAICqWh58qS32y4lcAABwTpXlzsrGMIELwACLXMAAntl0UsQKxQvBG_fLDYE",
    "replacement": "CgACAgIAAxkBAAICzGh5-xBcF1InTNdiFGGthnxeLnQWAAL_cwACe2XRS2BVCLRNVS-fNgQ",
    "return": "CgACAgIAAxkBAAICzmh5-3hrMswogfi0ZT0d7nqH9liWAAIKdAACe2XRS-e0JbA3KIndNgQ",
    "unregisteredconsumer": "CgACAgIAAxkBAAIC0Gh5-7vPyvivL9O2qAyyEum-UWn5AAIPdAACe2XRS1AKLBQAAYZLOzYE",
}

texts = {
    "ru": {
        "welcome": "Здравствуйте, я Бот компании Ploom - Ваш помощник по обучению. Как я могу к вам обращаться?",
        "name_reply": "Приятно познакомиться, {name}!\nВыберите раздел:",
        "materials": "Материалы",
        "videoguides": "Видеоуроки",
        "contact": "Контакты",
        "search": "Поиск",
        "choose_file": "Выберите нужный файл:",
        "back": "Назад",
        "contact_text": "Вы можете связаться с нами по следующим контактам:",
        "file_titles": {
            "direct": "Видео-инструкция Ploom Direct",
            "reboot": "Перезагрузка PloomXAdvanced",
            "replacement": "Замена в Phouse-IMS",
            "return": "Возврат в Phouse-IMS",
            "unregisteredconsumer": "Клиент без регистрации в Phouse-IMS",
            "product": "Информация о продукте",
            "sales": "Скрипты продаж",
            "sticks": "Стики Sobranie",
            "accessories": "Аксессуары"
        },
        "video_choice": "Выберите видеоурок:"
    },
    "az": {
        "welcome": "Salam, mən Ploom şirkətinin Botuyam və Sizə təlimdə köməklik göstərəcəyəm. Sizə necə müraciət edə bilərəm?",
        "name_reply": "Tanış olduğumuza şadam, {name}!\nZəhmət olmasa bölmə seçin:",
        "materials": "Materiallar",
        "videoguides": "Video dərslər",
        "contact": "Əlaqə",
        "search": "Axtarış",
        "choose_file": "Zəhmət olmasa faylı seçin:",
        "back": "Geri",
        "contact_text": "Aşağıdakı şəxslərlə əlaqə saxlaya bilərsiniz:",
        "file_titles": {
            "direct": "Ploom Direct üzrə Video təlimat",
            "reboot": "PloomXAdvanced Sıfırlanması",
            "replacement": "Dəyisdirilmə Phouse-IMS",
            "return": "Qaytarılma Phouse-IMS",
            "unregisteredconsumer": "Qeydiyyatsız müştəri Phouse-IMS",
            "product": "Məhsul haqqında məlumat",
            "sales": "Satış skriptləri",
            "sticks": "Sobranie Stikləri",
            "accessories": "Aksessuarlar"
        },
        "video_choice": "Video dərs seçin:"
    },
    "en": {
        "welcome": "Hello, I am the Ploom company Bot, and I will help You with your training. How can I address You?",
        "name_reply": "Nice to meet you, {name}!\nPlease choose a section:",
        "materials": "Materials",
        "videoguides": "Video Lessons",
        "contact": "Contact",
        "search": "Search",
        "choose_file": "Please choose a file:",
        "back": "Back",
        "contact_text": "You can contact us via:",
        "file_titles": {
            "direct": "Video Instructions of Ploom Direct",
            "reboot": "How to reboot PloomXAdvanced",
            "replacement": "Replacement Phouse-IMS",
            "return": "Return&Refund Phouse-IMS",
            "unregisteredconsumer": "Unregistered consumer Phouse-IMS",
            "product": "Product Info",
            "sales": "Sales Scripts",
            "sticks": "Sobranie Sticks",
            "accessories": "Accessories"
        },
        "video_choice": "Choose a video lesson:"
    }
}

user_data = {}

search_keywords = {
    "direct": ["direct", "ploom direct", "видео инструкция", "инструкция", "video instruction"],
    "reboot": ["reboot", "reset", "перезагрузка", "сброс", "restart"],
    "replacement": ["replacement", "замена", "phouse-ims", "замена phouse-ims"],
    "return": ["return", "refund", "возврат", "phouse-ims"],
    "unregisteredconsumer": ["unregistered", "consumer", "клиент", "без регистрации", "phouse-ims"],
    "product": ["product", "продукт", "информация", "info", "продукт информация"],
    "sales": ["sales", "продажи", "скрипты", "scripts"],
    "sticks": ["sticks", "stiks", "sobranie", "стики"],
    "accessories": ["accessories", "аксессуары"],
}

@bot.message_handler(commands=['stats'])
def send_stats(message):
    count = len(users)
    bot.send_message(message.chat.id, f"Всего пользователей: {count}")
    
@bot.message_handler(commands=['menu'])
def show_menu(message):
    user_id = message.from_user.id
    if user_id in user_data:
        lang = user_data[user_id].get("lang", "ru")
        name = user_data[user_id].get("name", "User")
        send_main_menu(user_id, lang, name)
    else:
        bot.send_message(message.chat.id, "Пожалуйста, введите /start для начала.")
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    if str(user_id) not in users:
        users[str(user_id)] = ""  # Имя пока пустое, запишем позже
        with open(users_file, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
    lang_markup = types.InlineKeyboardMarkup(row_width=3)
    lang_markup.add(
        types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
        types.InlineKeyboardButton("🇦🇿 Azərbaycan", callback_data="lang_az"),
        types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    )
    intro_video_id = VIDEO_FILE_IDS.get("intro")
    if intro_video_id:
        try:
            bot.send_video(message.chat.id, intro_video_id)
        except Exception as e:
            logging.error(f"Не удалось отправить видео приветствия: {e}")

    sent = bot.send_message(message.chat.id, "Выберите язык / Select language / Dil seçin:", reply_markup=lang_markup)
    user_data[message.from_user.id] = {"lang_msg": sent.message_id, "state": "awaiting_language"}

@bot.message_handler(commands=['count'])
def count_users(message):
    bot.send_message(message.chat.id, f"Всего пользователей: {len(users)}")

@bot.message_handler(func=lambda message: message.chat.type in ["group", "supergroup"])
def handle_group_messages(message):
    text_lower = message.text.lower() if message.text else ""
    if "поиск" in text_lower:
        bot.reply_to(message, "Чтобы начать обучение, нажми /start или /menu.")
    elif f"@{bot.get_me().username}" in text_lower:
        bot.reply_to(message, "Привет! Я бот для обучения. Напиши /start в личку, чтобы начать.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def ask_name(call):
    user_id = call.from_user.id
    lang = call.data.split("_")[1]
    user_data[user_id] = {"lang": lang, "state": "awaiting_name"}
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass
    sent = bot.send_message(call.message.chat.id, texts[lang]["welcome"])
    user_data[user_id]["name_msg"] = sent.message_id
    try:
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"Ошибка при answer_callback_query: {e}")
@bot.message_handler(func=lambda message: message.from_user.id in user_data and user_data[message.from_user.id].get("state") == "awaiting_name")
def get_name(message):
    user_id = message.from_user.id
    name = message.text.strip()
    user_data[user_id]["name"] = name
    users[str(user_id)] = name
    with open(users_file, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

    lang = user_data[user_id]["lang"]

    logging.info(f"User {user_id} named '{name}' started using the bot.")

    try:
        bot.delete_message(message.chat.id, user_data[user_id].get("name_msg", 0))
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass

    user_data[user_id]["state"] = "main"
    send_main_menu(user_id, lang, name)

def send_main_menu(user_id, lang, name):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(texts[lang]["materials"], callback_data="materials"),
        types.InlineKeyboardButton(texts[lang]["videoguides"], callback_data="videoguides"),
        types.InlineKeyboardButton(texts[lang]["contact"], callback_data="contact"),
        types.InlineKeyboardButton(texts[lang]["search"], callback_data="search")
    )
    bot.send_message(user_id, texts[lang]["name_reply"].format(name=name), reply_markup=markup)
    user_data[user_id]["state"] = "main"

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    if user_id not in user_data:
        bot.send_message(call.message.chat.id, "Пожалуйста, используйте /start чтобы начать.")
        bot.answer_callback_query(call.id)
        return

    lang = user_data[user_id].get("lang", "ru")
    name = user_data[user_id].get("name", "User")
    state = user_data[user_id].get("state", "main")

    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass

    if call.data == "materials":
        markup = types.InlineKeyboardMarkup(row_width=1)
        for key, title in texts[lang]["file_titles"].items():
            if key not in VIDEO_FILE_IDS:  # Это файлы, которые не видео
                markup.add(types.InlineKeyboardButton(title, callback_data=f"file_{key}"))
        markup.add(types.InlineKeyboardButton(texts[lang]["back"], callback_data="main_menu"))
        bot.send_message(call.message.chat.id, texts[lang]["choose_file"], reply_markup=markup)
        user_data[user_id]["state"] = "materials"

    elif call.data == "videoguides":
        markup = types.InlineKeyboardMarkup()
        for key in ["direct", "reboot", "replacement", "return", "unregisteredconsumer"]:
            title = texts[lang]["file_titles"].get(key, key)
            markup.add(types.InlineKeyboardButton(title, callback_data=f"file_{key}"))
        markup.add(types.InlineKeyboardButton(texts[lang]["back"], callback_data="main_menu"))
        bot.send_message(call.message.chat.id, texts[lang]["video_choice"], reply_markup=markup)
        user_data[user_id]["state"] = "videoguides"

    elif call.data.startswith("file_"):
        file_key = call.data[5:]
        back_to = "materials" if file_key in file_paths else "videoguides"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(texts[lang]["back"], callback_data=back_to))

        file_id = VIDEO_FILE_IDS.get(file_key)
        if file_id:
            bot.send_video(call.message.chat.id, file_id, caption=texts[lang]["file_titles"].get(file_key, file_key), reply_markup=markup)
        else:
            path = file_paths.get(file_key)
            if path and path.startswith("http"):
                bot.send_message(call.message.chat.id, f"{texts[lang]['file_titles'].get(file_key, file_key)}:\n{path}", reply_markup=markup)
            else:
                bot.send_message(call.message.chat.id, "Файл не найден.", reply_markup=markup)

    elif call.data == "contact":
        markup = types.InlineKeyboardMarkup()
        if lang == "ru":
            markup.add(types.InlineKeyboardButton("Мехти (техподдержка)", url="https://t.me/mexti_s"))
            markup.add(types.InlineKeyboardButton("Хайям Махмудов (тренер)", url="https://t.me/mxm086"))
        elif lang == "az":
            markup.add(types.InlineKeyboardButton("Mehdi Suleymanov (texniki dəstək)", url="https://t.me/mexti_s"))
            markup.add(types.InlineKeyboardButton("Xəyyam Mahmudov (təlimçi)", url="https://t.me/mxm086"))
        elif lang == "en":
            markup.add(types.InlineKeyboardButton("Mehti (tech Support)", url="https://t.me/mexti_s"))
            markup.add(types.InlineKeyboardButton("Khayyam Mahmudov (trainer)", url="https://t.me/mxm086"))
        markup.add(types.InlineKeyboardButton(texts[lang]["back"], callback_data="main_menu"))
        bot.send_message(call.message.chat.id, texts[lang]["contact_text"], reply_markup=markup)
        user_data[user_id]["state"] = "contact"

    elif call.data == "search":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, texts[lang]["search"] + ": Введите ключевое слово для поиска.")
        user_data[user_id]["state"] = "search"

    elif call.data == "main_menu":
        send_main_menu(user_id, lang, name)

    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda message: message.from_user.id in user_data and user_data[message.from_user.id].get("state") == "search")
def handle_search(message):
    user_id = message.from_user.id
    lang = user_data[user_id].get("lang", "ru")
    query = message.text.lower()

    results = []

    for key, keywords in search_keywords.items():
        if any(word in query for word in keywords):
            title = texts[lang]["file_titles"].get(key, key)
            results.append((key, title))

    if results:
        markup = types.InlineKeyboardMarkup()
        for key, title in results:
            markup.add(types.InlineKeyboardButton(title, callback_data=f"file_{key}"))
        markup.add(types.InlineKeyboardButton(texts[lang]["back"], callback_data="main_menu"))
        bot.send_message(message.chat.id, f"Результаты поиска по запросу: «{message.text}»", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, f"По запросу «{message.text}» ничего не найдено. Попробуйте другое ключевое слово.")

    user_data[user_id]["state"] = "search"

@bot.message_handler(content_types=['new_chat_members'])
def greet_new_member(message):
    for new_member in message.new_chat_members:
        welcome_text = (
            f"👋 Привет, {new_member.first_name}!\n"
            "Добро пожаловать в наш обучающий чат от Ploom 💼\n\n"
            "📌 Чтобы начать обучение, отправьте команду /обучение"
        )
        bot.send_message(message.chat.id, welcome_text)

        try:
            bot.send_message(new_member.id, "👋 Приветствуем в обучающем проекте Ploom!\nЧтобы начать, напишите /start.")
        except Exception:
            bot.send_message(message.chat.id, f"👋 {new_member.first_name}, добро пожаловать! Напиши мне в личку, чтобы получить материалы.")

@bot.message_handler(commands=['обучение'])
def admin_only_command(message):
    try:
        chat_member = bot.get_chat_member(message.chat.id, message.from_user.id)
        if chat_member.status not in ['administrator', 'creator']:
            bot.reply_to(message, "⛔ Эта команда доступна только администраторам.")
            return
        # Логика рассылки/отправки материалов
        bot.reply_to(message, "📚 Отправляю обучающие материалы...")
    except Exception as e:
        bot.reply_to(message, "⚠️ Произошла ошибка при проверке прав.")
        logging.error(f"Ошибка в команде /обучение: {e}")

@bot.message_handler(content_types=['video', 'animation', 'document'])
def handle_media_messages(message):
    if message.video:
        file_id = message.video.file_id
        bot.send_message(message.chat.id, f"📹 Это video\n`{file_id}`", parse_mode='Markdown')
    elif message.animation:
        file_id = message.animation.file_id
        bot.send_message(message.chat.id, f"🌀 Это animation (GIF)\n`{file_id}`", parse_mode='Markdown')
    elif message.document:
        file = message.document
        if file.mime_type == "video/mp4":
            bot.send_message(message.chat.id, f"📁 Это .mp4 отправлено как документ\n`{file.file_id}`", parse_mode='Markdown')
        else:
            bot.send_message(message.chat.id, f"📁 Документ: {file.file_name} (тип: {file.mime_type})")
    else:
        bot.send_message(message.chat.id, "❗ Пришли видео, GIF или mp4-документ.")

if __name__ == "__main__":
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            logging.error(f"Ошибка подключения к Telegram: {e}")
            time.sleep(10)





