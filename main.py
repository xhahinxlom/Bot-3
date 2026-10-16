import os
import re
import json
import asyncio
import time
from threading import Thread
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ==========================================
# কনফিগারেশন
# ==========================================
BOT_TOKEN = "8844166711:AAFYRraiOHzbGJrrCWhUggmV8egW4p1n980"
ADMIN_ID = 8583812180
BOT_USERNAME = "@premium12_bot"
RENDER_URL = "https://my-2-d05t.onrender.com"
WEB_APP_URL = "https://premiumxyz.dpdns.org/"
DB_FILE = "videos.json"
ADMIN_LINK = "https://t.me/premium12_bot/admin"  # 👈 আপনার কাঙ্ক্ষিত লিংক

HEADER_TEXT = "🎬 আপনার ভিডিওগুলো এখানে"

# ==========================================
# ডাটাবেজ
# ==========================================
def load_db():
    if not os.path.exists(DB_FILE):
        return {"next_id": 1, "videos": {}}
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"next_id": 1, "videos": {}}

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)

def add_album(media_list, title):
    """media_list = [{"file_id": "...", "type": "video/photo"}, ...]"""
    db = load_db()
    vid = str(db["next_id"])
    db["videos"][vid] = {"media": media_list, "title": title}
    db["next_id"] += 1
    save_db(db)
    return vid

def get_video(vid):
    db = load_db()
    return db["videos"].get(str(vid))

# ==========================================
# Telegram Application (webhook mode)
# ==========================================
application = Application.builder().token(BOT_TOKEN).updater(None).build()

# অ্যাডমিনের ব্যাচ প্রসেস করার জন্য বাফার
admin_batches = {}  # user_id -> {"media": [...], "title": "...", "task": asyncio.Task}

# ==========================================
# ১৫ মিনিট পর delete
# ==========================================
async def delete_after_delay(chat_id, message_ids, context):
    await asyncio.sleep(900)
    for mid in message_ids:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=mid)
        except Exception as e:
            print(f"Delete error {mid}: {e}")
    print(f"✅ Deleted {len(message_ids)} messages from chat {chat_id}")

# ==========================================
# অ্যাডমিনের মিডিয়া ব্যাচ প্রসেস (১০টার বেশি মিডিয়া এক লিংকে)
# ==========================================
async def wait_and_process_batch(user_id, context, chat_id):
    try:
        # ৫ সেকেন্ড অপেক্ষা করো। এর মধ্যে নতুন মিডিয়া আসলে এই টাস্ক বাতিল হবে।
        await asyncio.sleep(5)
        
        batch_data = admin_batches.pop(user_id, None)
        if not batch_data or not batch_data["media"]:
            return

        media_list = batch_data["media"]
        title = batch_data["title"]

        # একটাই লিংক তৈরি করো
        short_id = add_album(media_list, title)
        final_link = f"https://t.me/{BOT_USERNAME}?start={short_id}"

        count = len(media_list)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ **{count}টি মিডিয়া সেভ হয়েছে!**\n\n"
                 f"🆔 **Short ID:** `{short_id}`\n"
                 f"📝 **Title:** {title}\n\n"
                 f"🔗 **Download লিংক:**\n"
                 f"`{final_link}`",
            parse_mode="Markdown"
        )
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"Batch process error: {e}")

# ==========================================
# /start — User কে media পাঠায়
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    args = context.args

    # ===== args নেই মানে শুধু /start বাটন চাপা হয়েছে =====
    if not args:
        # ১. Inline keyboard তৈরি — "Open Video 🔞" বাটন সরাসরি লিংকে যাবে
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    text="Open Video 🔞",
                    url=ADMIN_LINK
                )
            ]
        ])

        # ২. আপনার দেওয়া হুবহু লেখা
        caption_text = (
            "✨ Welcome to  𝖯𝖱𝖤𝖬𝖨𝖴𝖬 HUB ✨\n"
            "🔥 Get Exclusive Videos & the Latest Trending Content — FREE!\n"
            "🎬 প্রতিদিন নতুন নতুন এক্সক্লুসিভ ভিডিও ও ট্রেন্ডিং কনটেন্ট উপভোগ করুন একদম ফ্রি!\n"
            "📢 নিয়মিত আপডেট, নতুন ভিডিও এবং সাপোর্ট পেতে আমাদের অফিসিয়াল চ্যানেলে যুক্ত থাকুন:\n"
            "https://t.me/+x3NVMZYXWZo2YzM1\n"
            "✅ Click the button below to watch the video!\n"
            "👇👇👇👇👇👇👇👇👇👇👇"
        )

        # ৩. ছবি + ক্যাপশন + বাটন পাঠানো
        try:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo="YOUR_PHOTO_FILE_ID_OR_URL",  # 👈 এখানে ছবির File ID বা URL বসান
                caption=caption_text,
                reply_markup=keyboard
            )
        except Exception as e:
            print(f"Welcome photo error: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=caption_text,
                reply_markup=keyboard
            )
        return

    # ===== args আছে (রেফারেল লিংক) ==========
    video = get_video(args[0])
    if not video:
        await update.message.reply_text("❌ দুঃখিত! ভিডিওটি পাওয়া যায়নি।")
        return

    media_list = video.get("media", [])
    if not media_list:
        await update.message.reply_text("❌ কোনো মিডিয়া পাওয়া যায়নি।")
        return

    sent_ids = []

    for item in media_list:
        try:
            if item["type"] == "video":
                m = await context.bot.send_video(chat_id=chat_id, video=item["file_id"])
            else:
                m = await context.bot.send_photo(chat_id=chat_id, photo=item["file_id"])
            sent_ids.append(m.message_id)
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"Send error: {e}")

    # 👇 ভিডিও পাঠানোর পর নিচের বাটন (t.me/premium12_bot/admin লিংক যুক্ত)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 আরো ভিডিও দেখুন", url=ADMIN_LINK)]
    ])

    final_text = (
        f"*{HEADER_TEXT}*\n\n"
        f"⚠️ এই ভিডিওগুলো *১৫ মিনিট পর* ডিলিট হয়ে যাবে।\n"
        f"চাইলে সেভ করে রাখতে পারেন।"
    )

    try:
        final_msg = await context.bot.send_message(
            chat_id=chat_id,
            text=final_text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        sent_ids.append(final_msg.message_id)
    except Exception as e:
        print(f"Final message error: {e}")

    asyncio.create_task(delete_after_delay(chat_id, sent_ids, context))

# ==========================================
# Admin media handler (album + single + unlimited batch)
# ==========================================
async def catch_everything(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    # শুধু admin
    if update.effective_user.id != ADMIN_ID:
        if message.text and not message.text.startswith('/'):
            await message.reply_text(
                "👋 হ্যালো! ভিডিও ডাউনলোড করতে আমাদের ওয়েবসাইট ব্যবহার করুন।"
            )
        return

    # কোনো media আছে কিনা
    file_id = None
    media_type = None

    if message.video:
        file_id = message.video.file_id
        media_type = "video"
    elif message.photo:
        file_id = message.photo[-1].file_id
        media_type = "photo"
    elif message.document and message.document.mime_type and message.document.mime_type.startswith('video/'):
        file_id = message.document.file_id
        media_type = "video"
    elif message.animation:
        file_id = message.animation.file_id
        media_type = "video"

    # চ্যানেল link টেক্সট দিলে forward করে file_id বের করা
    elif message.text and "t.me/" in message.text:
        link_parts = re.findall(r't\.me/(?:c/)?([^/]+)/(\d+)', message.text)
        if link_parts:
            channel_peer, msg_id = link_parts[0]
            message_id = int(msg_id)
            chat_target = int(f"-100{channel_peer}") if channel_peer.isdigit() else f"@{channel_peer}"
            try:
                target_msg = await context.bot.forward_message(
                    chat_id=message.chat_id,
                    from_chat_id=chat_target,
                    message_id=message_id
                )
                if target_msg.video:
                    file_id = target_msg.video.file_id
                    media_type = "video"
                elif target_msg.photo:
                    file_id = target_msg.photo[-1].file_id
                    media_type = "photo"
                elif target_msg.document:
                    file_id = target_msg.document.file_id
                    media_type = "video"
                elif target_msg.animation:
                    file_id = target_msg.animation.file_id
                    media_type = "video"

                await context.bot.delete_message(
                    chat_id=message.chat_id,
                    message_id=target_msg.message_id
                )
            except Exception as e:
                await message.reply_text("❌ চ্যানেল থেকে ফাইল রিড করা যায়নি।")
                print(f"Forward error: {e}")
                return

    # কোনো media পাওয়া যায়নি
    if not file_id:
        return

    user_id = update.effective_user.id
    chat_id = message.chat_id

    # ===== নতুন ব্যাচ সিস্টেম (১০টার বেশি মিডিয়া এক লিংকে) =====
    if user_id not in admin_batches:
        admin_batches[user_id] = {
            "media": [],
            "title": message.caption or "Batch Upload",
            "task": None
        }

    # মিডিয়া যোগ করো
    admin_batches[user_id]["media"].append({
        "file_id": file_id,
        "type": media_type
    })

    # ক্যাপশন থাকলে টাইটেল আপডেট করো
    if message.caption:
        admin_batches[user_id]["title"] = message.caption

    # আগের টাইমার টাস্ক বাতিল করো (কারণ নতুন মিডিয়া এসেছে)
    if admin_batches[user_id]["task"]:
        admin_batches[user_id]["task"].cancel()

    # নতুন ৫ সেকেন্ডের টাইমার চালু করো
    admin_batches[user_id]["task"] = asyncio.create_task(
        wait_and_process_batch(user_id, context, chat_id)
    )

# ==========================================
# Handlers
# ==========================================
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.ALL, catch_everything))

# ==========================================
# Flask + Webhook
# ==========================================
app = Flask('')
loop = asyncio.new_event_loop()

@app.route('/')
def home():
    return "✅ Premium Hub Bot is Running"

@app.route('/health')
def health():
    return "alive", 200

@app.route(f'/webhook/{BOT_TOKEN}', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, application.bot)
        asyncio.run_coroutine_threadsafe(application.process_update(update), loop)
        return "ok", 200
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return "error", 500

# ==========================================
# Startup
# ==========================================
async def setup_bot():
    await application.initialize()
    await application.bot.set_webhook(
        url=f"{RENDER_URL}/webhook/{BOT_TOKEN}",
        drop_pending_updates=True
    )
    await application.start()
    print(f"✅ Webhook set: {RENDER_URL}/webhook/{BOT_TOKEN}")

def run_async():
    asyncio.set_event_loop(loop)
    loop.run_until_complete(setup_bot())
    loop.run_forever()

def main():
    Thread(target=run_async, daemon=True).start()
    time.sleep(3)
    port = int(os.environ.get("PORT", 8080))
    print(f"🌐 Flask running on port {port}")
    app.run(host='0.0.0.0', port=port, use_reloader=False)

if __name__ == '__main__':
    main()
