import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
import sqlite3
import datetime

# Constants for feeding notifications
NOTIFICATION_JOB_QUEUE_INTERVAL_SECONDS = 300  # Interval to check feeding status (5 minutes)
NOTIFICATION_JOB_QUEUE_FIRST_SECONDS = 10  # Initial delay for the first check
NOTIFY_IF_UNFED_FOR_SECONDS = 10800  # Notify if no feeding for 3 hours (10800 seconds)

# Get the Telegram bot token
BOT_TOKEN = "7790382746:AAEhGPg2qoNnboGQsntZzNMcez6-YeL7LEs"

# Initialize database
def init_db():
    conn = sqlite3.connect("baby_tracker.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            amount TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "\ud83d\udc76 Hi! I'm your BabyTrackerBot. Use /help to see what I can do for you!"
    )

# Help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Here are my commands:\n"
        "/log_feed <amount> - Log milk intake (e.g., /log_feed 150ml)\n"
        "/log_diaper <type> - Log diaper change (wet/dirty)\n"
        "/log_sleep <hours> - Log sleep duration (e.g., /log_sleep 2.5)\n"
        "/daily_summary - Get a summary of today's activities\n"
        "/view_last_feeding - View the last feeding time and amount\n"
        "/feeding_statistics - Get 24-hour feeding stats\n"
        "/start_notifications - Enable feeding reminders"
    )

# Log feeding
async def log_feed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /log_feed <amount> (e.g., /log_feed 150ml)")
        return

    amount = context.args[0]
    conn = sqlite3.connect("baby_tracker.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO activities (type, amount) VALUES (?, ?)", ("feed", amount))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"\u2705 Milk intake logged: {amount}")

# Log diaper changes
async def log_diaper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /log_diaper <type> (e.g., /log_diaper wet)")
        return

    diaper_type = context.args[0].lower()
    if diaper_type not in ["wet", "dirty"]:
        await update.message.reply_text("Please specify 'wet' or 'dirty'.")
        return

    conn = sqlite3.connect("baby_tracker.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO activities (type, amount) VALUES (?, ?)", ("diaper", diaper_type))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"\u2705 Diaper change logged: {diaper_type}")

# Log sleep
async def log_sleep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /log_sleep <hours> (e.g., /log_sleep 3.5)")
        return

    try:
        hours = float(context.args[0])
    except ValueError:
        await update.message.reply_text("Please enter a valid number of hours.")
        return

    conn = sqlite3.connect("baby_tracker.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO activities (type, amount) VALUES (?, ?)", ("sleep", str(hours)))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"\u2705 Sleep logged: {hours} hours")

# View Last Feeding
async def view_last_feeding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect("baby_tracker.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT amount, timestamp FROM activities
        WHERE type = 'feed'
        ORDER BY timestamp DESC LIMIT 1
    """)
    last_feed = cursor.fetchone()
    conn.close()

    if last_feed:
        amount, timestamp = last_feed
        response = f"\ud83c\udf7c Last feeding:\n- Amount: {amount}\n- Time: {timestamp}"
    else:
        response = "No feedings recorded yet. Use /log_feed <amount> to record a feeding."

    await update.message.reply_text(response)

# 24-Hour Feeding Statistics
async def feeding_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.datetime.now()
    past_24_hours = now - datetime.timedelta(hours=24)
    conn = sqlite3.connect("baby_tracker.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT timestamp, amount FROM activities
        WHERE type = 'feed' AND timestamp >= ?
        ORDER BY timestamp ASC
    """, (past_24_hours,))
    feedings = cursor.fetchall()
    conn.close()

    if feedings:
        response = "\ud83d\udcca Feeding Statistics (Last 24 Hours):\n"
        intervals = []
        previous_time = None
        total_feed = 0

        for feed in feedings:
            timestamp, amount = feed
            total_feed += float(amount.rstrip("ml"))
            if previous_time:
                interval = (datetime.datetime.fromisoformat(timestamp) - previous_time).total_seconds() / 60
                intervals.append(f"{interval:.1f} minutes")
            previous_time = datetime.datetime.fromisoformat(timestamp)
            response += f"- Time: {timestamp}, Amount: {amount}\n"

        if intervals:
            avg_interval = sum(map(float, [i.split()[0] for i in intervals])) / len(intervals)
            response += f"\nAverage Interval: {avg_interval:.1f} minutes"
        response += f"\nTotal Feed: {total_feed:.1f} ml in the last 24 hours."
    else:
        response = "No feedings recorded in the last 24 hours. Use /log_feed <amount> to start tracking."

    await update.message.reply_text(response)

# Feeding Notification
def check_feeding_notification(context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect("baby_tracker.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT timestamp FROM activities
        WHERE type = 'feed'
        ORDER BY timestamp DESC LIMIT 1
    """)
    last_feed = cursor.fetchone()
    conn.close()

    if last_feed:
        last_feed_time = datetime.datetime.fromisoformat(last_feed[0])
        time_since_last_feed = (datetime.datetime.now() - last_feed_time).total_seconds()

        if time_since_last_feed > NOTIFY_IF_UNFED_FOR_SECONDS:
            context.bot.send_message(
                chat_id=context.job.chat_id,
                text="\ud83d\udd14 Reminder: It's been over 3 hours since the last feeding. Please check on Emilia!"
            )
    else:
        context.bot.send_message(
            chat_id=context.job.chat_id,
            text="\ud83d\udd14 Reminder: No feedings have been logged yet. Please record feeding times."
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
    await update.message.reply_text("\u2705 Notifications for feeding reminders have been enabled!")

# Initialize bot
if __name__ == "__main__":
    init_db()

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("log_feed", log_feed))
    application.add_handler(CommandHandler("log_diaper", log_diaper))
    application.add_handler(CommandHandler("log_sleep", log_sleep))
    application.add_handler(CommandHandler("daily_summary", daily_summary))
    application.add_handler(CommandHandler("view_last_feeding", view_last_feeding))
    application.add_handler(CommandHandler("feeding_statistics", feeding_statistics))
    application.add_handler(CommandHandler("start_notifications", start_notifications))

    print("Bot is running...")
    application.run_polling()
