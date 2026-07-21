import re
import requests
import base64
import json
import os
import time
import threading
from flask import Flask
import telebot

CONFIG_FILE = "config_synx.json"

# ---- Telegram Configuration ----
BOT_TOKEN = "8917211694:AAHxHW0_1nDvLFiRMpBDYG6oahkOi9Fusa8"
ADMIN_IDS = [6779617599, 8691909482]
# --------------------------------

bot = telebot.TeleBot(BOT_TOKEN)

# Clear any active webhooks to prevent 409 Conflict error
try:
    bot.remove_webhook()
    print("🗑️ Existing webhooks cleared successfully.")
except Exception as e:
    print(f"⚠️ Webhook remove warning: {e}")

# ---- Flask Server for UptimeRobot Keep-Alive ----
app = Flask('')

@app.route('/')
def home():
    return "🤖 KYAW ZIN Telegram Bot is active and running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.start()
# --------------------------------------------------

# User တစ်ယောက်ချင်းစီရဲ့ Session URL ကို ယာယီမှတ်ထားရန် memory dict
user_sessions = {}

def is_admin(chat_id):
    return chat_id in ADMIN_IDS

def get_session_id(session_url):
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'accept-language': 'en-US,en;q=0.9',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36',
    }
    try:
        response = requests.get(session_url, headers=headers, timeout=10, allow_redirects=True)
        match = re.search(r"[?&]sessionId=([a-zA-Z0-9_-]+)", response.url)
        if match: return match.group(1)
        
        match_orig = re.search(r"[?&]sessionId=([a-zA-Z0-9_-]+)", session_url)
        if match_orig: return match_orig.group(1)
            
        match_text = re.search(r"[?&]sessionId=([a-zA-Z0-9_-]+)", response.text)
        if match_text: return match_text.group(1)
            
        return None
    except Exception as e:
        print(f"Error getting session ID: {e}")
        return None

def login_voucher(session_id, voucher):
    data = {"accessCode": voucher, "sessionId": session_id, "apiVersion": 2}
    post_url = base64.b64decode(b'aHR0cHM6Ly9wb3J0YWwtYXMucnVpamllbmV0d29ya3MuY29tL2FwaS9hdXRoL3ZvdWNoZXIvP2xhbmc9ZW5fVVM=').decode()
    headers = {
        "content-type": "application/json",
        "user-agent": 'Mozilla/5.0 (Linux; Android 12; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/139.0.0.0',
    }
    try:
        with requests.post(post_url, json=data, headers=headers, timeout=10) as response:
            res_text = response.text
            token_match = re.search(r'token=(.*?)&', res_text)
            if token_match:
                return token_match.group(1), None
            else:
                try:
                    res_json = response.json()
                    if 'result' in res_json and isinstance(res_json['result'], dict):
                        token = res_json['result'].get('token') or res_json['result'].get('sessionId')
                        if token: return token, None
                except:
                    pass
                return None, res_text
    except Exception as Error:
        return None, str(Error)

def get_balance(active_session_id):
    headers = {
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
    }
    try:
        response = requests.get(
            f'https://portal-as.ruijienetworks.com/api/auth/balance/getBalance/{active_session_id}',
            headers=headers,
            timeout=10
        )
        return response.json()
    except:
        return None

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
    if not is_admin(message.chat.id):
        bot.reply_to(message, "❌ <b>ACCESS DENIED:</b> သင်သည် System Admin မဟုတ်ပါ။")
        return
    
    welcome_text = (
        "👑 <b>KYAW ZIN v2.0 PRO - CONTROL PANEL</b> 👑\n"
        "──────────────────────────────\n"
        "⚡ <b>Owner:</b> <code>KYAW ZIN</code>\n"
        "📱 <b>Telegram:</b> <code>@kyawzin114800</code>\n"
        "──────────────────────────────\n\n"
        "📥 <b>STEP 1:</b> ကျေးဇူးပြု၍ မိမိရဲ့ <b>WiFi Session URL</b> (သို့မဟုတ် Portal Link) ကို ပို့ပေးပါဗျ။\n\n"
        "💡 <i>အကူအညီလိုပါက /help ကိုနှိပ်ပါ။</i>\n"
        "🛑 <i>လုပ်ဆောင်ချက်ရပ်ရန် /stop ကိုနှိပ်ပါ။</i>"
    )
    
    markup = telebot.types.InlineKeyboardMarkup()
    btn_start = telebot.types.InlineKeyboardButton("🚀 စတင်ရန် (/start)", callback_data="cmd_start")
    btn_help = telebot.types.InlineKeyboardButton("📖 လမ်းညွှန် (/help)", callback_data="cmd_help")
    btn_stop = telebot.types.InlineKeyboardButton("🛑 ရပ်တန့်ရန် (/stop)", callback_data="cmd_stop")
    markup.add(btn_start, btn_help)
    markup.add(btn_stop)

    msg = bot.reply_to(message, welcome_text, parse_mode="HTML", reply_markup=markup)
    bot.register_next_step_handler(msg, process_url_step)

@bot.message_handler(commands=['help'])
def send_help(message):
    if not is_admin(message.chat.id):
        bot.reply_to(message, "❌ <b>ACCESS DENIED</b>")
        return

    help_text = (
        "📖 <b>KYAW ZIN BOT - SYSTEM GUIDE</b> 📖\n"
        "══════════════════════════════\n"
        "ဒီ Bot ကို အဆင့် (၂) ဆင့်နဲ့ အလွယ်ဆုံး သုံးနိုင်ပါတယ်-\n\n"
        "1️⃣ <b>STEP 1 (URL ပို့ရန်):</b>\n"
        "   • `/start` ကိုနှိပ်ပြီး WiFi Captive Portal ရဲ့ <b>URL</b> ကို ပို့ပါ။\n\n"
        "2️⃣ <b>STEP 2 (Voucher စစ်ရန်):</b>\n"
        "   • URL အောင်မြင်သွားရင် **Voucher Code** တွေကို ဆက်တိုက်ပို့ပြီး စစ်ဆေးနိုင်ပါတယ်။\n\n"
        "⚙️ <b>QUICK COMMANDS:</b>\n"
        "• /start - Bot ကို အစကနေစရန်\n"
        "• /help - လမ်းညွှန်ကြည့်ရန်\n"
        "• /stop - အလုပ်ရပ်ရန်\n"
        "══════════════════════════════"
    )
    
    markup = telebot.types.InlineKeyboardMarkup()
    btn_start = telebot.types.InlineKeyboardButton("🚀 စတင်ရန် (/start)", callback_data="cmd_start")
    btn_stop = telebot.types.InlineKeyboardButton("🛑 ရပ်တန့်ရန် (/stop)", callback_data="cmd_stop")
    markup.add(btn_start, btn_stop)

    bot.reply_to(message, help_text, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if not is_admin(call.message.chat.id):
        bot.answer_callback_query(call.id, "❌ Admin သာလျှင် သုံးခွင့်ရှိသည်။")
        return

    if call.data == "cmd_start":
        bot.answer_callback_query(call.id, "🚀 Control Panel သို့ ရောက်ရှိပါပြီ...")
        fake_message = call.message
        fake_message.text = "/start"
        send_welcome(fake_message)
    elif call.data == "cmd_help":
        bot.answer_callback_query(call.id, "📖 Help Menu ကို ဖွင့်နေပါပြီ...")
        fake_message = call.message
        fake_message.text = "/help"
        send_help(fake_message)
    elif call.data == "cmd_stop":
        bot.answer_callback_query(call.id, "🛑 စနစ်ကို ရပ်တန့်လိုက်ပါပြီ။")
        fake_message = call.message
        fake_message.text = "/stop"
        handle_stop_command(fake_message)

@bot.message_handler(commands=['stop'])
def handle_stop_command(message):
    chat_id = message.chat.id
    if chat_id in user_sessions:
        del user_sessions[chat_id]
    
    stop_text = (
        "🛑 <b>SYSTEM TERMINATED</b>\n"
        "──────────────────────────────\n"
        "လုပ်ဆောင်ချက်အားလုံးကို အောင်မြင်စွာ ရပ်တန့်လိုက်ပါပြီ။\n"
        "အသစ်ပြန်စလိုပါက အောက်ပါခလုတ်ကို နှိပ်ပါ 👇"
    )
    markup = telebot.types.InlineKeyboardMarkup()
    btn_start = telebot.types.InlineKeyboardButton("🚀 ပြန်လည်စတင်ရန် (/start)", callback_data="cmd_start")
    # Fixed syntax for button creation below:
    markup = telebot.types.InlineKeyboardMarkup()
    btn_start = telebot.types.InlineKeyboardButton("🚀 ပြန်လည်စတင်ရန် (/start)", callback_data="cmd_start")
    markup.add(btn_start)
    
    bot.reply_to(message, stop_text, parse_mode="HTML", reply_markup=markup)

def process_url_step(message):
    chat_id = message.chat.id
    url = message.text.strip()
    
    if url.startswith('/start'):
        send_welcome(message)
        return
    elif url.startswith('/help'):
        send_help(message)
        return
    elif url.startswith('/stop'):
        handle_stop_command(message)
        return

    if not url.startswith('http'):
        msg = bot.reply_to(message, "⚠️ <b>ERROR:</b> `http://` သို့မဟုတ် `https://` ပါဝင်သော URL အမှန်ကို ပြန်ပို့ပေးပါ။", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_url_step)
        return

    user_sessions[chat_id] = url
    
    success_text = (
        "✅ <b>URL ACCEPTED & SAVED!</b>\n"
        "──────────────────────────────\n"
        "📥 <b>STEP 2:</b> ယခု စစ်ဆေးလိုသော <b>Voucher Code</b> ကို ရိုက်ထည့်ပေးပါဗျ.\n\n"
        "<i>(ဆက်တိုက် ပို့ပြီး စစ်ဆေးနိုင်ပါတယ်)</i>"
    )
    msg = bot.reply_to(message, success_text, parse_mode="HTML")
    bot.register_next_step_handler(msg, process_voucher_step)

def process_voucher_step(message):
    chat_id = message.chat.id
    voucher = message.text.strip()

    if voucher.startswith('/start'):
        send_welcome(message)
        return
    elif voucher.startswith('/help'):
        send_help(message)
        return
    elif voucher.startswith('/stop'):
        handle_stop_command(message)
        return

    session_url = user_sessions.get(chat_id)
    if not session_url:
        bot.reply_to(message, "⚠️ <b>Session Expired!</b> ကျေးဇူးပြု၍ `/start` ကို ပြန်နှိပ်ပါ။", parse_mode="HTML")
        return

    status_msg = bot.reply_to(message, "⚡ <code>[████░░░░░░] Connecting to Server...</code>", parse_mode="HTML")
    time.sleep(0.3)
    try:
        bot.edit_message_text("⚡ <code>[████████░░] Scanning Database & Token...</code>", chat_id=chat_id, message_id=status_msg.message_id, parse_mode="HTML")
    except:
        pass

    session_id = get_session_id(session_url)
    if not session_id:
        try:
            resp = requests.get(session_url, timeout=5, allow_redirects=True)
            m = re.search(r"[?&]sessionId=([a-zA-Z0-9_-]+)", resp.url)
            if m: session_id = m.group(1)
        except:
            pass

    if not session_id:
        bot.edit_message_text("❌ <b>ERROR:</b> Session ID ရှာမတွေ့ပါ။ URL အမှန်ကို ပြန်လည် ပို့ပေးပါရန်。", chat_id=chat_id, message_id=status_msg.message_id, parse_mode="HTML")
        msg = bot.send_message(chat_id, "🔄 ကျေးဇူးပြု၍ မှန်ကန်သော **Session URL** အသစ် ပြန်ပို့ပါ (သို့မဟုတ် `/stop` ဖြင့် ရပ်ပါ)။", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_url_step)
        return

    active_session_id, error = login_voucher(session_id, voucher)
    if not active_session_id:
        fail_res = (
            f"❌ <b>VOUCHER CHECK RESULT</b>\n"
            f"──────────────────────────────\n"
            f"🎫 <b>Voucher:</b> <code>{voucher}</code>\n"
            f"📊 <b>Status:</b> ❌ Invalid / Expired (သို့မဟုတ် သုံးပြီးသား)\n\n"
            f"🔄 <i>နောက်ထပ် Voucher Code ကို ဆက်တိုက်ပို့နိုင်ပါတယ်။</i>"
        )
        msg = bot.edit_message_text(fail_res, chat_id=chat_id, message_id=status_msg.message_id, parse_mode="HTML")
        bot.register_next_step_handler(msg, process_voucher_step)
        return

    balance_data = get_balance(active_session_id)
    
    tg_msg = (
        f"💎 <b>KYAW ZIN - VOUCHER DETAILS</b> 💎\n"
        f"══════════════════════════════\n"
        f"🎫 <b>Voucher Code:</b> <code>{voucher}</code>\n"
    )

    if balance_data and 'result' in balance_data:
        result = balance_data['result']
        tg_msg += f"💻 <b>MAC Address:</b> <code>{result.get('mac', 'N/A')}</code>\n"
        tg_msg += f"📋 <b>Plan Name:</b> <code>{result.get('profileName', 'Unknown')}</code>\n"
        
        total_minutes = result.get('totalMinutes', 0)
        tg_msg += f"📦 <b>Total Time:</b> <code>{format_time(total_minutes)}</code>\n"
        
        remaining = result.get('remainingMinutes', 0)
        tg_msg += f"⏱️ <b>Remaining:</b> <code>{format_time(remaining)}</code>\n"
        
        status = result.get('status', 'Unknown')
        if status == 1 or status == 'active':
            tg_msg += f"📊 <b>Status:</b> ✅ <b>ACTIVE / ONLINE</b>\n"
        else:
            tg_msg += f"📊 <b>Status:</b> ❌ <b>EXPIRED / INACTIVE</b>\n"
    else:
        tg_msg += f"📊 <b>Status:</b> ⚠️ <b>Data fetched partially</b>\n"
        
    tg_msg += (
        f"══════════════════════════════\n"
        f"👤 <b>By:</b> KYAW ZIN (@kyawzin114800)\n\n"
        f"🔄 <i>နောက်ထပ် Voucher Code ကို ဆက်လက် ပို့ပေးနိုင်ပါတယ်!</i>"
    )
    
    msg = bot.edit_message_text(tg_msg, chat_id=chat_id, message_id=status_msg.message_id, parse_mode="HTML")
    bot.register_next_step_handler(msg, process_voucher_step)

if __name__ == "__main__":
    print("🚀 Starting Keep-Alive Flask Server...")
    keep_alive()
    print("🚀 KYAW ZIN v2.0 PRO Telegram Bot is running successfully...")
    bot.infinity_polling()
