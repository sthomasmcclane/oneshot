import os
import logging
import random
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import tasks_handler
import ai_handler
import reality_handler

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AUTHORIZED_USER_ID = os.getenv("AUTHORIZED_USER_ID")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome to OneShot Tasks V2.\n\nType naturally to capture tasks, or type '.' to get your next optimized task.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Type naturally to capture tasks. Type '.' for the Now view. Use /nudge for a morning summary.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    text = update.message.text.strip()
    
    # 1. The "Now" View Algorithm
    if text == '.' or text.lower() == 'now':
        await surface_now_task(update, context)
        return
        
    # 2. Task Capture Logic
    status_msg = await update.message.reply_text("🧠 Processing task...")
    try:
        # Zero Syntax Inference
        ai_meta = ai_handler.extract_metadata(text)
        steps = ai_handler.decompose_task(text)
        
        task_title = ai_meta.get('title', text[:30])
        
        # Save to Google Tasks
        tasks_handler.create_task(task_title, ai_meta, steps)
        
        confirmation = (
            f"✅ *{task_title}* saved to Google Tasks!\n"
            f"Context: {ai_meta.get('context')} • Energy: {ai_meta.get('energy')} • Duration: {ai_meta.get('duration')}\n"
            f"Decomposed into {len(steps)} steps."
        )
        await status_msg.edit_text(confirmation, parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"Error processing task: {e}")
        await status_msg.edit_text(f"❌ Error: {str(e)}")

async def surface_now_task(update, context):
    try:
        tasks = tasks_handler.get_active_tasks()
        if not tasks:
            await update.message.reply_text("You have no active tasks in Google Tasks!")
            return
            
        # Empathy Algorithm
        # For the V2 MVP, we randomly select from tasks to prevent decision fatigue. 
        # Future enhancement: correlate energy/context with time of day (e.g. high energy in morning).
        selected_task = random.choice(tasks)
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Complete", callback_data=f"complete_{selected_task['id']}"),
                InlineKeyboardButton("⏭️ Not Now", callback_data="skip")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        msg = (
            f"🎯 *Suggested Task for Now:*\n\n"
            f"*{selected_task['title']}*\n"
            f"Context: {selected_task['context']} • Energy: {selected_task['energy']} • Duration: {selected_task['duration']}"
        )
        await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"Error surfacing task: {e}")
        await update.message.reply_text(f"Error pulling tasks from Google: {str(e)}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data.startswith("complete_"):
        # The Google Tasks API uses string IDs
        task_id = data.split("_", 1)[1]
        try:
            tasks_handler.complete_task(task_id)
            await query.edit_message_text("🏁 Task marked completed in Google Tasks!")
        except Exception as e:
            await query.edit_message_text(f"❌ Error completing task: {str(e)}")
    elif data == "skip":
        await query.edit_message_text("⏭️ Task skipped for now. Send '.' to pull another.")

def main():
    if not TOKEN:
        logging.error("No TELEGRAM_BOT_TOKEN provided in environment variables.")
        return
        
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Start the bot
    application.run_polling()

if __name__ == '__main__':
    main()
