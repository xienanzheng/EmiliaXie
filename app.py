import os
from telegram import Update, InputMediaPhoto
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import sqlite3
import datetime
import random
import uuid

# Constants for feeding notifications
NOTIFICATION_JOB_QUEUE_INTERVAL_SECONDS = 300
NOTIFICATION_JOB_QUEUE_FIRST_SECONDS = 10
NOTIFY_IF_UNFED_FOR_SECONDS = 10800

# Get the Telegram bot token
BOT_TOKEN = "7790382746:AAEhGPg2qoNnboGQsntZzNMcez6-YeL7LEs"

# Initialize database
def init_db():
    conn = sqlite3.connect("baby_tracker.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            code TEXT PRIMARY KEY,
            baby_name TEXT,
            birth_date TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            type TEXT,
            amount TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (code) REFERENCES profiles (code)
        )
    """)
    conn.commit()
    conn.close()

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👶 Hi! I'm your BabyTrackerBot. Use /help to see what I can do for you!"
    )

# Help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Here are my commands:\n"
        "/create_profile <baby_name> <birth_date YYYY-MM-DD> - Create a profile for your baby\n"
        "/log_activity <code> <type> <amount> - Log activities (feed, diaper, sleep)\n"
        "/profile_summary <code> - Get a summary of all activities for a baby\n"
        "/upload_photo <code> - Upload a photo for a baby\n"
        "/send_daily_photo <code> - Get a random photo for a baby\n"
        "/start_notifications - Enable feeding reminders"
    )

# Create a baby profile
async def create_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /create_profile <baby_name> <birth_date YYYY-MM-DD>")
        return

    baby_name = context.args[0]
    birth_date = context.args[1]

    try:
        datetime.datetime.strptime(birth_date, "%Y-%m-%d")
    except ValueError:
        await update.message.reply_text("Please enter a valid birth date in YYYY-MM-DD format.")
        return

    code = str(uuid.uuid4())[:8]

    conn = sqlite3.connect("baby_tracker.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO profiles (code, baby_name, birth_date) VALUES (?, ?, ?)", (code, baby_name, birth_date))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"✅ Profile created for {baby_name}! Share this code with others to log activities: {code}")

# Log activities for a specific profile
async def log_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("Usage: /log_activity <code> <type> <amount>")
        return

    code = context.args[0]
    activity_type = context.args[1].lower()
    amount = context.args[2]

    if activity_type not in ["feed", "diaper", "sleep"]:
        await update.message.reply_text("Invalid type. Use 'feed', 'diaper', or 'sleep'.")
        return

    conn = sqlite3.connect("baby_tracker.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM profiles WHERE code = ?", (code,))
    profile = cursor.fetchone()

    if not profile:
        await update.message.reply_text("Invalid code. Please ensure the code is correct.")
        return

    cursor.execute("INSERT INTO activities (code, type, amount) VALUES (?, ?, ?)", (code, activity_type, amount))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"✅ {activity_type.capitalize()} logged for {profile[1]}: {amount}")

# View a summary for a specific profile
async def profile_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /profile_summary <code>")
        return

    code = context.args[0]
    conn = sqlite3.connect("baby_tracker.db", check_same_thread=False)
    cursor = conn.cursor()

    cursor.execute("SELECT baby_name FROM profiles WHERE code = ?", (code,))
    profile = cursor.fetchone()

    if not profile:
        await update.message.reply_text("Invalid code. Please ensure the code is correct.")
        return

    cursor.execute("""
        SELECT type, COUNT(*), SUM(CAST(amount AS FLOAT)) FROM activities
        WHERE code = ?
        GROUP BY type
    """, (code,))
    summary = cursor.fetchall()
    conn.close()

    response = f"📋 Summary for {profile[0]}:\n"
    for row in summary:
        if row[0] == "feed":
            response += f"- Milk intake: {row[2]} ml\n"
        elif row[0] == "diaper":
            response += f"- Diaper changes: {row[1]} times\n"
        elif row[0] == "sleep":
            response += f"- Sleep: {row[2]} hours\n"

    if not summary:
        response += "No activities logged yet. Start tracking now!"

    await update.message.reply_text(response)

# Upload photo for a specific profile
async def upload_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /upload_photo <code>")
        return

    code = context.args[0]
    conn = sqlite3.connect("baby_tracker.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT baby_name FROM profiles WHERE code = ?", (code,))
    profile = cursor.fetchone()

    if not profile:
        await update.message.reply_text("Invalid code. Please ensure the code is correct.")
        return

    if not update.message.photo:
        await update.message.reply_text("Please upload a photo with this command.")
        return

    file_id = update.message.photo[-1].file_id
    file = await context.bot.get_file(file_id)
    photo_dir = f"photos/{code}"
    os.makedirs(photo_dir, exist_ok=True)
    photo_path = f"{photo_dir}/{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.jpg"
    await file.download(photo_path)

    await update.message.reply_text(f"📸 Photo uploaded successfully for {profile[0]}!")

# Send random photo for a profile
async def send_daily_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /send_daily_photo <code>")
        return

    code = context.args[0]
    photo_dir = f"photos/{code}"

    if not os.path.exists(photo_dir) or not os.listdir(photo_dir):
        await update.message.reply_text("No photos available yet. Use /upload_photo <code> to add some.")
        return

    photo_path = random.choice(os.listdir(photo_dir))
    await update.message.reply_photo(photo=open(os.path.join(photo_dir, photo_path), 'rb'))

# Feeding Notification
def check_feeding_notification(context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect("baby_tracker.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT timestamp FROM activities
        WHERE type = 'feed'
        ORDER BY timestamp DESC LIMIT 1
    """)
    last_feed = cursor.fetchone()
    conn.close()

    if not last_feed:
        context.bot.send_message(
            chat_id=context.job.chat_id,
            text="🔔 Reminder: No feedings have been logged yet. Please record feeding times."
        )
        return

    last_feed_time = datetime.datetime.fromisoformat(last_feed[0])
    time_since_last_feed = (datetime.datetime.now() - last_feed_time).total_seconds()

    if time_since_last_feed > NOTIFY_IF_UNFED_FOR_SECONDS:
        context.bot.send_message(
            chat_id=context.job.chat_id,
            text="🔔 Reminder: It's been over 3 hours since the last feeding. Please check on your baby!"
        )

# Set up the notification job
async def start_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    context.job_queue.run_repeating(
        check_feeding_notification,
        interval=NOTIFICATION_JOB_QUEUE_INTERVAL_SECONDS,
        first=NOTIFICATION_JOB_QUEUE_FIRST_SECONDS,
        chat_id=chat_id
    )
    await update.message.reply_text("✅ Notifications for feeding reminders have been enabled!")

# Error handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"Exception while handling update: {context.error}")

# Initialize bot
if __name__ == "__main__":
    init_db()

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("create_profile", create_profile))
    application.add_handler(CommandHandler("log_activity", log_activity))
    application.add_handler(CommandHandler("profile_summary", profile_summary))
    application.add_handler(CommandHandler("upload_photo", upload_photo))
    application.add_handler(CommandHandler("send_daily_photo", send_daily_photo))
    application.add_handler(CommandHandler("start_notifications", start_notifications))
    application.add_error_handler(error_handler)

    print("Bot is running...")
    application.run_polling()
