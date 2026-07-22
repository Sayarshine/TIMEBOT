import telebot, asyncio, aiohttp, json, base64, random, re, os, string, time, uuid
from telebot.async_telebot import AsyncTeleBot
from aiohttp import web
import cv2
import ddddocr
import numpy as np
from datetime import datetime, timedelta, timezone

BOT_TOKEN = '8739058169:AAHQLlPvsgkRTfpcckZ8CbENrFlflr0GSGE'
GITHUB_TOKEN = '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'
OWNER_ID = "6779617599"
REPO_OWNER = "k4370975-lang"
REPO_NAME = "my-new-bot"
SUCCESS_CODE = asyncio.Queue()
bot = AsyncTeleBot(BOT_TOKEN)
user_data = {}
approve = {}
scan_tasks = {}
success_messages = {}
success_texts = {}
limited_messages = {}
limited_texts = {}
captcha_state = {}
retry_counts = {}
session = None
_connector = None

# ==================== SPEED SETTINGS ====================
CONCURRENCY = 150       
TARGET_SPEED = 2800     
# ========================================================

_voucher_sem = None
_start_time = time.monotonic()

# ==================== FLASK / WEB SERVER ====================
async def handle(request):
    return web.Response(text="Bot is awake and running 24/7!")

async def web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get('PORT', 8099))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port}")
# ============================================================

async def get_file_content(path):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            data = await response.json()
            content = base64.b64decode(data['content']).decode('utf-8')
            return json.loads(content), data['sha']
    return {}, None

async def update_file_content(path, content, sha, message):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Content-Type": "application/json"
    }
    encoded = base64.b64encode(json.dumps(content).encode()).decode()
    payload = {
        "message": message,
        "content": encoded,
        "sha": sha
    }
    async with session.put(url, headers=headers, json=payload) as response:
        return await response.text()

@bot.message_handler(commands=['start'])
async def start(message):
    await bot.reply_to(message, "Bot စတင်ပါပြီ။ /key ဖြင့်စတင်ပါ။")

@bot.message_handler(commands=['key'])
async def handle_key(message):
    global approve
    key = str(message.chat.id)
    auth_list, _ = await get_file_content("auth_list.json")
    if key in auth_list:
        valid = check_key_expiration(auth_list[key])
        if valid:
            approve[message.chat.id] = True
            user_data[message.chat.id] = {}
            await bot.reply_to(
                message,
                " Key မှန်ကန်ပါသည်။ /input ဖြင့် Session URL ထည့်ပါ။"
            )
        else:
            approve[message.chat.id] = False
            await bot.reply_to(
                message,
                " Key Expired ဖြစ်နေပါသည်။"
            )
    else:
        await bot.reply_to(
            message,
            " သင်၏ key ကို registered မလုပ်ရသေးပါ။"
        )

# ==================== OWNER / ADMIN MANAGEMENT FEATURES ====================

@bot.message_handler(commands=['addadmin'])
async def add_admin(message):
    if str(message.chat.id) != OWNER_ID:
        await bot.reply_to(message, "⚠️ ဤ විධාန် (Command) သည် Owner အတွက်သာ သီးသန့်ဖြစ်ပါသည်။")
        return
    try:
        args = message.text.split()
        if len(args) < 2:
            await bot.reply_to(message, "Usage:\n/addadmin <user_id>")
            return
        new_admin_id = args[1]
        admins, sha = await get_file_content("admins.json")
        if not isinstance(admins, dict):
            admins = {"admins": []}
        if "admins" not in admins:
            admins["admins"] = []
            
        if new_admin_id in admins["admins"]:
            await bot.reply_to(message, f"⚠️ User ID {new_admin_id} သည် Admin စာရင်းတွင် ရှိနှင့်ပြီးသား ဖြစ်ပါသည်။")
            return
            
        admins["admins"].append(new_admin_id)
        await update_file_content("admins.json", admins, sha, f"Add admin {new_admin_id}")
        await bot.reply_to(message, f"✅ Successfully added {new_admin_id} as Admin.")
    except Exception as e:
        print(f"Error at addadmin: {e}")
        await bot.reply_to(message, "❌ Admin ထည့်သွင်းရာတွင် အမှားအယွင်းရှိခဲ့ပါသည်။")

@bot.message_handler(commands=['removeadmin'])
async def remove_admin(message):
    if str(message.chat.id) != OWNER_ID:
        await bot.reply_to(message, "⚠️ ဤ විධාန် သည် Owner အတွက်သာ သီးသန့်ဖြစ်ပါသည်။")
        return
    try:
        args = message.text.split()
        if len(args) < 2:
            await bot.reply_to(message, "Usage:\n/removeadmin <user_id>")
            return
        target_id = args[1]
        admins, sha = await get_file_content("admins.json")
        if not admins or "admins" not in admins or target_id not in admins["admins"]:
            await bot.reply_to(message, f"⚠️ User ID {target_id} ကို Admin စာရင်းတွင် မတွေ့ရှိပါ။")
            return
            
        admins["admins"].remove(target_id)
        await update_file_content("admins.json", admins, sha, f"Remove admin {target_id}")
        await bot.reply_to(message, f"✅ Successfully removed {target_id} from Admins.")
    except Exception as e:
        print(f"Error at removeadmin: {e}")

@bot.message_handler(commands=['kick'])
async def kick_user(message):
    is_owner = str(message.chat.id) == OWNER_ID
    if not is_owner:
        try:
            member = await bot.get_chat_member(message.chat.id, message.from_user.id)
            if member.status not in ['administrator', 'creator']:
                await bot.reply_to(message, "⚠️ ဤ Group တွင် Member များကို Kick ထုတ်ရန် Admin ဖြစ်ရန် လိုအပ်ပါသည်။")
                return
        except:
            await bot.reply_to(message, "⚠️ ခွင့်ပြုချက် မရှိပါ။")
            return

    if not message.reply_to_message:
        await bot.reply_to(message, "⚠️ ကျေးဇူးပြု၍ Kick ထုတ်လိုသူ၏ မက်ဆေ့ခ်ျကို Reply လုပ်၍ /kick ဟု အသုံးပြုပါ။")
        return
        
    try:
        target_user = message.reply_to_message.from_user
        if str(target_user.id) == OWNER_ID:
            await bot.reply_to(message, "❌ Owner ကို Kick ထုတ်၍ မရပါ။")
            return
        await bot.ban_chat_member(message.chat.id, target_user.id)
        await bot.unban_chat_member(message.chat.id, target_user.id)
        await bot.reply_to(message, f"✅ Successfully kicked {target_user.first_name} from the group.")
    except Exception as e:
        await bot.reply_to(message, f"❌ Kick ထုတ်၍မရပါ (သို့) Bot တွင် Permission မရှိပါ။ Error: {e}")

@bot.message_handler(commands=['ban'])
async def ban_user(message):
    if str(message.chat.id) != OWNER_ID:
        try:
            member = await bot.get_chat_member(message.chat.id, message.from_user.id)
            if member.status not in ['administrator', 'creator']:
                await bot.reply_to(message, "⚠️ ခွင့်ပြုချက် မရှိပါ။")
                return
        except:
            await bot.reply_to(message, "⚠️ ခွင့်ပြုချက် မရှိပါ။")
            return

    if not message.reply_to_message:
        await bot.reply_to(message, "⚠️ Ban လိုသူ၏ message ကို reply ပေး၍ /ban သုံးပါ။")
        return
    try:
        target_user = message.reply_to_message.from_user
        if str(target_user.id) == OWNER_ID:
            await bot.reply_to(message, "❌ Owner ကို Ban ၍ မရပါ။")
            return
        await bot.ban_chat_member(message.chat.id, target_user.id)
        await bot.reply_to(message, f"🚫 Successfully banned {target_user.first_name}.")
    except Exception as e:
        await bot.reply_to(message, f"❌ Error: {e}")

# ============================================================================

@bot.message_handler(commands=['listkeys'])
async def listkeys(message):
    if str(message.chat.id) != OWNER_ID:
        await bot.reply_to(message, "No Permission")
        return
    try:
        auth_list, _ = await get_file_content("auth_list.json")
        if not auth_list:
            await bot.reply_to(message, "Registered key မရှိသေးပါ။")
            return
        lines = []
        for uid, data in auth_list.items():
            if isinstance(data, dict):
                expires = data.get("expires_at", "unknown")
                plan = data.get("plan", "unknown")
                if expires == "9999-12-31T23:59:59Z":
                    expires_str = "Unlimited"
                else:
                    try:
                        exp_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                        now = datetime.now(timezone.utc)
                        if exp_dt < now:
                            expires_str = "Expired"
                        else:
                            diff = exp_dt - now
                            days = diff.days
                            hours, rem = divmod(diff.seconds, 3600)
                            minutes = rem // 60
                            expires_str = f"{days}d {hours}h {minutes}m left"
                    except:
                        expires_str = expires
            else:
                plan = "old"
                expires_str = str(data)
            lines.append(f"👤 {uid}\n   Plan: {plan}\n   Expires: {expires_str}")
        text = f"📋 Registered Keys ({len(auth_list)})\n\n" + "\n\n".join(lines)
        if len(text) > 4096:
            for i in range(0, len(text), 4096):
                await bot.send_message(message.chat.id, text[i:i+4096])
        else:
            await bot.reply_to(message, text)
    except Exception as e:
        print(f"Error at listkeys {e}")

@bot.message_handler(commands=['delkey'])
async def delkey(message):
    if str(message.chat.id) != OWNER_ID:
        await bot.reply_to(message, "No Permission")
        return
    try:
        args = message.text.split()
        if len(args) < 2:
            await bot.reply_to(message, "Usage:\n/delkey 123456789")
            return
        user_id = args[1]
        auth_list, sha = await get_file_content("auth_list.json")
        if user_id not in auth_list:
            await bot.reply_to(message, f"User ID {user_id} မတွေ့ပါ။")
            return
        del auth_list[user_id]
        await update_file_content(
            "auth_list.json",
            auth_list,
            sha,
            f"Delete key for {user_id}"
        )
        approve.pop(int(user_id), None)
        user_data.pop(int(user_id), None)
        await bot.reply_to(
            message,
            f" Key Deleted\n\nUSER ID : {user_id}"
        )
    except Exception as e:
        print(f"Error at delkey {e}")

@bot.message_handler(commands=['genkey'])
async def genkey(message):
    if str(message.chat.id) != OWNER_ID:
        await bot.reply_to(message, "No Permission")
        return
    try:
        args = message.text.split()
        if len(args) < 3:
            await bot.reply_to(message, "Usage:\n/genkey 1h 123456789")
            return
        plan = args[1]
        user_id = args[2]
        expiry = generate_expiry(plan)
        if not expiry:
            await bot.reply_to(
                message,
                "Plans:\n30m\n1h\n1d\n7d\n1m\n1y\nunlimited"
            )
            return
        auth_list, sha = await get_file_content("auth_list.json")
        auth_list[user_id] = {
            "expires_at": expiry,
            "plan": plan
        }
        await update_file_content(
            "auth_list.json",
            auth_list,
            sha,
            f"Add key for {user_id}"
        )
        await bot.reply_to(
            message,
            f" Key Generated\n\n"
            f"USER ID : {user_id}\n"
            f"PLAN : {plan}\n"
            f"EXPIRES : {expiry}"
        )
    except Exception as e:
        print(f"Error at genkey {e}")

@bot.message_handler(commands=['result'])
async def handle_result(message):
    auth_list, _ = await get_file_content("auth_list.json")
    if str(message.chat.id) in auth_list:
        results, _ = await get_file_content("result.json")
        chat_id_str = str(message.chat.id)
        if chat_id_str in results and results[chat_id_str]:
            codes = "\n".join(results[chat_id_str])
            await bot.reply_to(message, f"✅ Found Codes:\n{codes}")
        else:
            await bot.reply_to(message, "သင့်တွင် ယခင်ကရရှိထားသေး code မရှိသေးပါ။")
    else:
        await bot.reply_to(message, "သင်၏ key ကို registered မပြုလုပ်ရသေးပါ။")

def check_key_expiration(expiration_time):
    try:
        if isinstance(expiration_time, dict):
            expiry = expiration_time.get("expires_at")
            if expiry == "9999-12-31T23:59:59Z":
                return True
            exp_time = datetime.fromisoformat(
                expiry.replace("Z", "+00:00")
            )
            return datetime.now(timezone.utc) < exp_time
        mm, hh, dd, MM, yyyy = map(
            int,
            expiration_time.split('-')
        )
        expiration_dt = datetime(
            year=yyyy,
            month=MM,
            day=dd,
            hour=hh,
            minute=mm,
            second=0,
            tzinfo=timezone.utc
        )
        return datetime.now(timezone.utc) < expiration_dt
    except Exception as e:
        print("Key parse error:", e)
        return False

def generate_expiry(plan):
    now = datetime.now(timezone.utc)
    plans = {
        "30m": timedelta(minutes=30),
        "1h": timedelta(hours=1),
        "1d": timedelta(days=1),
        "7d": timedelta(days=7),
        "1m": timedelta(days=30),
        "1y": timedelta(days=365),
        "unlimited": None
    }
    if plan not in plans:
        return None
    if plan == "unlimited":
        return "9999-12-31T23:59:59Z"
    return (now + plans[plan]).isoformat()

def get_current_time():
    return datetime.now(timezone.utc)

@bot.message_handler(commands=['recheck'])
async def recheck(message):
    chat_id = message.chat.id
    if not approve.get(chat_id, False):
        await bot.reply_to(message, "/recheck ကိုအသုံးမပြုမီ /key ကိုအရင်ပြုလုပ်ပေးပါ။")
        return
    auth_list, _ = await get_file_content("auth_list.json")
    if str(message.chat.id) in auth_list:
        results, sha = await get_file_content("result.json")
        chat_id_str = str(message.chat.id)
        if chat_id_str in results and results[chat_id_str]:
            if message.chat.id not in user_data:
                await bot.reply_to(message, "/scan ကိုအသုံးမပြုမီ /key ကိုအရင်ပြုလုပ်ပေးပါ။")
                return
            if "session_url" not in user_data[message.chat.id]:
                await bot.reply_to(message, "/recheck ကိုအသုံးမပြုမီ /input ဖြင့် Session URL ကိုအရင်ထည့်သွင်းပေးရပါမည်။")
                return
            codes = results[chat_id_str]
            await bot.reply_to(message, f"Success Code များအား ပြန်လည်စစ်ဆေးနေပါသည်။")
            session_url_recheck = user_data[message.chat.id]["session_url"]
            recheck_list = []
            for code in codes:
                recode = await perform_check(
                    session_url_recheck,
                    code,
                    chat_id,
                    scan_id=None,
                    recheck=True,
                    message=message
                )
                if recode:
                    recheck_list.append(recode)
            to_show = "\n".join(recheck_list) if recheck_list else "Code များအားလုံးစစ်ဆေးပြီးပါပြီ မည်သည့် success code မျှရှာမတွေ့ပါ။"
            await bot.reply_to(message, f"✅ Rechcked Codes:\n\n{to_show}")
            await save_rechecked_codes(chat_id_str, recheck_list, sha)
        else:
            await bot.reply_to(message, "သင့်တွင် success code တစ်ခုမျှမရှိသေးပါ။")
    else:
        await bot.reply_to(message, "သင်၏ key ကို registered မလုပ်ရသေးပါ။")

async def save_rechecked_codes(chat_id_str, recheck_list, sha):
    results, _ = await get_file_content("result.json")
    results[chat_id_str] = recheck_list
    await update_file_content("result.json", results, sha, f"Update after recheck for {chat_id_str}")

async def check_session_url(session_url):
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-US,en;q=0.9',
        'priority': 'u=0, i',
        'referer': session_url,
        'sec-ch-ua': '"Chromium";v="148", "Microsoft Edge";v="148", "Not/A)Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Android"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0',
        'cookie': 'sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%2219e0ddbd9f2152-0df941f2efc6b08-4c657b58-1327104-19e0ddbd9f3a60%22%2C%22first_id%22%3A%22%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E8%87%AA%E7%84%B6%E6%90%9C%E7%B4%A2%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC%22%2C%22%24latest_referrer%22%3A%22https%3A%2F%2Fgemini.google.com%2F%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTllMGRkYmQ5ZjIxNTItMGRmOTQxZjJlZmM2YjA4LTRjNjU3YjU4LTEzMjcxMDQtMTllMGRkYmQ5ZjNhNjAifQ%3D%3D%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%22%2C%22value%22%3A%22%22%7D%2C%22%24device_id%22%3A%2219e0ddbd9f2152-0df941f2efc6b08-4c657b58-1327104-19e0ddbd9f3a60%22%7D'
    }
    try:
        async with session.get(session_url, allow_redirects=True, headers=headers) as response:
            text_ = str(response.url)
            print(text_)
            if "sessionId" in text_:
                return True
            else:
                return False
    except:
        return False

@bot.message_handler(commands=['input'])
async def handle_input(message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await bot.reply_to(
            message,
            "Usage:\n\n/input your_session_url"
        )
        return
    url = args[1]
    if message.chat.id in user_data:
        await bot.reply_to(message, "Session URL အားစစ်ဆေးနေပါသည်။")
        if await check_session_url(session_url=url):
            user_data[message.chat.id]['session_url'] = url
            await bot.reply_to(message, "Session URL အားသိမ်းဆည်းပြီးပါပြီ။ /scan 6, 7, 8, all, ascii-lower စသည်ဖြင့်မိမိအသုံးပြုလိုတာကိုရွေးပြီး စတင်ပါ။")
        else:
            await bot.reply_to(message, f"Session URL မှားယွင်းနေပါသည်။")

@bot.message_handler(commands=['scan'])
async def scan(message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await bot.reply_to(
            message,
            "Usage:\n\n/scan <6, 7, 8, ascii-lower, all>"
        )
        return
    mode = args[1]
    chat_id = message.chat.id
    if not approve.get(chat_id, False):
        await bot.reply_to(message, "/scan ကိုအသုံးမပြုမီ /key ကိုအရင်ပြုလုပ်ပေးပါ။")
        return
    chat_id = message.chat.id
    if chat_id not in user_data:
        await bot.reply_to(message, "/scan ကိုအသုံးမပြုမီ /key ကိုအရင်ပြုလုပ်ပေးပါ။")
        return
    if 'session_url' not in user_data[chat_id]:
        await bot.reply_to(message, "/scan ကိုအသုံးမပြုမီ /input ဖြင့် Session URL ကိုအရင်ထည့်သွင်းပေးရပါမည်။")
        return

    if (
        chat_id in scan_tasks
        and not scan_tasks[chat_id]["task"].done()
    ):
        await bot.reply_to(
            message,
            "/scan သည် အလုပ်လုပ်နေပြီဖြစ်သည် /scan ကိုထပ်မံမလုပ်ပါနှင့်။"
        )
        return

    progress_msg = await bot.send_message(
        chat_id,
        "စတင်နေပါပြီ..."
    )

async def main():
    global session, _connector
    _connector = aiohttp.TCPConnector(limit=CONCURRENCY, ttl_dns_cache=300)
    session = aiohttp.ClientSession(connector=_connector)
    await web_server()
    try:
        await bot.infinity_polling()
    finally:
        await session.close()

if __name__ == '__main__':
    asyncio.run(main())
