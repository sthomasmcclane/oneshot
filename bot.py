import os
import logging
import random
import asyncio
import datetime
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
        task_title = ai_meta.get('title', text[:30])
        
        # Explicit override for "idea:" prefix
        if text.lower().startswith('idea:'):
            ai_meta['is_shiny_object'] = True
            if task_title.lower().startswith('idea:'):
                task_title = task_title[5:].strip()
                
        if ai_meta.get('is_shiny_object'):
            tasks_handler.create_shiny_object(task_title)
            confirmation = (
                f"✨ *Shiny Object Detected: {task_title}*\n"
                f"I've placed this in the Incubator. I'll check back with you in 30 days before we commit any time to it."
            )
            await status_msg.edit_text(confirmation, parse_mode="Markdown")
            return
            
        steps = ai_handler.decompose_task(text)
        
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

async def check_incubator_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        mature_tasks = tasks_handler.get_mature_shiny_objects()
        for task in mature_tasks:
            keyboard = [
                [
                    InlineKeyboardButton("✅ Start Project", callback_data=f"incubatestart_{task['id']}"),
                    InlineKeyboardButton("🗑️ Trash it", callback_data=f"incubatetrash_{task['id']}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            msg = (
                f"🕰️ *30 Days Ago...*\n\n"
                f"You had the idea to: *{task['title']}*\n\n"
                f"Are you still interested in this, or was it just a shiny object?"
            )
            await context.bot.send_message(chat_id=AUTHORIZED_USER_ID, text=msg, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Error checking incubator: {e}")

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
    elif data.startswith("incubatestart_"):
        task_id = data.split("_", 1)[1]
        try:
            await query.edit_message_text("🧠 Warming up the incubator... Decomposing project into actionable steps...")
            title = tasks_handler.get_shiny_object_title(task_id)
            
            # Decompose and create
            ai_meta = ai_handler.extract_metadata(title)
            steps = ai_handler.decompose_task(title)
            tasks_handler.create_task(title, ai_meta, steps)
            
            # Delete from incubator
            tasks_handler.delete_shiny_object(task_id)
            
            await query.edit_message_text(f"🚀 *{title}* is now live!\nDecomposed into {len(steps)} steps and moved to OneShot Tasks.", parse_mode="Markdown")
        except Exception as e:
            await query.edit_message_text(f"❌ Error starting project: {str(e)}")
            
    elif data.startswith("incubatetrash_"):
        task_id = data.split("_", 1)[1]
        try:
            tasks_handler.delete_shiny_object(task_id)
            await query.edit_message_text("🗑️ Shiny object trashed. Crisis averted!")
        except Exception as e:
            await query.edit_message_text(f"❌ Error trashing project: {str(e)}")

def main():
    if not TOKEN:
        logging.error("No TELEGRAM_BOT_TOKEN provided in environment variables.")
        return
        
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Schedule incubator check every morning at 09:00
    if application.job_queue:
        application.job_queue.run_daily(check_incubator_job, time=datetime.time(hour=9, minute=0, second=0))
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Start the bot
    application.run_polling()

if __name__ == '__main__':
    main()
