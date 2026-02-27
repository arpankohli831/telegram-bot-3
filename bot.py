import telebot
import sqlite3
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

# ================= CONFIG =================
BOT_TOKEN = "8767042514:AAGqnQSKeH1qHVc2nQqEY3repS6EyvBxCrg"

ADMIN_IDS = [7853887140]   # your numeric Telegram ID
ADMIN_USERNAME = "@ARPANMODX"

FORCE_CHANNEL_LINK = "https://t.me/+qWBcAAqb33Q3MmE1"
FORCE_CHANNEL_USERNAME = "+qWBcAAqb33Q3MmE1"

REFERRAL_REWARD = 10

SERVICE_PRICES = {
    "FACEBOOK": 25,
    "GOOGLE": 25,
    "TWITTER": 25,
    "GUEST": 20
}

bot = telebot.TeleBot(BOT_TOKEN)

# ================= DATABASE =================
conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    service TEXT,
    status TEXT DEFAULT 'Pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS referrals (
    user_id INTEGER PRIMARY KEY,
    referred_by INTEGER
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS delivery (
    service TEXT PRIMARY KEY,
    message TEXT
)""")

conn.commit()

# ================= FORCE JOIN =================
def force_join(message):
    try:
        member = bot.get_chat_member(FORCE_CHANNEL_USERNAME, message.from_user.id)
        if member.status in ["left", "kicked"]:
            raise Exception
        return True
    except:
        bot.send_message(
            message.chat.id,
            f"🚫 Join channel first:\n{FORCE_CHANNEL_LINK}"
        )
        return False

# ================= MAIN MENU =================
def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🟢 ADD FUNDS")
    kb.row("🔵 FACEBOOK ₹25", "🔵 GOOGLE ₹25")
    kb.row("🔵 TWITTER ₹25", "🔵 GUEST ₹20")
    kb.row("📜 MY ORDERS", "🟡 MY BALANCE")
    kb.row("👥 REFER & EARN", "⭐ PAID PUSH ⭐")
    kb.row("🔗 CHANNEL", "⚫ CONTACT OWNER")
    return kb

# ================= START =================
@bot.message_handler(commands=['start'])
def start(message):
    if not force_join(message):
        return

    user_id = message.from_user.id
    cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()

    # Referral
    if len(message.text.split()) > 1:
        ref_id = int(message.text.split()[1])
        if ref_id != user_id:
            cur.execute("SELECT * FROM referrals WHERE user_id=?", (user_id,))
            if not cur.fetchone():
                cur.execute("INSERT INTO referrals VALUES (?,?)", (user_id, ref_id))
                cur.execute(
                    "UPDATE users SET balance = balance + ? WHERE user_id=?",
                    (REFERRAL_REWARD, ref_id)
                )
                conn.commit()
                bot.send_message(ref_id, f"🎉 Referral bonus ₹{REFERRAL_REWARD} added!")

    bot.send_message(
        message.chat.id,
        "Welcome to our service bot 👋",
        reply_markup=main_menu()
    )

# ================= MESSAGE HANDLER =================
@bot.message_handler(func=lambda m: True)
def handler(message):
    if not force_join(message):
        return

    text = message.text
    user_id = message.from_user.id

    # ----- SERVICES -----
    for service in SERVICE_PRICES:
        if service in text:
            cur.execute(
                "INSERT INTO orders (user_id, service) VALUES (?,?)",
                (user_id, service)
            )
            conn.commit()
            oid = cur.lastrowid
            bot.reply_to(message, f"✅ Order Created\n🆔 {oid}\n📦 {service}")
            return

    # ----- MY ORDERS -----
    if text == "📜 MY ORDERS":
        cur.execute("SELECT id, service, status FROM orders WHERE user_id=?", (user_id,))
        rows = cur.fetchall()
        if not rows:
            bot.reply_to(message, "📭 No orders found")
            return
        msg = "📜 Your Orders\n\n"
        for r in rows:
            msg += f"🆔 {r[0]} | {r[1]} | {r[2]}\n"
        bot.reply_to(message, msg)

    # ----- BALANCE -----
    elif text == "🟡 MY BALANCE":
        cur.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        bal = cur.fetchone()[0]
        bot.reply_to(message, f"💳 Balance: ₹{bal}")

    # ----- REFER -----
    elif text == "👥 REFER & EARN":
        link = f"https://t.me/{bot.get_me().username}?start={user_id}"
        bot.reply_to(message, f"Earn ₹{REFERRAL_REWARD} per referral:\n{link}")

    # ----- ADD FUNDS -----
    elif text == "🟢 ADD FUNDS":
        bot.reply_to(message, "💰 Send payment screenshot to admin.")

    # ----- CHANNEL -----
    elif text == "🔗 CHANNEL":
        bot.reply_to(message, FORCE_CHANNEL_LINK)

    # ----- OWNER -----
    elif text == "⚫ CONTACT OWNER":
        bot.reply_to(message, f"👤 Owner: {ADMIN_USERNAME}")

    # ----- ADMIN PANEL -----
    elif text == "/admin" and user_id in ADMIN_IDS:
        bot.reply_to(
            message,
            "👑 Admin Commands:\n"
            "/orders – Manage orders\n"
            "/broadcast – Send broadcast\n"
            "/analytics – Sales analytics\n"
            "/setdelivery SERVICE"
        )

    # ----- ADMIN ORDERS -----
    elif text == "/orders" and user_id in ADMIN_IDS:
        cur.execute("SELECT id, service, status FROM orders")
        for o in cur.fetchall():
            bot.send_message(
                message.chat.id,
                f"🆔 {o[0]} | {o[1]} | {o[2]}\n"
                f"/complete_{o[0]} /cancel_{o[0]}"
            )

    # ----- COMPLETE / CANCEL -----
    elif text.startswith("/complete_") and user_id in ADMIN_IDS:
        oid = text.split("_")[1]
        cur.execute("UPDATE orders SET status='Completed' WHERE id=?", (oid,))
        conn.commit()

        cur.execute("SELECT user_id, service FROM orders WHERE id=?", (oid,))
        uid, service = cur.fetchone()

        cur.execute("SELECT message FROM delivery WHERE service=?", (service,))
        msg = cur.fetchone()
        delivery = msg[0] if msg else "✅ Order completed"

        bot.send_message(uid, delivery)
        bot.reply_to(message, f"Order {oid} completed")

    elif text.startswith("/cancel_") and user_id in ADMIN_IDS:
        oid = text.split("_")[1]
        cur.execute("UPDATE orders SET status='Cancelled' WHERE id=?", (oid,))
        conn.commit()
        bot.reply_to(message, f"Order {oid} cancelled")

    # ----- SET DELIVERY -----
    elif text.startswith("/setdelivery") and user_id in ADMIN_IDS:
        service = text.split()[1].upper()
        bot.reply_to(message, f"Send delivery message for {service}")
        bot.register_next_step_handler(message, save_delivery, service)

    # ----- ANALYTICS -----
    elif text == "/analytics" and user_id in ADMIN_IDS:
        cur.execute("SELECT COUNT(*) FROM users")
        users = cur.fetchone()[0]

        cur.execute("SELECT service FROM orders WHERE status='Completed'")
        revenue = sum(SERVICE_PRICES.get(o[0], 0) for o in cur.fetchall())

        bot.reply_to(
            message,
            f"📊 Analytics\n\n👥 Users: {users}\n💰 Revenue: ₹{revenue}"
        )

    # ----- BROADCAST -----
    elif text == "/broadcast" and user_id in ADMIN_IDS:
        bot.reply_to(message, "Send broadcast message")
        bot.register_next_step_handler(message, do_broadcast)

# ================= SAVE DELIVERY =================
def save_delivery(message, service):
    cur.execute("INSERT OR REPLACE INTO delivery VALUES (?,?)",
                (service, message.text))
    conn.commit()
    bot.reply_to(message, f"✅ Delivery saved for {service}")

# ================= BROADCAST =================
def do_broadcast(message):
    cur.execute("SELECT user_id FROM users")
    for u in cur.fetchall():
        try:
            bot.send_message(u[0], message.text)
        except:
            pass
    bot.reply_to(message, "✅ Broadcast sent")

# ================= RUN =================
print("🤖 Bot running...")
bot.infinity_polling()