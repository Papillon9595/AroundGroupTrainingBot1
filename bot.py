# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
import hmac, hashlib
import threading
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
from urllib.parse import parse_qsl

# ─────────────────── ЛОГИ ───────────────────
logging.basicConfig(filename='bot_errors.log', level=logging.ERROR)

# ─────────────────── USERS ───────────────────
users: dict = {}
users_file = "users.json"

def _save_users():
    with open(users_file, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def ensure_user_record(user_id: int):
    uid = str(user_id)
    if uid not in users:
        users[uid] = {"name": "", "verified": False, "phone": "", "phone_ok": False}
        _save_users()
    else:
        rec = users[uid]
        if "name" not in rec:      rec["name"] = ""
        if "verified" not in rec:  rec["verified"] = False
        if "phone" not in rec:     rec["phone"] = ""
        if "phone_ok" not in rec:  rec["phone_ok"] = False

try:
    with open(users_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)
        if isinstance(loaded, dict):
            users = loaded
            # миграция старого формата
            for k, v in list(users.items()):
                if isinstance(v, str):
                    users[k] = {"name": v, "verified": False, "phone": "", "phone_ok": False}
                else:
                    if "name" not in v:     users[k]["name"] = ""
                    if "verified" not in v: users[k]["verified"] = False
                    if "phone" not in v:    users[k]["phone"] = ""
                    if "phone_ok" not in v: users[k]["phone_ok"] = False
            _save_users()
        else:
            users = {}
except FileNotFoundError:
    users = {}

# ─────────────────── ENV ───────────────────
load_dotenv(override=True)

def _parse_int_set(env_name: str):
    raw = (os.getenv(env_name) or "").strip()
    if not raw:
        return set()
    return set(int(x) for x in raw.replace(" ", "").split(",") if x)

# whitelist телефонов
def normalize_phone(p: str) -> str:
    if not p:
        return ""
    digits = "".join(ch for ch in str(p) if ch.isdigit())
    return f"+{digits}" if digits else ""

def _parse_phone_set_from_env(env_name: str) -> set[str]:
    raw = (os.getenv(env_name) or "").strip()
    if not raw:
        return set()
    parts = [x for x in raw.replace(" ", "").split(",") if x]
    return {normalize_phone(x) for x in parts}

def _parse_phone_set_from_file(path: str) -> set[str]:
    s = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                s.add(normalize_phone(line))
    except FileNotFoundError:
        pass
    return s

REQUIRE_PHONE       = os.getenv("REQUIRE_PHONE", "0") == "1"
ALLOWED_PHONES_FILE = (os.getenv("ALLOWED_PHONES_FILE") or "").strip()

def load_allowed_phones() -> set[str]:
    s = _parse_phone_set_from_env("ALLOWED_PHONES")
    if ALLOWED_PHONES_FILE:
        s |= _parse_phone_set_from_file(ALLOWED_PHONES_FILE)
    return {p for p in s if p and p != "+"}

ALLOWED_SET = load_allowed_phones()

TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
if not TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения")

ADMIN_IDS   = _parse_int_set("ADMIN_IDS")
ALLOW_GROUPS = os.getenv("ALLOW_GROUPS", "0") == "1"

# WebApp/OTP/Webhook
REQUIRE_CODE  = os.getenv("REQUIRE_CODE", "0") == "1"
OTP_TTL_SECS  = int(os.getenv("OTP_TTL_SECS", "600"))
OTP_LENGTH    = int(os.getenv("OTP_LENGTH", "6"))
OTP_ATTEMPTS  = int(os.getenv("OTP_ATTEMPTS", "3"))
USE_WEBHOOK   = os.getenv("USE_WEBHOOK", "0") == "1"
PUBLIC_URL    = (os.getenv("PUBLIC_URL") or "").rstrip("/")
WEBAPP_URL    = (os.getenv("WEBAPP_URL") or "").strip()

# ──────────────── BOT ────────────────
bot = telebot.TeleBot(TOKEN, parse_mode=None)

# ──────────────── OTP ────────────────
otp_store = {}  # uid -> {'code': '123456', 'exp': ts, 'attempts': 3}

def _gen_otp(n: int) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(n))

def issue_otp(uid: int) -> str:
    code = _gen_otp(OTP_LENGTH)
    otp_store[uid] = {"code": code, "exp": time.time() + OTP_TTL_SECS, "attempts": OTP_ATTEMPTS}
    return code

def check_otp(uid: int, code: str):
    rec = otp_store.get(uid)
    if not rec:
        return False, "Код не запрошен."
    if time.time() > rec["exp"]:
        otp_store.pop(uid, None)
        return False, "Код истёк. Запросите новый."
    if code != rec["code"]:
        rec["attempts"] -= 1
        if rec["attempts"] <= 0:
            otp_store.pop(uid, None)
            return False, "Код заблокирован. Запросите новый."
        return False, f"Неверный код. Осталось попыток: {rec['attempts']}"
    otp_store.pop(uid, None)
    return True, ""

# ──────────────── КОНТЕНТ ────────────────
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
        "materials": "Материалы", "videoguides": "Видеоуроки", "contact": "Контакты", "search": "Поиск",
        "choose_file": "Выберите нужный файл:", "back": "Назад", "contact_text": "Вы можете связаться с нами по следующим контактам:",
        "file_titles": {
            "direct": "Видео-инструкция Ploom Direct","reboot": "Перезагрузка PloomXAdvanced",
            "replacement": "Замена в Phouse-IMS","return": "Возврат в Phouse-IMS",
            "unregisteredconsumer": "Клиент без регистрации в Phouse-IMS","product": "Информация о продукте",
            "sales": "Скрипты продаж","sticks": "Стики Sobranie","accessories": "Аксессуары"
        }, "video_choice": "Выберите видеоурок:"
    },
    "az": {
        "welcome":"Salam, mən Ploom şirkətinin Botuyam və Sizə təlimdə köməklik göstərəcəyəm. Sizə necə müraciət edə bilərəm?",
        "name_reply":"Tanış olduğumuza şadam, {name}!\nZəhmət olmasa bölmə seçin:",
        "materials":"Materiallar","videoguides":"Video dərslər","contact":"Əlaqə","search":"Axtarış",
        "choose_file":"Zəhmət olmasa faylı seçin:","back":"Geri","contact_text":"Aşağıdakı şəxslərlə əlaqə saxlaya bilərsiniz:",
        "file_titles":{
            "direct":"Ploom Direct üzrə Video təlimat","reboot":"PloomXAdvanced Sıfırlanması",
            "replacement":"Dəyisdirilmə Phouse-IMS","return":"Qaytarılma Phouse-IMS",
            "unregisteredconsumer":"Qeydiyyatsız müştəri Phouse-IMS","product":"Məhsul haqqında məlumat",
            "sales":"Satış skriptləri","sticks":"Sobranie Stikləri","accessories":"Aksessuarlar"
        },"video_choice":"Video dərslər seçin:"
    },
    "en": {
        "welcome":"Hello, I am the Ploom company Bot, and I will help You with your training. How can I address You?",
        "name_reply":"Nice to meet you, {name}!\nPlease choose a section:",
        "materials":"Materials","videoguides":"Video Lessons","contact":"Contact","search":"Search",
        "choose_file":"Please choose a file:","back":"Back","contact_text":"You can contact us via:",
        "file_titles":{
            "direct":"Video Instructions of Ploom Direct","reboot":"How to reboot PloomXAdvanced",
            "replacement":"Replacement Phouse-IMS","return":"Return&Refund Phouse-IMS",
            "unregisteredconsumer":"Unregistered consumer Phouse-IMS","product":"Product Info",
            "sales":"Sales Scripts","sticks":"Sobranie Sticks","accessories":"Accessories"
        },"video_choice":"Choose a video lesson:"
    }
}
user_data = {}
search_keywords = {
    "direct": ["direct","ploom direct","видео инструкция","инструкция","video instruction"],
    "reboot": ["reboot","reset","перезагрузка","сброс","restart"],
    "replacement": ["replacement","замена","phouse-ims","замена phouse-ims"],
    "return": ["return","refund","возврат","phouse-ims"],
    "unregisteredconsumer": ["unregistered","consumer","клиент","без регистрации","phouse-ims"],
    "product": ["product","продукт","информация","info","продукт информация"],
    "sales": ["sales","продажи","скрипты","scripts"],
    "sticks": ["sticks","stiks","sobranie","стики"],
    "accessories": ["accessories","аксессуары"],
}

# ──────────────── ACCESS ────────────────
def maybe_answer_callback(update):
    try:
        if isinstance(update, TGCallbackQuery):
            bot.answer_callback_query(update.id)
    except Exception:
        pass

def require_access(handler):
    """
    Доступ только для:
      - админов, ИЛИ
      - пользователей с phone_ok=True (номер в whitelist) + (если включено) verified=True (OTP через WebApp)
    """
    @wraps(handler)
    def wrapper(update, *args, **kwargs):
        if isinstance(update, TGCallbackQuery):
            uid = update.from_user.id
            chat_id = update.message.chat.id
            chat_type = getattr(update.message.chat, "type", "private")
        else:
            uid = update.from_user.id
            chat_id = update.chat.id
            chat_type = getattr(update.chat, "type", "private")

        ensure_user_record(uid)

        if uid in ADMIN_IDS:
            return handler(update, *args, **kwargs)

        if not ALLOW_GROUPS and chat_type in ("group", "supergroup"):
            return

        rec = users.get(str(uid), {})

        if REQUIRE_PHONE and not rec.get("phone_ok"):
            kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            kb.add(types.KeyboardButton("Подтвердить номер 📱", request_contact=True))
            bot.send_message(
                chat_id,
                "Доступ только для номеров из списка.\n"
                "Нажмите «Подтвердить номер 📱», чтобы отправить свой номер из Telegram.",
                reply_markup=kb
            )
            maybe_answer_callback(update)
            return

        if REQUIRE_CODE and not rec.get("verified", False):
            kb = types.InlineKeyboardMarkup()
            if WEBAPP_URL:
                kb.add(types.InlineKeyboardButton(
                    "Открыть форму подтверждения",
                    web_app=types.WebAppInfo(url=WEBAPP_URL)
                ))
                bot.send_message(
                    chat_id,
                    "🔒 Требуется подтверждение входа. Откройте форму и завершите подтверждение.",
                    reply_markup=kb
                )
            else:
                bot.send_message(chat_id, "WEBAPP_URL не настроен. Обратитесь к администратору.")
            maybe_answer_callback(update)
            return

        return handler(update, *args, **kwargs)
    return wrapper

# ──────────────── WebApp (Flask) ────────────────
app = Flask(__name__)

HTML_WEBAPP = r"""
<!doctype html><html lang="ru"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<title>Подтверждение доступа</title>
<style>
  body{background:#111;color:#fff;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:0;padding:24px}
  h1{font-size:20px;margin:0 0 16px}
  .small{opacity:.8;font-size:12px;text-align:center;margin-top:8px}
  .boxes{display:flex;gap:10px;justify-content:center;margin:24px 0}
  .box{width:44px;height:56px;border-radius:12px;border:1px solid #333;display:flex;align-items:center;justify-content:center;font-size:24px;background:#1a1a1a}
  #err{color:#f66;margin-top:8px;min-height:20px;text-align:center}
  .btn{display:block;width:100%;padding:14px;border-radius:12px;border:none;background:#2ea44f;color:#fff;font-size:16px;margin-top:12px}
  .sec{display:flex;gap:10px}
  input[type=tel]{opacity:0;position:absolute;left:-9999px}
</style></head><body>
<h1>Подтверждение доступа</h1>
<div class="small">Нажмите «Получить код», затем «Подтвердить».</div>
<div class="boxes" id="boxes"></div>
<div id="err"></div>
<div class="sec">
  <button class="btn" id="btnIssue" style="background:#444">Получить код</button>
  <button class="btn" id="btnSend" disabled>Подтвердить</button>
</div>
<input id="hid" inputmode="numeric" pattern="[0-9]*" type="tel" maxlength="6" autocomplete="one-time-code" />
<script>
const tg = window.Telegram.WebApp; tg.expand();
const initData = tg.initData || "";

const hid = document.getElementById('hid');
const boxes = document.getElementById('boxes');
const btnIssue = document.getElementById('btnIssue');
const btnSend = document.getElementById('btnSend');
const err = document.getElementById('err');

for(let i=0;i<6;i++){ const d=document.createElement('div'); d.className='box'; boxes.appendChild(d); }
function render(){
  const v=hid.value.replace(/\D/g,"").slice(0,6);
  hid.value=v; [...boxes.children].forEach((b,i)=>{ b.textContent = v[i] ? v[i] : "" });
  btnSend.disabled = v.length!==6;
}
boxes.addEventListener('click', ()=>hid.focus()); render();

btnIssue.addEventListener('click', async ()=>{
  try{
    if(!initData){ err.textContent='WebApp открыт вне Telegram. Запустите форму из бота.'; return; }
    const r = await fetch('/api/otp/issue?init_data=' + encodeURIComponent(initData), {
      method:'POST',
      headers:{'X-Init-Data': initData, 'Content-Type':'application/json'},
      body: JSON.stringify({init_data: initData})
    });
    const j = await r.json();
    if(!j.ok){ err.textContent = j.error || 'Не удалось получить код'; return; }
    document.getElementById('hid').value = (j.code || '').toString().slice(0,6);
    render();
    err.textContent = 'Код сгенерирован. Нажмите «Подтвердить». Срок: ' + j.ttl_min + ' мин.';
    hid.focus();
  }catch(e){ err.textContent = 'Сеть недоступна'; }
});

btnSend.addEventListener('click', async ()=>{
  try{
    const code = hid.value;
    const r = await fetch('/api/otp/verify?init_data=' + encodeURIComponent(initData), {
      method:'POST',
      headers:{'X-Init-Data': initData, 'Content-Type':'application/json'},
      body: JSON.stringify({code, init_data: initData})
    });
    const j = await r.json();
    if(!j.ok){ err.textContent = j.error || 'Код не принят'; return; }
    tg.showAlert('Доступ подтверждён'); tg.close();
  }catch(e){ err.textContent = 'Сеть недоступна'; }
});
</script></body></html>
"""

def _verify_webapp_init_data(init_data: str):
    """
    Каноничная проверка подписи WebApp. Возвращает {"user_id": int} или None.
    """
    try:
        if not init_data:
            return None
        data = dict(parse_qsl(init_data, strict_parsing=True))
        recv_hash = data.pop('hash', None)
        if not recv_hash:
            return None
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
        secret = hashlib.sha256(TOKEN.encode()).digest()
        calc_hash = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
        if calc_hash != recv_hash:
            return None
        user_json = data.get('user')
        if not user_json:
            return None
        user = json.loads(user_json)
        return {"user_id": int(user["id"])}
    except Exception as e:
        logging.error(f"verify_webapp_init_data error: {e}")
        return None

def _extract_init_data():
    """
    Берём init_data из заголовка, query и/или body — что дойдёт.
    """
    init_data = request.headers.get('X-Init-Data', '') or ""
    if not init_data:
        init_data = request.args.get('init_data', '') or ""
    if not init_data:
        init_data = (request.get_json(silent=True) or {}).get('init_data', '') or ""
    return init_data

@app.get("/webapp")
def webapp_page():
    return HTML_WEBAPP

@app.post("/api/otp/issue")
def api_issue():
    init_data = _extract_init_data()
    info = _verify_webapp_init_data(init_data)
    if not info:
        return jsonify(ok=False, error="bad signature"), 403
    uid = info["user_id"]

    # проверка номера (если включена)
    if REQUIRE_PHONE:
        ensure_user_record(uid)
        if not users[str(uid)].get("phone_ok"):
            return jsonify(ok=False, error="phone not approved"), 403

    code = issue_otp(uid)
    return jsonify(ok=True, code=code, ttl=OTP_TTL_SECS, ttl_min=max(1, OTP_TTL_SECS//60))

@app.post("/api/otp/verify")
def api_verify():
    init_data = _extract_init_data()
    info = _verify_webapp_init_data(init_data)
    if not info:
        return jsonify(ok=False, error="bad signature"), 403
    uid = info["user_id"]

    payload = request.get_json(silent=True) or {}
    code = str(payload.get('code','')).strip()
    ok, msg = check_otp(uid, code)
    if not ok:
        return jsonify(ok=False, error=msg)

    ensure_user_record(uid)
    users[str(uid)]["verified"] = True
    _save_users()
    return jsonify(ok=True)

# ──────────────── Webhook endpoint (если используется) ────────────────
WEBHOOK_PATH = f"/tg/{TOKEN}"

@app.post(WEBHOOK_PATH)
def telegram_webhook():
    if request.headers.get('content-type') == 'application/json':
        js = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(js)
        bot.process_new_updates([update])
        return 'ok', 200
    return 'bad', 400

# ──────────────── HANDLERS ────────────────
@bot.message_handler(content_types=["contact"])
def handle_contact(message):
    uid = message.from_user.id
    ensure_user_record(uid)

    if not message.contact or message.contact.user_id != uid:
        bot.reply_to(message, "Отправьте свой номер через кнопку «Подтвердить номер 📱».")
        return

    phone = normalize_phone(message.contact.phone_number)
    if not phone:
        bot.reply_to(message, "Не удалось распознать номер. Попробуйте ещё раз.")
        return

    users[str(uid)]["phone"] = phone
    users[str(uid)]["phone_ok"] = (phone in ALLOWED_SET)
    _save_users()

    bot.send_message(message.chat.id, f"Номер получен: {phone}", reply_markup=types.ReplyKeyboardRemove())

    if not users[str(uid)]["phone_ok"]:
        bot.send_message(message.chat.id, "❌ Ваш номер не в списке доступа. Обратитесь к администратору.")
        return

    if REQUIRE_CODE and not users[str(uid)].get("verified"):
        kb = types.InlineKeyboardMarkup()
        if WEBAPP_URL:
            kb.add(types.InlineKeyboardButton(
                "Открыть форму подтверждения",
                web_app=types.WebAppInfo(url=WEBAPP_URL)
            ))
        bot.send_message(message.chat.id, "✅ Номер подтверждён. Осталось подтвердить вход:", reply_markup=kb)
    else:
        bot.send_message(message.chat.id, "✅ Доступ разрешён. Открываю меню…")
        try:
            start(message)
        except Exception:
            pass

@bot.message_handler(commands=["reload_phones"])
def reload_phones_cmd(m):
    if m.from_user.id not in ADMIN_IDS:
        return
    global ALLOWED_SET
    ALLOWED_SET = load_allowed_phones()
    bot.reply_to(m, f"Список телефонов обновлён. Всего: {len(ALLOWED_SET)}")

@bot.message_handler(commands=['stats', 'count'])
def send_stats(message):
    total = len(users)
    verified = sum(1 for v in users.values() if isinstance(v, dict) and v.get("verified"))
    bot.send_message(message.chat.id, f"Всего пользователей: {total}\nПодтверждены (OTP): {verified}")

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
    _save_users()
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

    user_data.setdefault(user_id, {})
    user_data[user_id].update({"state": "main", "lang": lang, "name": name})

@bot.callback_query_handler(func=lambda call: True)
@require_access
def callback_handler(call):
    user_id = call.from_user.id

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

# ──────────────── RUN ────────────────
if __name__ == "__main__":
    try:
        bot.remove_webhook()

        if USE_WEBHOOK:
            if not PUBLIC_URL:
                raise SystemExit("PUBLIC_URL не задан. Укажи https://<your-app>.up.railway.app")
            bot.set_webhook(url=PUBLIC_URL + f"/tg/{TOKEN}", drop_pending_updates=True)
            app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")), threaded=True, use_reloader=False)
        else:
            threading.Thread(
                target=lambda: app.run(host="0.0.0.0", port=int(os.getenv("PORT","8080")), threaded=True, use_reloader=False),
                daemon=True
            ).start()
            bot.infinity_polling(skip_pending=True, timeout=60)

    except ApiTelegramException as e:
        print(f"❌ Telegram error: {e}")
        raise
