import os
import logging
import random
import asyncio
import datetime
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import re
import tasks_handler
import ai_handler
import reality_handler
import database

def format_step_title(title):
    match = re.search(r'(?:🤖\s*)?(\d+)\s*[.-]\s*(?:🤖\s*)?(.*)', title)
    if match:
        num = int(match.group(1))
        desc = match.group(2)
        ai = "🤖 " if "🤖" in title else ""
        return f"Step {num}: {ai}{desc}"
    else:
        return f"Step: {title}"

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
        recent_logs = database.get_energy_logs(limit=1)
        max_energy = 3 # default to any (1=easy, 2=med, 3=hard)
        current_state = "🔋 High Energy" # default state
        
        if recent_logs:
            latest_energy_str = recent_logs[0][1]
            if latest_energy_str in ['🪫', '🌫️']:
                max_energy = 1
                current_state = "🪫 Low Energy / 🌫️ Brain Fog"
            else:
                max_energy = 3
                current_state = "🔋 High Energy / 🧠 High Focus"
                
        # Filter tasks matching energy constraint
        suitable_tasks = [t for t in tasks if t.get('energy', 2) <= max_energy]
        
        # Automatic Rescue: gradual fallback if no low-energy tasks exist
        if not suitable_tasks and max_energy == 1:
            suitable_tasks = [t for t in tasks if t.get('energy', 2) <= 2]
            current_state += " (Rescue: bumped to Level 2)"
            
        if not suitable_tasks:
            suitable_tasks = tasks
            if "Rescue" not in current_state:
                current_state += " (Rescue: bumped to All Tasks)"
            else:
                current_state = current_state.replace("Level 2", "All Tasks")

        selected_task = random.choice(suitable_tasks)
        
        next_step = tasks_handler.get_next_subtask(selected_task['id'])
        
        if next_step:
            step_text = format_step_title(next_step['title'])
            keyboard = [
                [
                    InlineKeyboardButton("✅ Step Done", callback_data=f"stepdone_{next_step['id']}"),
                    InlineKeyboardButton("⏭️ Not Now", callback_data="skip")
                ]
            ]
            msg = (
                f"_(Matching your current state: {current_state})_\n\n"
                f"I've selected the *{selected_task['title']}* task.\n"
                f"Let's get started.\n"
                f"*{step_text}*"
            )
        else:
            keyboard = [
                [
                    InlineKeyboardButton("✅ Complete Task", callback_data=f"complete_{selected_task['id']}"),
                    InlineKeyboardButton("⏭️ Not Now", callback_data="skip")
                ]
            ]
            msg = (
                f"_(Matching your current state: {current_state})_\n\n"
                f"I've selected the *{selected_task['title']}* task.\n"
                f"There are no uncompleted steps remaining. Ready to mark it as done?"
            )
            
        reply_markup = InlineKeyboardMarkup(keyboard)
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

async def check_energy_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        keyboard = [
            [
                InlineKeyboardButton("🔋 High Energy", callback_data="energy_🔋"),
                InlineKeyboardButton("🪫 Low Energy", callback_data="energy_🪫")
            ],
            [
                InlineKeyboardButton("🧠 High Focus", callback_data="energy_🧠"),
                InlineKeyboardButton("🌫️ Brain Fog", callback_data="energy_🌫️")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        msg = "🕰️ Time for an energy check-in! How are you feeling right now?"
        await context.bot.send_message(chat_id=AUTHORIZED_USER_ID, text=msg, reply_markup=reply_markup)
    except Exception as e:
        logging.error(f"Error checking energy: {e}")

async def check_decay_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        logging.info("Running daily decay job...")
        tasks_handler.archive_stale_tasks(days=14)
    except Exception as e:
        logging.error(f"Error in decay job: {e}")

async def monthly_review_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        import os
        if os.path.exists('data/archived_tasks.txt'):
            with open('data/archived_tasks.txt', 'r') as f:
                titles = [t.strip() for t in f.read().strip().split('\n') if t.strip()]
                
            if titles:
                msg = (
                    "🗓️ *Monthly Review*\n\n"
                    "Over the last 30 days, I shame-free archived these tasks that went cold for over 14 days:\n\n"
                )
                for t in titles:
                    msg += f"• {t}\n"
                msg += "\nThey are safely tucked away in your 'Someday' Google Tasks list if you ever want them back."
                
                await context.bot.send_message(chat_id=AUTHORIZED_USER_ID, text=msg, parse_mode="Markdown")
                
                # Clear file
                os.remove('data/archived_tasks.txt')
    except Exception as e:
        logging.error(f"Error in monthly review job: {e}")

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
            
    elif data.startswith("stepdone_"):
        step_id = data.split("_", 1)[1]
        try:
            # Fetch step to get its parent ID
            service = tasks_handler.get_service()
            tasklist_id = tasks_handler.get_or_create_tasklist(service)
            step_task = service.tasks().get(tasklist=tasklist_id, task=step_id).execute()
            parent_id = step_task.get('parent')
            
            # Now complete the step
            tasks_handler.complete_task(step_id)
            
            # Fetch the next step
            next_step = tasks_handler.get_next_subtask(parent_id)
            
            if next_step:
                step_text = format_step_title(next_step['title'])
                
                msg = (
                    f"✅ Step checked off!\n\n"
                    f"The next step is:\n"
                    f"*{step_text}*"
                )
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Step Done", callback_data=f"stepdone_{next_step['id']}"),
                        InlineKeyboardButton("⏭️ Not Now", callback_data="skip")
                    ]
                ]
                await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            else:
                # All steps done, offer to complete the parent task
                parent_task = service.tasks().get(tasklist=tasklist_id, task=parent_id).execute()
                parent_title = parent_task.get('title', 'Task')
                msg = f"🎉 All steps for *{parent_title}* are complete!\nReady to mark the whole task as done?"
                keyboard = [
                    [InlineKeyboardButton("✅ Complete Project", callback_data=f"complete_{parent_id}")]
                ]
                await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
                
        except Exception as e:
            await query.edit_message_text(f"❌ Error updating step: {str(e)}")
            
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
            
    elif data.startswith("energy_"):
        level = data.split("_", 1)[1]
        try:
            database.log_energy(level)
            await query.edit_message_text(f"Recorded your energy as {level}. Thanks!")
        except Exception as e:
            await query.edit_message_text(f"❌ Error recording energy: {str(e)}")

def main():
    if not TOKEN:
        logging.error("No TELEGRAM_BOT_TOKEN provided in environment variables.")
        return
        
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Ensure times are explicitly in Brisbane time
    brisbane_tz = ZoneInfo("Australia/Brisbane")

    # Schedule incubator check every morning at 09:00
    if application.job_queue:
        application.job_queue.run_daily(check_incubator_job, time=datetime.time(hour=9, minute=0, second=0, tzinfo=brisbane_tz))
        
        # Poll energy during waking hours (9am, 1pm, 5pm, 9pm)
        for hour in [9, 13, 17, 21]:
            application.job_queue.run_daily(check_energy_job, time=datetime.time(hour=hour, minute=0, second=0, tzinfo=brisbane_tz))
            
        # Daily check for 14-day stale tasks at 3:00 AM
        application.job_queue.run_daily(check_decay_job, time=datetime.time(hour=3, minute=0, second=0, tzinfo=brisbane_tz))
        
        # Monthly review on the 1st of every month at 10:00 AM
        application.job_queue.run_monthly(monthly_review_job, when=datetime.time(hour=10, minute=0, second=0, tzinfo=brisbane_tz), day=1)
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Start the bot
    application.run_polling()

if __name__ == '__main__':
    main()
