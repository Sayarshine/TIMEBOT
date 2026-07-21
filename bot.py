import re
import requests
import base64
import json
import os
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

# User တစ်ယောက်ချင်းစီရဲ့ Session URL ကို ယာယီမှတ်ထားရန် memory dict
user_sessions = {}

# ---- Flask Server for UptimeRobot Keep-Alive ----
app = Flask('')

@app.route('/')
def home():
    return "🤖 Telegram Bot is active and running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.start()
# --------------------------------------------------

def is_admin(chat_id):
    return chat_id in ADMIN_IDS

def get_session_id(session_url):
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-US,en;q=0.9',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36',
    }
    try:
        response = requests.get(session_url, headers=headers, timeout=10)
        session_id = re.search(r"[?&]sessionId=([a-zA-Z0-9]+)", response.url).group(1)
        return session_id
    except:
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
            token_match = re.search('token=(.*?)&', res_text)
            if token_match:
                return token_match.group(1), None
            else:
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
    minutes = int(minutes)
    if minutes <= 0: return "⛔ Expired"
    days = minutes // 1440
    hours = (minutes % 1440) // 60
    mins = minutes % 60
    parts = []
    if days > 0: parts.append(f"{days}d")
    if hours > 0: parts.append(f"{hours}h")
    if mins > 0: parts.append(f"{mins}m")
    return " ".join(parts) if parts else "0m"

# ---- Bot Handlers ----

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if not is_admin(message.chat.id):
        bot.reply_to(message, "❌ သင်သည် Admin မဟုတ်သဖြင့် ဤ Bot ကို သုံးခွင့်မရှိပါ။")
        return
    
    welcome_text = (
        "👋 *Voucher Time Checker Bot မှ ကြိုဆိုပါတယ်ဗျာ*\n\n"
        "အဆင့် (၁) - ကျေးဇူးပြု၍ မိမိရဲ့ *WiFi Session URL* ကို ပို့ပေးပါဦး။\n\n"
        "💡 အသုံးပြုပုံလမ်းညွှန်ကို သိလိုပါက `/help` ကို နှိပ်ပါ။\n"
        "🛑 လက်ရှိလုပ်ဆောင်ချက်ကို ရပ်တန့်လိုပါက `/stop` ကို နှိပ်ပါ။"
    )
    msg = bot.reply_to(message, welcome_text, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_url_step)

@bot.message_handler(commands=['help'])
def send_help(message):
    if not is_admin(message.chat.id):
        bot.reply_to(message, "❌ သင်သည် Admin မဟုတ်ပါ။")
        return

    help_text = (
        "📖 *Bot အသုံးပြုနည်း လမ်းညွှန်ချက်*\n"
        "───────────────────\n"
        "ဒီ Bot ကို အဆင့် (၂) ဆင့်နဲ့ လွယ်ကူစွာ အသုံးပြုနိုင်ပါတယ်-\n\n"
        "1️⃣ *အဆင့် (၁) - URL ပို့ခြင်း*\n"
        "   • ပထမဆုံး `/start` ကို နှိပ်ပါ။\n"
        "   • Bot က တောင်းဆိုတဲ့အခါ မိမိရဲ့ WiFi Captive Portal ရဲ့ **Session URL** (Link) ကို ပို့ပေးပါ။\n\n"
        "2️⃣ *အဆင့် (၂) - Voucher စစ်ခြင်း*\n"
        "   • URL အောင်မြင်စွာ ရရှိပြီးနောက် စစ်ဆေးလိုသော **Voucher Code** ကို ပို့ပေးပါ။\n"
        "   • Bot မှ Voucher ရဲ့ သက်တမ်းနှင့် အချက်အလက်များကို ပြသပေးပါလိမ့်မည်။\n"
        "   • ၎င်းနောက် URL ထပ်ပို့စရာမလိုဘဲ အခြား Voucher Code များကို **ဆက်တိုက်** ပို့ပြီး စစ်ဆေးနိုင်ပါသည်။\n\n"
        "📌 *သတိပြုရန်*\n"
        "   • URL အသစ်ပြောင်းလဲလိုပါက `/start` ကို ပြန်နှိပ်ပြီး အစမှ ပြန်လုပ်ပါ။\n"
        "   • ဘာပဲလုပ်နေနေ လုပ်လက်စကို ရပ်ချင်ရင် `/stop` ကို ရိုက်ထည့်နိုင်ပါတယ်။\n"
        "───────────────────\n"
        "⚙️ *ရနိုင်သော Commands များ-*\n"
        "• `/start` - Bot ကို စတင်ရန်/URL အသစ်ထည့်ရန်\n"
        "• `/help` - အသုံးပြုပုံလမ်းညွှန် ကြည့်ရန်\n"
        "• `/stop` - လုပ်ဆောင်ချက်အားလုံးကို ရပ်တန့်ရန်"
    )
    bot.reply_to(message, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['stop'])
def handle_stop_command(message):
    chat_id = message.chat.id
    if chat_id in user_sessions:
        del user_sessions[chat_id]
    bot.reply_to(message, "🛑 *လုပ်ဆောင်ချက်များကို ရပ်တန့်လိုက်ပါပြီ။*\n\nအသစ်ပြန်စလိုပါက `/start` ကို နှိပ်ပါ။", parse_mode="Markdown")

def process_url_step(message):
    chat_id = message.chat.id
    url = message.text.strip()
    
    if url.startswith('/start'):
        send_welcome(message)
        return
    elif url.startswith('/help'):
        send_help(message)
        msg = bot.send_message(chat_id, "⏳ ကျေးဇူးပြု၍ သင်၏ *WiFi Session URL* ကို ပို့ပေးပါရန်။", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_url_step)
        return
    elif url.startswith('/stop'):
        handle_stop_command(message)
        return

    if not url.startswith('http'):
        msg = bot.reply_to(message, "⚠️ URL ပုံစံ မှားယွင်းနေပုံရပါတယ်။ ကျေးဇူးပြု၍ `http://` သို့မဟုတ် `https://` ပါဝင်သော URL အမှန်ကို ပြန်ပို့ပေးပါရန်။\n(ရပ်တန့်လိုပါက `/stop` ကို ရိုက်ပါ)")
        bot.register_next_step_handler(msg, process_url_step)
        return

    user_sessions[chat_id] = url
    
    msg = bot.reply_to(message, "✅ URL ရပါပြီ။\n\nအဆင့် (၂) - စစ်ဆေးလိုသော *Voucher Code* ကို ရိုက်ထည့်ပေးပါဗျာ။\n(ရပ်တန့်လိုပါက `/stop` ကို ရိုက်ပါ)", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_voucher_step)

def process_voucher_step(message):
    chat_id = message.chat.id
    voucher = message.text.strip()

    if voucher.startswith('/start'):
        send_welcome(message)
        return
    elif voucher.startswith('/help'):
        send_help(message)
        msg = bot.send_message(chat_id, "🔄 စစ်ဆေးလိုသော *Voucher Code* ကို ဆက်လက်ပို့ပေးနိုင်ပါတယ်ဗျာ။", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_voucher_step)
        return
    elif voucher.startswith('/stop'):
        handle_stop_command(message)
        return

    session_url = user_sessions.get(chat_id)
    if not session_url:
        bot.reply_to(message, "⚠️ Session သက်တမ်း ကုန်ဆုံးသွားပါပြီ။ `/start` ကို ပြန်နှိပ်ပြီး အစကပြန်လုပ်ပေးပါ။", parse_mode="Markdown")
        return

    status_msg = bot.reply_to(message, "⏳ ဆာဗာမှ အချက်အလက်များကို စစ်ဆေးနေပါသည်...")

    # Step 1: Get Session ID
    session_id = get_session_id(session_url)
    if not session_id:
        bot.edit_message_text("❌ Session ID မရနိုင်ပါ (URL မှားယွင်းနေနိုင်ပါသည်)။ URL ပြန်ပို့ပေးရန် `/start` ကို ပြန်နှိပ်ပါ။", chat_id=chat_id, message_id=status_msg.message_id)
        return

    # Step 2: Login Voucher
    active_session_id, error = login_voucher(session_id, voucher)
    if not active_session_id:
        tg_res = f"📊 *VOUCHER RESULT*\n\n🎫 *Voucher:* `{voucher}`\n📊 *Status:* ❌ Invalid သို့မဟုတ် Expired ဖြစ်နေပါသည်။\n\n🔄 နောက်ထပ်စစ်ချင်သော *Voucher Code* ကို ထပ်မံ ပို့ပေးနိုင်ပါတယ်ဗျာ။\n(ရပ်တန့်လိုပါက `/stop` ကို ရိုက်ပါ)"
        msg = bot.edit_message_text(tg_res, chat_id=chat_id, message_id=status_msg.message_id, parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_voucher_step)
        return

    # Step 3: Get Balance
    balance_data = get_balance(active_session_id)
    
    # Step 4: Format Result
    tg_msg = f"📊 *VOUCHER DETAILS*\n"
    tg_msg += f"──────────────────\n"
    tg_msg += f"🎫 *Voucher:* `{voucher}`\n"

    if balance_data and 'result' in balance_data:
        result = balance_data['result']
        tg_msg += f"💻 *MAC:* `{result.get('mac', 'N/A')}`\n"
        tg_msg += f"📋 *Plan:* {result.get('profileName', 'Unknown')}\n"
        
        total_minutes = result.get('totalMinutes', 0)
        tg_msg += f"📦 *Total Time:* {format_time(total_minutes)}\n"
        
        remaining = result.get('remainingMinutes', 0)
        tg_msg += f"⏱️ *Remaining:* {format_time(remaining)}\n"
        
        status = result.get('status', 'Unknown')
        if status == 1 or status == 'active':
            tg_msg += f"📊 *Status:* ✅ Active\n"
        else:
            tg_msg += f"📊 *Status:* ❌ Inactive / Expired\n"
    else:
        tg_msg += f"📊 *Status:* ❌ အချက်အလက် ဆွဲမရပါ\n"
        
    tg_msg += f"──────────────────\n\n"
    tg_msg += f"🔄 နောက်ထပ်စစ်ချင်သော *Voucher Code* ကို ထပ်မံ ပို့ပေးနိုင်ပါတယ်ဗျာ။\n(ရပ်တန့်လိုပါက `/stop` ကို ရိုက်ပါ)"
    
    msg = bot.edit_message_text(tg_msg, chat_id=chat_id, message_id=status_msg.message_id, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_voucher_step)

if __name__ == "__main__":
    print("🚀 Starting Keep-Alive Flask Server...")
    keep_alive()
    print("🚀 Telegram Bot is running...")
    bot.infinity_polling()
