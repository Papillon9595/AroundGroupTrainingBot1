# -*- coding: utf-8 -*-
import os
import time
import json
import logging
from functools import wraps

import telebot
from telebot import types
from telebot.types import CallbackQuery as TGCallbackQuery
from telebot.apihelper import ApiTelegramException
from dotenv import load_dotenv

logging.basicConfig(filename='bot_errors.log', level=logging.ERROR)

users: dict = {}
users_file = "users.json"

try:
    with open(users_file, "r", encoding="utf-8") as f:
        users = json.load(f)
        # Миграция старого формата: "12345": "Имя" -> "12345": {"name": "Имя", "verified": False}
        changed = False
        for k, v in list(users.items()):
            if isinstance(v, str):
                users[k] = {"name": v, "verified": False}
                changed = True
            elif isinstance(v, dict):
                if "name" not in v:
                    users[k]["name"] = ""
                    changed = True
                if "verified" not in v:
                    users[k]["verified"] = False
                    changed = True
        if changed:
            with open(users_file, "w", encoding="utf-8") as wf:
                json.dump(users, wf, ensure_ascii=False, indent=2)
except FileNotFoundError:
    users = {}

def save_users():
    with open(users_file, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def ensure_user_record(user_id: int):
    uid = str(user_id)
    if uid not in users:
        users[uid] = {"name": "", "verified": False}
        save_users()

load_dotenv(override=True)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения")

def _parse_int_set(env_name: str):
    raw = os.getenv(env_name, "").strip()
    if not raw:
        return set()
    return set(int(x) for x in raw.replace(" ", "").split(",") if x)

CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))           
CHANNEL_INVITE_LINK = os.getenv("CHANNEL_INVITE_LINK", "")
ADMIN_IDS = _parse_int_set("ADMIN_IDS")                  
REQUIRE_CODE = os.getenv("REQUIRE_CODE", "0") == "1"     
ACCESS_CODE = os.getenv("ACCESS_CODE", "").strip()       
ALLOW_GROUPS = os.getenv("ALLOW_GROUPS", "0") == "1"     

bot = telebot.TeleBot(TOKEN, parse_mode=None)

# ... импортов и загрузки users.json ...

# ---------------------------- ОКРУЖЕНИЕ ----------------------------
from dotenv import load_dotenv
load_dotenv(override=True)           # ← замени на override=True
TOKEN = os.getenv("BOT_TOKEN")
...
bot = telebot.TeleBot(TOKEN, parse_mode=None)

# ==== ВРЕМЕННЫЕ ДИАГНОСТИЧЕСКИЕ КОМАНДЫ ====
@bot.message_handler(commands=['whoami'])
def whoami(m):
    bot.reply_to(m, f"Ваш user_id: {m.from_user.id}")

@bot.message_handler(func=lambda m: m.forward_from_chat is not None and m.from_user.id in ADMIN_IDS)
def show_forwarded_chat_id(m):
    cid = m.forward_from_chat.id
    ctype = m.forward_from_chat.type
    title = m.forward_from_chat.title
    bot.reply_to(m, f"Forwarded from: {title!r}\nchat_type={ctype}\nchat_id={cid}")
    
@bot.message_handler(commands=['env'])
def env_cmd(m):
    try:
        bme = bot.get_me()
        txt = (
            "🔎 ENV:\n"
            f"CHANNEL_ID = {CHANNEL_ID}\n"
            f"ADMIN_IDS  = {sorted(list(ADMIN_IDS))}\n"
            f"REQUIRE_CODE = {REQUIRE_CODE}\n"
            f"ALLOW_GROUPS = {ALLOW_GROUPS}\n"
            f"BOT (me).id  = {bme.id}\n"
        )
        bot.reply_to(m, txt)
    except Exception as e:
        bot.reply_to(m, f"Ошибка /env: {e}")

@bot.message_handler(commands=['check_access'])
def check_access(m):
    uid = m.from_user.id
    lines = [f"Проверка доступа для user_id={uid} и бота:"]
    try:
        member_me = bot.get_chat_member(CHANNEL_ID, uid)
        lines.append(f"Вы в канале? status={member_me.status!r}")
    except Exception as e:
        lines.append(f"Проверка ВАС: ошибка get_chat_member: {e}")

    try:
        me = bot.get_me()
        member_bot = bot.get_chat_member(CHANNEL_ID, me.id)
        lines.append(f"Бот в канале? status={member_bot.status!r}")
    except Exception as e:
        lines.append(f"Проверка БОТА: ошибка get_chat_member: {e}\n"
                     f"👉 Вероятно, бот НЕ админ канала.")

    bot.reply_to(m, "\n".join(lines))
# ==== КОНЕЦ ДИАГНОСТИКИ ====

# ---------------------------- ДАННЫЕ КОНТЕНТА ----------------------------
file_paths = {
    ...
}

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
        "video_choice": "Video dərс seçin:"
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

def get_safe_lang(uid: int) -> str:
    return user_data.get(uid, {}).get("lang", "ru")

def is_member_of_channel(user_id: int) -> bool:
    """Проверка, состоит ли пользователь в закрытом канале."""
    if not CHANNEL_ID:
        logging.error("CHANNEL_ID не настроен")
        return False
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ("member", "administrator", "creator")
    except ApiTelegramException as e:
        logging.error(f"get_chat_member error: {e}")
        return False
    except Exception as e:
        logging.error(f"membership check failed: {e}")
        return False

def maybe_answer_callback(update):
    """Безопасно отвечаем на callback, чтобы не было 'query is too old'."""
    try:
        if isinstance(update, TGCallbackQuery):
            bot.answer_callback_query(update.id)
    except Exception:
        pass

def require_access(handler):
    """Декоратор: пускаем только участников канала; при необходимости — просим код."""
    @wraps(handler)
    def wrapper(update, *args, **kwargs):
        # Определение контекста
        if isinstance(update, TGCallbackQuery):
            uid = update.from_user.id
            chat_id = update.message.chat.id
        else:
            # Message
            uid = update.from_user.id
            chat_id = update.chat.id

        ensure_user_record(uid)

        # Админам — всегда можно
        if uid in ADMIN_IDS:
            return handler(update, *args, **kwargs)

        # Блок групп при необходимости
        try:
            chat_type = update.chat.type if hasattr(update, "chat") else update.message.chat.type
        except Exception:
            chat_type = "private"
        if not ALLOW_GROUPS and chat_type in ("group", "supergroup"):
            return  # игнорим

        # 1) Проверка членства
        if not is_member_of_channel(uid):
            msg = ("Доступ только для участников закрытого канала.\n"
                   "Вступите в канал и вернитесь к боту.")
            if CHANNEL_INVITE_LINK:
                msg += f"\n\nСсылка: {CHANNEL_INVITE_LINK}"
            bot.send_message(chat_id, msg)
            maybe_answer_callback(update)
            return

        # 2) Если включена проверка кодом — требуем verified
        rec = users.get(str(uid), {})
        if REQUIRE_CODE and not rec.get("verified", False):
            user_data[uid] = user_data.get(uid, {})
            user_data[uid]["state"] = "awaiting_code"
            bot.send_message(chat_id, "🔒 Введите код доступа (из закреплённого сообщения канала):")
            maybe_answer_callback(update)
            return

        # Пропускаем внутрь
        return handler(update, *args, **kwargs)
    return wrapper

@bot.message_handler(commands=['stats', 'count'])
def send_stats(message):
    total = len(users)
    verified = sum(1 for v in users.values() if isinstance(v, dict) and v.get("verified"))
    bot.send_message(message.chat.id, f"Всего пользователей: {total}\nПодтверждены: {verified}")

@bot.message_handler(commands=['setcode'])
def set_code(message):
    """Админ-команда: /setcode NEW_CODE"""
    uid = message.from_user.id
    if uid not in ADMIN_IDS:
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) == 2:
        global ACCESS_CODE
        ACCESS_CODE = parts[1].strip()
        bot.reply_to(message, f"Код обновлён: {ACCESS_CODE}")
    else:
        bot.reply_to(message, "Использование: /setcode NEW_CODE")

@bot.message_handler(commands=['menu'])
@require_access
def show_menu(message):
    user_id = message.from_user.id
    ensure_user_record(user_id)
    if user_id in user_data:
        lang = user_data[user_id].get("lang", "ru")
        name = user_data[user_id].get("name", users.get(str(user_id), {}).get("name", "User"))
        send_main_menu(user_id, lang, name)
    else:
        bot.send_message(message.chat.id, "Пожалуйста, введите /start для начала.")

@bot.message_handler(commands=['start'])
@require_access
def start(message):
    user_id = message.from_user.id
    ensure_user_record(user_id)

    # Новичок — предлагаем выбор языка и приветственное видео
    rec = users.get(str(user_id), {})
    if not rec.get("name"):
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
        user_data[user_id] = {"lang_msg": sent.message_id, "state": "awaiting_language"}
    else:
        # Повторный старт — сразу меню
        lang = user_data.get(user_id, {}).get("lang", "ru")
        name = rec.get("name", "User")
        send_main_menu(user_id, lang, name)

@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
@require_access
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
        logging.error(f"answer_callback_query error: {e}")

@bot.message_handler(func=lambda m: m.from_user.id in user_data and user_data[m.from_user.id].get("state") == "awaiting_name")
@require_access
def get_name(message):
    user_id = message.from_user.id
    ensure_user_record(user_id)
    name = (message.text or "").strip()

    # Сохраняем в users и user_data
    users[str(user_id)]["name"] = name
    save_users()
    user_data[user_id]["name"] = name

    lang = user_data[user_id].get("lang", "ru")
    logging.info(f"User {user_id} named '{name}' started using the bot.")

    try:
        nm = user_data[user_id].get("name_msg", 0)
        if nm:
            bot.delete_message(message.chat.id, nm)
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass

    user_data[user_id]["state"] = "main"
    send_main_menu(user_id, lang, name)

def send_main_menu(user_id: int, lang: str, name: str):
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
@require_access
def callback_handler(call):
    user_id = call.from_user.id
    if user_id not in user_data:
        bot.send_message(call.message.chat.id, "Пожалуйста, используйте /start чтобы начать.")
        bot.answer_callback_query(call.id)
        return

    lang = user_data[user_id].get("lang", "ru")
    name = users.get(str(user_id), {}).get("name", "User")
    # state = user_data[user_id].get("state", "main")

    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass

    if call.data == "materials":
        markup = types.InlineKeyboardMarkup(row_width=1)
        for key, title in texts[lang]["file_titles"].items():
            if key not in VIDEO_FILE_IDS:  # файлы, не видео
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

    # финальный ответ на коллбек
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

@bot.message_handler(func=lambda m: m.from_user.id in user_data and user_data[m.from_user.id].get("state") == "search")
@require_access
def handle_search(message):
    user_id = message.from_user.id
    lang = user_data[user_id].get("lang", "ru")
    query = (message.text or "").lower()

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

@bot.message_handler(func=lambda m: m.from_user.id in user_data and user_data[m.from_user.id].get("state") == "awaiting_code")
def verify_code(message):
    uid = message.from_user.id
    ensure_user_record(uid)
    code = (message.text or "").strip()
    if ACCESS_CODE and code == ACCESS_CODE:
        users[str(uid)]["verified"] = True
        save_users()
        user_data[uid]["state"] = "main"
        bot.reply_to(message, "✅ Доступ подтверждён.")
        # после успешной верификации — запускаем стандартный старт
        return start(message)
    else:
        bot.reply_to(message, "❌ Неверный код. Попробуйте ещё раз.")

@bot.message_handler(func=lambda m: m.chat.type in ["group", "supergroup"])
def handle_group_messages(message):
    if not ALLOW_GROUPS:
        return
    text_lower = (message.text or "").lower()
    if "поиск" in text_lower:
        bot.reply_to(message, "Чтобы начать обучение, нажмите /start или /menu.")
    elif f"@{bot.get_me().username}" in text_lower:
        bot.reply_to(message, "Привет! Я бот для обучения. Напишите /start в личку, чтобы начать.")

@bot.message_handler(content_types=['new_chat_members'])
def greet_new_member(message):
    # это про группы/супергруппы; в личке не потребуется
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
        bot.send_message(message.chat.id, "❗ Пришлите видео, GIF или mp4-документ.")

if __name__ == "__main__":
    try:
        # На всякий случай снимаем вебхук, иначе Telegram будет конфликтовать с polling
        bot.remove_webhook()
    except Exception as e:
        logging.error(f"remove_webhook error: {e}")
    # Один-единственный цикл polling:
    bot.infinity_polling(skip_pending=True, timeout=60)








