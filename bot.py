# -*- coding: utf-8 -*-
import os
import json
import logging
from functools import wraps
import secrets
import string
import time

import telebot
from telebot import types
from telebot.types import CallbackQuery as TGCallbackQuery
from telebot.apihelper import ApiTelegramException
from dotenv import load_dotenv

# ─────────────────────────── ЛОГИ ───────────────────────────
logging.basicConfig(filename='bot_errors.log', level=logging.ERROR)

# ───────────────────── ДАННЫЕ ПОЛЬЗОВАТЕЛЕЙ ─────────────────
users: dict = {}
users_file = "users.json"

try:
    with open(users_file, "r", encoding="utf-8") as f:
        users = json.load(f)
        # Миграция: "123":"Имя" -> "123":{"name":"Имя","verified":False}
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

# ───────────────────────── ОКРУЖЕНИЕ ────────────────────────
load_dotenv(override=True)

TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
if not TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения")

def _parse_int_set(env_name: str):
    raw = os.getenv(env_name, "").strip()
    if not raw:
        return set()
    return set(int(x) for x in raw.replace(" ", "").split(",") if x)

CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))           # -100xxxxxxxxxxxx
CHANNEL_INVITE_LINK = os.getenv("CHANNEL_INVITE_LINK", "")
ADMIN_IDS = _parse_int_set("ADMIN_IDS")                  # 111,222
REQUIRE_CODE = os.getenv("REQUIRE_CODE", "0") == "1"     # "1" -> True
ACCESS_CODE = (os.getenv("ACCESS_CODE") or "").strip()   # можно оставить пустым
ALLOW_GROUPS = os.getenv("ALLOW_GROUPS", "0") == "1"     # "1" -> True

# OTP-параметры
OTP_TTL_SECS = int(os.getenv("OTP_TTL_SECS", "600"))
OTP_LENGTH = int(os.getenv("OTP_LENGTH", "6"))
OTP_ATTEMPTS = int(os.getenv("OTP_ATTEMPTS", "3"))

# ─────────────────────── ИНИЦИАЛИЗАЦИЯ БОТА ─────────────────
bot = telebot.TeleBot(TOKEN, parse_mode=None)

# ─────────────────────────── OTP ЛОГИКА ─────────────────────
# uid -> {'code': '123456', 'exp': ts, 'attempts': 3}
otp_store = {}

def _gen_otp(length: int) -> str:
    # только цифры: удобнее на телефоне
    return "".join(secrets.choice(string.digits) for _ in range(length))

def issue_otp(uid: int) -> str:
    """Создать и сохранить одноразовый код для пользователя."""
    code = _gen_otp(OTP_LENGTH)
    otp_store[uid] = {
        "code": code,
        "exp": time.time() + OTP_TTL_SECS,
        "attempts": OTP_ATTEMPTS,
    }
    return code

def check_otp(uid: int, code: str):
    """
    Проверить введённый код.
    Возвращает (ok: bool, msg: str). msg — причина ошибки.
    """
    rec = otp_store.get(uid)
    if not rec:
        return False, "Код не запрошен. Нажмите «Получить код»."
    if time.time() > rec["exp"]:
        otp_store.pop(uid, None)
        return False, "Код истёк. Запросите новый."
    if code != rec["code"]:
        rec["attempts"] -= 1
        if rec["attempts"] <= 0:
            otp_store.pop(uid, None)
            return False, "Код заблокирован из-за попыток. Запросите новый."
        return False, f"Неверный код. Осталось попыток: {rec['attempts']}"
    # успех — сжигаем код
    otp_store.pop(uid, None)
    return True, ""

# ────────────────────────── КОНТЕНТ ─────────────────────────
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
        "video_choice": "Video dərslər seçin:"
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

# ─────────────────────────── УТИЛИТЫ ─────────────────────────
def is_member_of_channel(user_id: int) -> bool:
    if not CHANNEL_ID:
        logging.error("CHANNEL_ID не настроен")
        return False
    try:
        m = bot.get_chat_member(CHANNEL_ID, user_id)
        return m.status in ("member", "administrator", "creator")
    except Exception as e:
        logging.error(f"get_chat_member error: {e}")
        return False

def maybe_answer_callback(update):
    try:
        if isinstance(update, TGCallbackQuery):
            bot.answer_callback_query(update.id)
    except Exception:
        pass

def require_access(handler):
    """Доступ только для участников канала. Если включено — требуем код/OTP."""
    @wraps(handler)
    def wrapper(update, *args, **kwargs):
        # контекст
        if isinstance(update, TGCallbackQuery):
            uid = update.from_user.id
            chat_id = update.message.chat.id
            chat_type = getattr(update.message.chat, "type", "private")
        else:
            uid = update.from_user.id
            chat_id = update.chat.id
            chat_type = getattr(update.chat, "type", "private")

        ensure_user_record(uid)

        # админам можно всегда
        if uid in ADMIN_IDS:
            return handler(update, *args, **kwargs)

        # блок групп при необходимости
        if not ALLOW_GROUPS and chat_type in ("group", "supergroup"):
            return

        # 1) членство
        if not is_member_of_channel(uid):
            # если был подтверждён — сбросим
            try:
                if users.get(str(uid), {}).get("verified"):
                    users[str(uid)]["verified"] = False
                    save_users()
            except Exception:
                pass

            msg = ("Доступ только для участников закрытого канала.\n"
                   "Вступите в канал и вернитесь к боту.")
            if CHANNEL_INVITE_LINK:
                msg += f"\n\nСсылка: {CHANNEL_INVITE_LINK}"
            bot.send_message(chat_id, msg)
            maybe_answer_callback(update)
            return

        # 2) если включена проверка — требуем verified
        rec = users.get(str(uid), {})
        if REQUIRE_CODE and not rec.get("verified", False):
            user_data.setdefault(uid, {})
            user_data[uid]["state"] = "awaiting_code"

            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("Получить код", callback_data="otp_get"))

            bot.send_message(
                chat_id,
                "🔒 Требуется подтверждение доступа.\n"
                "Нажмите «Получить код», затем введите присланный одноразовый код.",
                reply_markup=kb
            )
            maybe_answer_callback(update)
            return

        return handler(update, *args, **kwargs)
    return wrapper

# ─────────────────────────── ХЭНДЛЕРЫ ────────────────────────
@bot.callback_query_handler(func=lambda c: c.data == "otp_get")
def on_otp_get(c):
    uid = c.from_user.id
    chat_id = c.message.chat.id

    # код только членам канала
    if not is_member_of_channel(uid):
        try:
            bot.answer_callback_query(c.id, "Сначала вступите в канал.", show_alert=True)
        except Exception:
            pass
        return

    ensure_user_record(uid)
    code = issue_otp(uid)

    try:
        bot.answer_callback_query(c.id, "Код отправлен", show_alert=False)
    except Exception:
        pass

    mins = max(1, OTP_TTL_SECS // 60)
    bot.send_message(
        chat_id,
        f"Ваш одноразовый код: **{code}**\n"
        f"Действует {mins} мин. Введите его одним сообщением.",
        parse_mode="Markdown"
    )

    user_data.setdefault(uid, {})
    user_data[uid]["state"] = "awaiting_code"

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
        bot.reply_to(message, "Код обновлён.")
    else:
        bot.reply_to(message, "Использование: /setcode NEW_CODE")

@bot.message_handler(commands=['menu'])
@require_access
def show_menu(message):
    uid = message.from_user.id
    ensure_user_record(uid)
    rec = users.get(str(uid), {})
    lang = user_data.get(uid, {}).get("lang", "ru")
    name = rec.get("name", "User")
    send_main_menu(uid, lang, name)

@bot.message_handler(commands=['start'])
@require_access
def start(message):
    user_id = message.from_user.id
    ensure_user_record(user_id)

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

        sent = bot.send_message(
            message.chat.id,
            "Выберите язык / Select language / Dil seçin:",
            reply_markup=lang_markup
        )
        user_data[user_id] = {"lang_msg": sent.message_id, "state": "awaiting_language"}
    else:
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
    except Exception:
        pass

@bot.message_handler(func=lambda m: m.from_user.id in user_data and user_data[m.from_user.id].get("state") == "awaiting_name")
@require_access
def get_name(message):
    user_id = message.from_user.id
    ensure_user_record(user_id)
    name = (message.text or "").strip()

    users[str(user_id)]["name"] = name
    save_users()
    user_data[user_id]["name"] = name

    lang = user_data[user_id].get("lang", "ru")

    try:
        nm = user_data[user_id].get("name_msg", 0)
        if nm:
            bot.delete_message(message.chat.id, nm)
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass

    user_data[user_id]["state"] = "main"
    send_main_menu(user_id, lang, name)

def send_main_menu(user_id: int, lang: str = None, name: str = None):
    # восстановим lang/name
    rec = users.get(str(user_id), {})
    lang = (lang or user_data.get(user_id, {}).get("lang") or "ru")
    name = (name or user_data.get(user_id, {}).get("name") or rec.get("name", "User"))

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(texts[lang]["materials"], callback_data="materials"),
        types.InlineKeyboardButton(texts[lang]["videoguides"], callback_data="videoguides"),
        types.InlineKeyboardButton(texts[lang]["contact"], callback_data="contact"),
        types.InlineKeyboardButton(texts[lang]["search"], callback_data="search")
    )
    bot.send_message(user_id, texts[lang]["name_reply"].format(name=name), reply_markup=markup)

    # гарантируем сессию
    user_data.setdefault(user_id, {})
    user_data[user_id].update({"state": "main", "lang": lang, "name": name})

@bot.callback_query_handler(func=lambda call: True)
@require_access
def callback_handler(call):
    user_id = call.from_user.id

    # если бот перезапускался и user_data потерялась — восстановим сессию
    if user_id not in user_data:
        rec = users.get(str(user_id), {})
        send_main_menu(user_id, "ru", rec.get("name", "User"))
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        return

    lang = user_data[user_id].get("lang", "ru")
    name = users.get(str(user_id), {}).get("name", "User")

    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass

    if call.data == "materials":
        markup = types.InlineKeyboardMarkup(row_width=1)
        for key, title in texts[lang]["file_titles"].items():
            if key not in VIDEO_FILE_IDS:
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
            bot.send_video(
                call.message.chat.id,
                file_id,
                caption=texts[lang]["file_titles"].get(file_key, file_key),
                reply_markup=markup
            )
        else:
            path = file_paths.get(file_key)
            if path and path.startswith("http"):
                bot.send_message(
                    call.message.chat.id,
                    f"{texts[lang]['file_titles'].get(file_key, file_key)}:\n{path}",
                    reply_markup=markup
                )
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
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        bot.send_message(call.message.chat.id, texts[lang]["search"] + ": Введите ключевое слово для поиска.")
        user_data[user_id]["state"] = "search"

    elif call.data == "main_menu":
        send_main_menu(user_id, lang, name)

    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

# ─────────────────────────── ПОИСК ──────────────────────────
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

# ─────────────────────── ВЕРИФИКАЦИЯ КОДА ────────────────────
@bot.message_handler(func=lambda m: m.from_user.id in user_data and user_data[m.from_user.id].get("state") == "awaiting_code")
def verify_code(message):
    uid = message.from_user.id
    ensure_user_record(uid)
    code = (message.text or "").strip()

    ok, reason = False, ""

    # (опционально) общий код как бэкап
    if ACCESS_CODE and code == ACCESS_CODE:
        ok = True
    else:
        ok, reason = check_otp(uid, code)

    if not ok:
        bot.reply_to(message, f"❌ {reason}")
        return

    users[str(uid)]["verified"] = True
    save_users()
    user_data[uid]["state"] = "main"
    bot.reply_to(message, "✅ Доступ подтверждён.")
    start(message)

# ─────────────────────────── ГРУППЫ ─────────────────────────
@bot.message_handler(func=lambda m: m.chat.type in ["group", "supergroup"])
def handle_group_messages(message):
    if not ALLOW_GROUPS:
        return
    text_lower = (message.text or "").lower()
    if "поиск" in text_lower:
        bot.reply_to(message, "Чтобы начать обучение, нажмите /start или /menu.")
    elif f"@{bot.get_me().username}" in text_lower:
        bot.reply_to(message, "Привет! Я бот для обучения. Напишите /start в личку, чтобы начать.")

# ─────────────────────────── МЕДИА ──────────────────────────
@bot.message_handler(content_types=['video', 'animation', 'document'])
def handle_media_messages(message):
    if message.video:
        bot.send_message(message.chat.id, f"📹 Это video\n`{message.video.file_id}`", parse_mode='Markdown')
    elif message.animation:
        bot.send_message(message.chat.id, f"🌀 Это animation (GIF)\n`{message.animation.file_id}`", parse_mode='Markdown')
    elif message.document:
        file = message.document
        if file.mime_type == "video/mp4":
            bot.send_message(message.chat.id, f"📁 Это .mp4 отправлено как документ\n`{file.file_id}`", parse_mode='Markdown')
        else:
            bot.send_message(message.chat.id, f"📁 Документ: {file.file_name} (тип: {file.mime_type})")
    else:
        bot.send_message(message.chat.id, "❗ Пришлите видео, GIF или mp4-документ.")

# ─────────────────────────── ЗАПУСК ─────────────────────────
if __name__ == "__main__":
    try:
        bot.remove_webhook()
        bot.get_me()  # валидируем токен на старте
    except Exception as e:
        print(f"❌ Startup error: {e}")
        raise SystemExit(1)
    bot.infinity_polling(skip_pending=True, timeout=60)
