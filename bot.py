import re
import requests
import base64
import json
import os
import time
import telebot
from threading import Thread
from flask import Flask

CONFIG_FILE = "config_allowed_users.json"

# ---- Telegram Configuration ----
BOT_TOKEN = "8917211694:AAHxHW0_1nDvLFiRMpBDYG6oahkOi9Fusa8"

# 👑 Main Owner ID
OWNER_ID = 6779617599

# ---- Flask Server Configuration (Render 24/7 Uptime) ----
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is awake and running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def load_allowed_users():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                return data.get("allowed_users", [])
        except:
            pass
    return []

def save_allowed_users(users):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump({"allowed_users": users}, f)
    except Exception as e:
        print(f"Error saving config: {e}")

ALLOWED_USERS = load_allowed_users()
bot = telebot.TeleBot(BOT_TOKEN)
user_sessions = {}

def is_owner(chat_id):
    return chat_id == OWNER_ID

def is_allowed(chat_id):
    return chat_id == OWNER_ID or chat_id in ALLOWED_USERS

def extract_session_id(text_or_url):
    try:
        from urllib.parse import unquote
        decoded_text = unquote(text_or_url)
        
        # ၁။ sessionId ကို အမျိုးမျိုးသောပုံစံဖြင့် ရှာဖွေခြင်း
        patterns = [
            r"[?&]sessionId=([a-zA-Z0-9_-]+)",
            r"sessionId/([a-zA-Z0-9_-]+)",
            r"[?&]gw_id=([a-zA-Z0-9_-]+)",
            r"[?&]token=([a-zA-Z0-9_-]+)",
            r"[?&]id=([a-zA-Z0-9_-]+)"
        ]
        
        for pat in patterns:
            match = re.search(pat, decoded_text)
            if match: return match.group(1)
            match_orig = re.search(pat, text_or_url)
            if match_orig: return match_orig.group(1)

        # ၂။ URL ထဲတွင် ပါဝင်သော ရှည်လျားသော ID သို့မဟုတ် Token များကိုပါ ရှာပေးရန်
        if "http" in text_or_url:
            parts = text_or_url.replace("?", "&").split("&")
            for p in parts:
                if "=" in p:
                    k, v = p.split("=", 1)
                    if len(v) > 10 and k.lower() not in ['url', 'link', 'redirect']:
                        return v.strip()

        clean_text = text_or_url.strip()
        if len(clean_text) > 8 and not clean_text.startswith("http") and " " not in clean_text:
            return clean_text
        return None
    except Exception as e:
        print(f"Error extracting session ID: {e}")
        return None

def login_voucher(session_id, voucher):
    data = {"accessCode": voucher, "sessionId": session_id, "apiVersion": 2}
    post_url = base64.b64decode(b'aHR0cHM6Ly9wb3J0YWwtYXMucnVpamllbmV0d29ya3MuY29tL2FwaS9hdXRoL3ZvdWNoZXIvP2xhbmc9ZW5fVVM=').decode()
    
    # 403 Forbidden မတက်စေရန် Browser ပုံစံ Headers အပြည့်အစုံသုံးခြင်း
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/json",
        "origin": "https://portal-as.ruijienetworks.com",
        "referer": "https://portal-as.ruijienetworks.com/",
        "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    }
    try:
        with requests.post(post_url, json=data, headers=headers, timeout=10) as response:
            res_text = response.text
            print(f"Server Response Debug: {res_text}")
            
            # ပုံမှန် token ပြန်လာခြင်း
            token_match = re.search(r'token=(.*?)&', res_text)
            if token_match:
                return token_match.group(1), None
            
            # JSON Response ကို စစ်ဆေးခြင်း
            try:
                res_json = response.json()
                # အောင်မြင်သော Response
                if 'result' in res_json and isinstance(res_json['result'], dict):
                    token = res_json['result'].get('token') or res_json['result'].get('sessionId')
                    if token: 
                        return token, None
                
                # Error Message ကို ထုတ်ယူခြင်း
                error_msg = res_json.get('message') or res_json.get('msg') or res_json.get('error')
                if error_msg:
                    return None, error_msg
                    
                # result ထဲတွင် error ရှိမရှိ စစ်ဆေးခြင်း
                if 'result' in res_json and isinstance(res_json['result'], dict):
                    result_error = res_json['result'].get('message') or res_json['result'].get('error')
                    if result_error:
                        return None, result_error
                        
            except json.JSONDecodeError:
                # JSON မဟုတ်သော Response
                if "Invalid" in res_text or "invalid" in res_text:
                    return None, "Invalid Voucher Code"
                elif "expired" in res_text or "Expired" in res_text:
                    return None, "Voucher Expired"
                elif "used" in res_text or "Used" in res_text:
                    return None, "Voucher Already Used"
                else:
                    return None, res_text[:100] if res_text else "Unknown Error"
            
            return None, "Invalid Voucher Code"
            
    except requests.exceptions.Timeout:
        return None, "Connection Timeout"
    except requests.exceptions.ConnectionError:
        return None, "Network Error"
    except Exception as Error:
        return None, str(Error)

def get_balance(active_session_id):
    headers = {
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'accept-language': 'en-US,en;q=0.9',
        'referer': 'https://portal-as.ruijienetworks.com/',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
    }
    try:
        response = requests.get(
            f'https://portal-as.ruijienetworks.com/api/auth/balance/getBalance/{active_session_id}',
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def format_time(minutes):
    if minutes is None or minutes == 0: return "N/A"
    try:
        minutes = int(minutes)
    except:
        return str(minutes)
    if minutes <= 0: return "⛔ <b>Expired</b>"
    days = minutes // 1440
    hours = (minutes % 1440) // 60
    mins = minutes % 60
    parts = []
    if days > 0: parts.append(f"{days}d")
    if hours > 0: parts.append(f"{hours}h")
    if mins > 0: parts.append(f"{mins}m")
    return " ".join(parts) if parts else "0m"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    if not is_allowed(chat_id):
        denied_text = (
            "╭━━━[ ❌ ACCESS DENIED ]━━━╮\n"
            "┃ ⚠️ အသုံးပြုခွင့် မရှိသေးပါ       ┃\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
            "💬 **Admin ဆက်သွယ်ရန်:** [👑 @kyawzin114800](t.me/kyawzin114800)"
        )
        bot.reply_to(message, denied_text, parse_mode="Markdown")
        return
    
    welcome_text = (
        "╭━━━[ 👑 KYAW ZIN v2.0 PRO ]━━━╮\n"
        "┃ ⚡ System Status : Online 🟢   ┃\n"
        "┃ 👑 Owner / Admin : KYAW ZIN   ┃\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
        "✨ **COMMANDS MENU:**\n"
        "• 🌐 `/url [URL/ID]` - Session သိမ်းပြီး Voucher ဆက်စစ်ရန်\n"
        "• ⚡ `/testsession [URL] [Voucher]` - တစ်ခါတည်း တိုက်ရိုက်စစ်ရန်\n"
        "• 🔑 `/getsession [URL]` - Session ID သက်သက်ထုတ်ရန်\n"
        "• 📖 `/help` - အကူအညီရယူရန်\n"
        "• 🛑 `/stop` - လုပ်ဆောင်ချက်ရပ်ရန်\n\n"
        "👇 *အောက်ပါ Button များမှလည်း အသုံးပြုနိုင်ပါသည်*"
    )
    
    markup = telebot.types.InlineKeyboardMarkup()
    btn_start = telebot.types.InlineKeyboardButton("🚀 စတင်ရန် (/start)", callback_data="cmd_start")
    btn_help = telebot.types.InlineKeyboardButton("📖 လမ်းညွှန် (/help)", callback_data="cmd_help")
    btn_stop = telebot.types.InlineKeyboardButton("🛑 ရပ်တန့်ရန် (/stop)", callback_data="cmd_stop")
    markup.add(btn_start, btn_help)
    markup.add(btn_stop)

    bot.reply_to(message, welcome_text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['url'])
def url_command(message):
    chat_id = message.chat.id
    if not is_allowed(chat_id): return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        msg = bot.reply_to(message, "⚠️ **Usage:** `/url [Session_URL သို့မဟုတ် Session_ID]`\n\nကျေးဇူးပြု၍ URL (သို့) Session ID ကို ပို့ပေးပါ:", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_url_step)
        return
        
    input_data = parts[1].strip()
    extracted_id = extract_session_id(input_data)
    if not extracted_id:
        bot.reply_to(message, "❌ **ERROR:** မှန်ကန်သော Session ID သို့မဟုတ် URL မဟုတ်ပါ။", parse_mode="Markdown")
        return
        
    user_sessions[chat_id] = input_data
    success_text = (
        "╭━━━[ ✅ SESSION SAVED ]━━━╮\n"
        "┃ 🟢 အောင်မြင်စွာ သိမ်းဆည်းပြီး ┃\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
        "📥 **STEP 2:** ယခု စစ်ဆေးလိုသော **Voucher Code** ကို ဆက်တိုက် ရိုက်ထည့်ပေးပါဗျ။"
    )
    msg = bot.reply_to(message, success_text, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_voucher_step)

@bot.message_handler(commands=['testsession', 'testseesion'])
def testsession_command(message):
    chat_id = message.chat.id
    if not is_allowed(chat_id): return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        bot.reply_to(message, "⚠️ **Usage:** `/testsession [URL သို့မဟုတ် ID] [Voucher_Code]`", parse_mode="Markdown")
        return
        
    url_input = parts[1].strip()
    voucher = parts[2].strip()
    
    status_msg = bot.reply_to(message, "⚡ `[████░░░░░░] Connecting to Server...`", parse_mode="Markdown")
    time.sleep(0.3)

    session_id = extract_session_id(url_input)
    if not session_id:
        bot.edit_message_text("❌ **ERROR:** Session ID ရှာမတွေ့ပါ။", chat_id=chat_id, message_id=status_msg.message_id, parse_mode="Markdown")
        return

    active_session_id, error = login_voucher(session_id, voucher)
    if not active_session_id:
        fail_res = (
            "╭━━━[ ❌ CHECK FAILED ]━━━╮\n"
            f"┃ 🎫 Voucher : `{voucher}`   ┃\n"
            f"┃ 📊 Status  : ❌ Invalid    ┃\n"
            f"┃ 💬 Reason  : `{str(error)[:40]}` ┃\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯"
        )
        bot.edit_message_text(fail_res, chat_id=chat_id, message_id=status_msg.message_id, parse_mode="Markdown")
        return

    balance_data = get_balance(active_session_id)
    tg_msg = (
        "╭━━━[ 💎 VOUCHER DETAILS ]━━━╮\n"
        f"┃ 🎫 Code   : `{voucher}`\n"
    )

    if balance_data and 'result' in balance_data:
        result = balance_data['result']
        tg_msg += f"┃ 💻 MAC    : `{result.get('mac', 'N/A')}`\n"
        tg_msg += f"┃ 📋 Plan   : `{result.get('profileName', 'Unknown')}`\n"
        total_minutes = result.get('totalMinutes', 0)
        tg_msg += f"┃ 📦 Total  : `{format_time(total_minutes)}`\n"
        remaining = result.get('remainingMinutes', 0)
        tg_msg += f"┃ ⏱️ Remain : `{format_time(remaining)}`\n"
        status = result.get('status', 'Unknown')
        if status == 1 or status == 'active':
            tg_msg += f"┃ 📊 Status : ✅ ACTIVE\n"
        else:
            tg_msg += f"┃ 📊 Status : ❌ EXPIRED\n"
    else:
        tg_msg += f"┃ 📊 Status : ⚠️ Partial Data\n"
        
    tg_msg += (
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯\n"
        "👤 **By:** KYAW ZIN | 💬 @kyawzin114800"
    )
    bot.edit_message_text(tg_msg, chat_id=chat_id, message_id=status_msg.message_id, parse_mode="Markdown")

@bot.message_handler(commands=['getsession', 'getseassion'])
def getsession_command(message):
    chat_id = message.chat.id
    if not is_allowed(chat_id): return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ **Usage:** `/getsession [WiFi_Session_URL]`", parse_mode="Markdown")
        return
    url_input = parts[1].strip()
    session_id = extract_session_id(url_input)

    if session_id:
        result_text = (
            "╭━━━[ 🔑 SESSION ID ]━━━╮\n"
            f"┃ `{session_id}`\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
            "📋 *(ကော်ပီကူးရန် အထက်ပါ ID ပေါ်ကို တစ်ချက်နှိပ်ပါ)*"
        )
        bot.reply_to(message, result_text, parse_mode="Markdown")
    else:
        bot.reply_to(message, "❌ **ERROR:** ပေးထားသော URL ထဲမှ Session ID ရှာမတွေ့ပါ။", parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def send_help(message):
    if not is_allowed(message.chat.id): return
    help_text = (
        "╭━━━[ 📖 GUIDE & HELP ]━━━╮\n"
        "┃ 🌐 `/url [URL]` - ဆက်စစ်ရန်   ┃\n"
        "┃ ⚡ `/testsession` - တိုက်စစ်ရန် ┃\n"
        "┃ 🔑 `/getsession` - ID ထုတ်ရန် ┃\n"
        "┃ 🛑 `/stop` - ရပ်တန့်ရန်       ┃\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
        "💬 **Admin:** [👑 @kyawzin114800](t.me/kyawzin114800)"
    )
    bot.reply_to(message, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['addid'])
def add_id_command(message):
    if not is_owner(message.chat.id): return
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ **Usage:** `/addid [Telegram_ID]`", parse_mode="Markdown")
        return
    try:
        new_id = int(parts[1])
        if new_id not in ALLOWED_USERS:
            ALLOWED_USERS.append(new_id)
            save_allowed_users(ALLOWED_USERS)
            bot.reply_to(message, f"✅ Successfully added user ID `{new_id}`.", parse_mode="Markdown")
        else:
            bot.reply_to(message, "⚠️ ID already exists.", parse_mode="Markdown")
    except ValueError:
        bot.reply_to(message, "❌ Invalid ID format.", parse_mode="Markdown")

@bot.message_handler(commands=['delid'])
def del_id_command(message):
    if not is_owner(message.chat.id): return
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ **Usage:** `/delid [Telegram_ID]`", parse_mode="Markdown")
        return
    try:
        target_id = int(parts[1])
        if target_id in ALLOWED_USERS:
            ALLOWED_USERS.remove(target_id)
            save_allowed_users(ALLOWED_USERS)
            bot.reply_to(message, f"✅ Successfully removed user ID `{target_id}`.", parse_mode="Markdown")
        else:
            bot.reply_to(message, "⚠️ ID not found.", parse_mode="Markdown")
    except ValueError:
        bot.reply_to(message, "❌ Invalid ID format.", parse_mode="Markdown")

@bot.message_handler(commands=['listid'])
def list_id_command(message):
    if not is_owner(message.chat.id): return
    if not ALLOWED_USERS:
        bot.reply_to(message, "📋 ခွင့်ပြုထားသော ID မရှိသေးပါ။", parse_mode="Markdown")
        return
    text = "📋 **Allowed Users List:**\n"
    for uid in ALLOWED_USERS:
        text += f"• `{uid}`\n"
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if not is_allowed(call.message.chat.id):
        bot.answer_callback_query(call.id, "❌ အသုံးပြုခွင့် မရှိပါ။", show_alert=True)
        return
    if call.data == "cmd_start":
        bot.answer_callback_query(call.id, "🚀 Control Panel...")
        fake_message = call.message
        fake_message.text = "/start"
        send_welcome(fake_message)
    elif call.data == "cmd_help":
        bot.answer_callback_query(call.id, "📖 Help Menu...")
        fake_message = call.message
        fake_message.text = "/help"
        send_help(fake_message)
    elif call.data == "cmd_stop":
        bot.answer_callback_query(call.id, "🛑 ရပ်တန့်လိုက်ပါပြီ။")
        fake_message = call.message
        fake_message.text = "/stop"
        handle_stop_command(fake_message)

@bot.message_handler(commands=['stop'])
def handle_stop_command(message):
    chat_id = message.chat.id
    if chat_id in user_sessions: del user_sessions[chat_id]
    stop_text = (
        "╭━━━[ 🛑 TERMINATED ]━━━╮\n"
        "┃ လုပ်ဆောင်ချက် ရပ်ပြီးပါပြီ ┃\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━╯"
    )
    markup = telebot.types.InlineKeyboardMarkup()
    btn_start = telebot.types.InlineKeyboardButton("🚀 ပြန်လည်စတင်ရန် (/start)", callback_data="cmd_start")
    markup.add(btn_start)
    bot.reply_to(message, stop_text, parse_mode="Markdown", reply_markup=markup)

def process_url_step(message):
    chat_id = message.chat.id
    if not is_allowed(chat_id): return
    text_input = message.text.strip()
    if text_input.startswith('/'): return
    extracted_id = extract_session_id(text_input)
    if not extracted_id:
        msg = bot.reply_to(message, "⚠️ **ERROR:** မှန်ကန်သော Session URL သို့မဟုတ် Session ID ကို ပို့ပေးပါ။", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_url_step)
        return
    user_sessions[chat_id] = text_input
    success_text = (
        "╭━━━[ ✅ ACCEPTED ]━━━╮\n"
        "┃ 🟢 Session လက်ခံရရှိပါပြီ ┃\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
        "📥 **STEP 2:** ယခု စစ်ဆေးလိုသော **Voucher Code** ကို ထည့်ပါ။"
    )
    msg = bot.reply_to(message, success_text, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_voucher_step)

def process_voucher_step(message):
    chat_id = message.chat.id
    if not is_allowed(chat_id): return
    voucher = message.text.strip()
    
    # Command တွေကို စစ်ထုတ်ခြင်း
    if voucher.startswith('/'):
        # Command ဆိုရင် ဘာမှမလုပ်ဘဲ ပြန်ထွက်
        return
        
    session_input = user_sessions.get(chat_id)
    if not session_input:
        bot.reply_to(message, "⚠️ **Session Expired!** `/url` ကို ပြန်သုံးပါ။", parse_mode="Markdown")
        return

    status_msg = bot.reply_to(message, "⚡ `[████░░░░░░] Connecting to Server...`", parse_mode="Markdown")
    time.sleep(0.3)

    session_id = extract_session_id(session_input)
    if not session_id:
        bot.edit_message_text("❌ **ERROR:** Session ID ရှာမတွေ့ပါ။", chat_id=chat_id, message_id=status_msg.message_id, parse_mode="Markdown")
        msg = bot.send_message(chat_id, "🔄 မှန်ကန်သော Session URL / ID အသစ် ပြန်ပို့ပါ:", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_url_step)
        return

    active_session_id, error = login_voucher(session_id, voucher)
    
    if not active_session_id:
        fail_res = (
            "╭━━━[ ❌ CHECK FAILED ]━━━╮\n"
            f"┃ 🎫 Voucher : `{voucher}`   ┃\n"
            f"┃ 📊 Status  : ❌ Invalid    ┃\n"
            f"┃ 💬 Reason  : `{str(error)[:50]}` ┃\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
            "🔄 *နောက်ထပ် Voucher Code ကို ဆက်တိုက်ပို့နိုင်ပါတယ်။*"
        )
        bot.edit_message_text(fail_res, chat_id=chat_id, message_id=status_msg.message_id, parse_mode="Markdown")
        # အသစ်တစ်ခုအတွက် ပြန်စောင့်မည်
        bot.register_next_step_handler(message, process_voucher_step)
        return

    balance_data = get_balance(active_session_id)
    
    tg_msg = (
        "╭━━━[ 💎 VOUCHER DETAILS ]━━━╮\n"
        f"┃ 🎫 Code   : `{voucher}`\n"
    )

    if balance_data and 'result' in balance_data:
        result = balance_data['result']
        tg_msg += f"┃ 💻 MAC    : `{result.get('mac', 'N/A')}`\n"
        tg_msg += f"┃ 📋 Plan   : `{result.get('profileName', 'Unknown')}`\n"
        total_minutes = result.get('totalMinutes', 0)
        tg_msg += f"┃ 📦 Total  : `{format_time(total_minutes)}`\n"
        remaining = result.get('remainingMinutes', 0)
        tg_msg += f"┃ ⏱️ Remain : `{format_time(remaining)}`\n"
        status = result.get('status', 'Unknown')
        if status == 1 or status == 'active':
            tg_msg += f"┃ 📊 Status : ✅ ACTIVE\n"
        else:
            tg_msg += f"┃ 📊 Status : ❌ EXPIRED\n"
    elif balance_data and 'error' in balance_data:
        tg_msg += f"┃ 📊 Status : ⚠️ {balance_data['error'][:30]}\n"
    else:
        tg_msg += f"┃ 📊 Status : ⚠️ Partial Data\n"
        
    tg_msg += (
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯\n"
        "👤 **By:** KYAW ZIN | 💬 @kyawzin114800\n\n"
        "🔄 *နောက်ထပ် Voucher Code ကို ဆက်လက် ပို့ပေးနိုင်ပါတယ်!*"
    )
    
    bot.edit_message_text(tg_msg, chat_id=chat_id, message_id=status_msg.message_id, parse_mode="Markdown")
    # နောက်ထပ် Voucher တစ်ခုအတွက် ပြန်စောင့်မည်
    bot.register_next_step_handler(message, process_voucher_step)

if __name__ == "__main__":
    # Flask server ကို separate thread မှာ run ခြင်း
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    print("🚀 KYAW ZIN v2.0 PRO Telegram Bot & Flask Server are running successfully...")
    print(f"✅ Allowed Users: {ALLOWED_USERS}")
    print(f"👑 Owner ID: {OWNER_ID}")
    
    # Webhook ကိုဖယ်ရှားပြီး Polling ဖြင့် run ခြင်း
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.infinity_polling(none_stop=True, interval=0, timeout=20)
    except Exception as e:
        print(f"Bot Error: {e}")
        time.sleep(5)
        # Restart polling if error occurs
        bot.infinity_polling(none_stop=True, interval=0, timeout=20)
