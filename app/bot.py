import os
import hashlib
import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# =========================
# CONFIG
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")

# =========================
# DATABASE
# =========================

conn = sqlite3.connect("data.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id TEXT UNIQUE,
    bankroll INTEGER DEFAULT 0,
    vip INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id TEXT,
    session TEXT,
    result TEXT,
    created_at TEXT
)
""")

conn.commit()

# =========================
# AI ENGINE
# =========================

global_history = []

def md5_predict(session_id):
    hash_hex = hashlib.md5(session_id.encode()).hexdigest()
    number = int(hash_hex[-8:], 16)
    percent = number % 100
    result = "TÀI" if percent > 50 else "XỈU"
    return result, percent

def bayesian(history):
    if not history:
        return 50, 50
    tai = history.count("TÀI")
    total = len(history)
    p = (tai + 1) / (total + 2)
    return round(p * 100, 2), round((1 - p) * 100, 2)

def detect_streak(history):
    if len(history) < 3:
        return None
    last3 = history[-3:]
    if last3.count(last3[0]) == 3:
        return f"Bệt {last3[0]} 3+"
    return None

# =========================
# COMMANDS
# =========================

def start(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)

    cursor.execute("INSERT OR IGNORE INTO users (telegram_id) VALUES (?)", (user_id,))
    conn.commit()

    update.message.reply_text(
        "🤖 BOT PRO ONLINE\n"
        "Gửi mã phiên để soi.\n"
        "Lệnh:\n"
        "/bank - Xem vốn\n"
        "/setbank 1000 - Nhập vốn\n"
        "/vip - Kiểm tra VIP"
    )

def bank(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    cursor.execute("SELECT bankroll FROM users WHERE telegram_id=?", (user_id,))
    data = cursor.fetchone()
    bankroll = data[0] if data else 0
    update.message.reply_text(f"💰 Vốn hiện tại: {bankroll}")

def setbank(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    if len(context.args) != 1 or not context.args[0].isdigit():
        update.message.reply_text("Dùng: /setbank 1000")
        return

    amount = int(context.args[0])
    cursor.execute("UPDATE users SET bankroll=? WHERE telegram_id=?", (amount, user_id))
    conn.commit()
    update.message.reply_text(f"✅ Đã cập nhật vốn: {amount}")

def vip(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    cursor.execute("SELECT vip FROM users WHERE telegram_id=?", (user_id,))
    data = cursor.fetchone()
    status = "VIP 👑" if data and data[0] == 1 else "FREE"
    update.message.reply_text(f"Tài khoản: {status}")

# =========================
# MAIN AI HANDLE
# =========================

def handle(update: Update, context: CallbackContext):
    text = update.message.text.strip()
    user_id = str(update.effective_user.id)

    if not text.isdigit():
        update.message.reply_text("❌ Nhập mã phiên hợp lệ (chỉ số)")
        return

    result, percent = md5_predict(text)
    global_history.append(result)

    p_tai, p_xiu = bayesian(global_history)
    streak = detect_streak(global_history)

    ai_decision = "TÀI" if p_tai > p_xiu else "XỈU"
    confidence = abs(p_tai - p_xiu)

    cursor.execute(
        "INSERT INTO history (telegram_id, session, result, created_at) VALUES (?, ?, ?, ?)",
        (user_id, text, result, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()

    msg = (
        f"🎯 Phiên: {text}\n"
        f"MD5: {result} ({percent}%)\n"
        f"Bayes: {p_tai}% Tài\n"
        f"AI Tổng: {ai_decision}\n"
        f"Độ tin cậy: {confidence}%"
    )

    if streak:
        msg += f"\n⚠️ {streak}"

    update.message.reply_text(msg)

# =========================
# RUN BOT
# =========================

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("bank", bank))
    dp.add_handler(CommandHandler("setbank", setbank))
    dp.add_handler(CommandHandler("vip", vip))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()