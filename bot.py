import sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from config import *

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
async def force_join(update, context):
    try:
        member = await context.bot.get_chat_member(
            FORCE_CHANNEL_USERNAME, update.effective_user.id
        )
        if member.status in ["left", "kicked"]:
            raise Exception
        return True
    except:
        await update.message.reply_text(
            f"🚫 *Join our channel to use this bot*\n\n👉 {FORCE_CHANNEL_LINK}",
            parse_mode="Markdown"
        )
        return False

# ================= MAIN MENU =================
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 ADD FUNDS", callback_data="add_funds")],
        [
            InlineKeyboardButton("🔵 FACEBOOK ₹25", callback_data="facebook"),
            InlineKeyboardButton("🔵 GOOGLE ₹25", callback_data="google"),
        ],
        [
            InlineKeyboardButton("🔵 TWITTER ₹25", callback_data="twitter"),
            InlineKeyboardButton("🔵 GUEST ₹20", callback_data="guest"),
        ],
        [
            InlineKeyboardButton("📜 MY ORDERS", callback_data="my_orders"),
            InlineKeyboardButton("💳 MY BALANCE", callback_data="balance"),
        ],
        [
            InlineKeyboardButton("👥 REFER & EARN", callback_data="refer"),
            InlineKeyboardButton("⭐ PAID PUSH", callback_data="paid_push"),
        ],
        [
            InlineKeyboardButton("🔗 CHANNEL", callback_data="channel"),
            InlineKeyboardButton("⚫ CONTACT OWNER", callback_data="owner"),
        ]
    ])

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join(update, context):
        return

    user_id = update.effective_user.id
    cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()

    # Referral logic
    if context.args:
        ref_id = int(context.args[0])
        if ref_id != user_id:
            cur.execute("SELECT * FROM referrals WHERE user_id=?", (user_id,))
            if not cur.fetchone():
                cur.execute("INSERT INTO referrals VALUES (?,?)", (user_id, ref_id))
                cur.execute(
                    "UPDATE users SET balance = balance + ? WHERE user_id=?",
                    (REFERRAL_REWARD, ref_id)
                )
                conn.commit()
                await context.bot.send_message(
                    ref_id,
                    f"🎉 Referral bonus ₹{REFERRAL_REWARD} added!",
                )

    await update.message.reply_text(
        "📩 *Welcome to the Service Bot*",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

# ================= USER BUTTONS =================
async def user_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data.upper() in SERVICE_PRICES:
        cur.execute(
            "INSERT INTO orders (user_id, service) VALUES (?,?)",
            (user_id, data.upper())
        )
        conn.commit()
        oid = cur.lastrowid
        await query.message.reply_text(
            f"✅ Order Created\n🆔 {oid}\n📦 {data.upper()}\n⏳ Pending"
        )

    elif data == "my_orders":
        cur.execute("SELECT id, service, status FROM orders WHERE user_id=?", (user_id,))
        rows = cur.fetchall()
        if not rows:
            await query.message.reply_text("📭 No orders found")
            return
        msg = "📜 Your Orders\n\n"
        for r in rows:
            msg += f"🆔 {r[0]} | {r[1]} | {r[2]}\n"
        await query.message.reply_text(msg)

    elif data == "balance":
        cur.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        bal = cur.fetchone()[0]
        await query.message.reply_text(f"💳 Balance: ₹{bal}")

    elif data == "refer":
        link = f"https://t.me/{context.bot.username}?start={user_id}"
        await query.message.reply_text(
            f"👥 Refer & Earn ₹{REFERRAL_REWARD}\n\n{link}"
        )

    elif data == "owner":
        await query.message.reply_text(f"📞 Owner: {ADMIN_USERNAME}")

    elif data == "channel":
        await query.message.reply_text(FORCE_CHANNEL_LINK)

    elif data == "add_funds":
        await query.message.reply_text("💰 Contact admin to add funds")

    elif data == "paid_push":
        await query.message.reply_text("⭐ Paid Push\nContact admin")

# ================= ADMIN PANEL =================
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Manage Orders", callback_data="admin_orders")],
        [InlineKeyboardButton("📊 Sales Analytics", callback_data="admin_analytics")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")]
    ])
    await update.message.reply_text("👑 Admin Panel", reply_markup=kb)

# ================= ADMIN BUTTONS =================
async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id not in ADMIN_IDS:
        return

    if query.data == "admin_orders":
        cur.execute("SELECT id, service, status FROM orders")
        for o in cur.fetchall():
            kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Complete", callback_data=f"complete_{o[0]}"),
                    InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{o[0]}")
                ]
            ])
            await query.message.reply_text(
                f"🆔 {o[0]} | {o[1]} | {o[2]}",
                reply_markup=kb
            )

    elif query.data == "admin_broadcast":
        context.user_data["broadcast"] = True
        await query.message.reply_text("📢 Send broadcast message")

    elif query.data == "admin_analytics":
        cur.execute("SELECT COUNT(*) FROM users")
        users = cur.fetchone()[0]

        cur.execute("SELECT service FROM orders WHERE status='Completed'")
        revenue = sum(SERVICE_PRICES.get(o[0], 0) for o in cur.fetchall())

        await query.message.reply_text(
            f"📊 Analytics\n\n👥 Users: {users}\n💰 Revenue: ₹{revenue}"
        )

# ================= ORDER UPDATE & DELIVERY =================
async def update_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id not in ADMIN_IDS:
        return

    action, oid = query.data.split("_")
    status = "Completed" if action == "complete" else "Cancelled"

    cur.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
    conn.commit()

    cur.execute("SELECT user_id, service FROM orders WHERE id=?", (oid,))
    uid, service = cur.fetchone()

    cur.execute("SELECT message FROM delivery WHERE service=?", (service,))
    msg = cur.fetchone()
    delivery_text = msg[0] if msg else "✅ Order completed"

    await context.bot.send_message(uid, delivery_text)
    await query.message.edit_text(f"Order {oid} → {status}")

# ================= DELIVERY SET =================
async def set_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    service = context.args[0].upper()
    context.user_data["delivery_service"] = service
    await update.message.reply_text(f"Send delivery text for {service}")

async def save_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    service = context.user_data.get("delivery_service")
    if service:
        cur.execute("INSERT OR REPLACE INTO delivery VALUES (?,?)",
                    (service, update.message.text))
        conn.commit()
        context.user_data["delivery_service"] = None
        await update.message.reply_text("✅ Delivery saved")

# ================= BROADCAST =================
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("broadcast"):
        cur.execute("SELECT user_id FROM users")
        for u in cur.fetchall():
            try:
                await context.bot.send_message(u[0], update.message.text)
            except:
                pass
        context.user_data["broadcast"] = False
        await update.message.reply_text("✅ Broadcast sent")

# ================= RUN =================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("setdelivery", set_delivery))

    app.add_handler(CallbackQueryHandler(update_order, pattern="^(complete|cancel)_"))
    app.add_handler(CallbackQueryHandler(admin_buttons, pattern="^admin_"))
    app.add_handler(CallbackQueryHandler(user_buttons))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save_delivery))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast))

    print("🤖 Bot Running...")
    app.run_polling()

if __name__ == "__main__":
    main()