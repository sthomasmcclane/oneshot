import os
import logging
import re
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import database
import ai_handler
import reality_handler

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AUTHORIZED_USER_ID = os.getenv("AUTHORIZED_USER_ID")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to OneShot Tasks.\n\n"
        "Use /help to see all commands and syntax."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🚀 *OneShot Tasks*\n\n"
        "*Capture:* Just send the task. Add markers like `+office`, `30m`, `large`, `#tag`, `!ui` (urgent/important), `!i` (important), or `[ai]` (AI-offloadable).\n\n"
        "*Pull:* Send any combination of markers (e.g., `+laptop 15m #git` or `ai` for AI-offloadable tasks) to get a matching task.\n\n"
        "*Commands:*\n"
        "• /dash: Your unified task dashboard.\n"
        "• /tags: List all active hashtags.\n"
        "• /nudge: Trigger a morning nudge manually.\n"
        "• /audit: Triage tasks older than 30 days.\n"
        "• /clear: Wipe everything.\n"
        "• /help: This guide."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def clear_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    database.clear_all_data()
    await update.message.reply_text("💥 Database wiped clean. Ready for fresh tasks.")

async def list_contexts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contexts = database.get_all_contexts()
    if not contexts:
        await update.message.reply_text("No active contexts found.")
        return
        
    msg = "📂 Active Contexts:\n\n"
    for ctx, count in contexts:
        msg += f"• +{ctx} ({count} steps)\n"
    
    await update.message.reply_text(msg)

async def list_magnitudes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    magnitudes = database.get_all_magnitudes()
    if not magnitudes:
        await update.message.reply_text("No pending tasks with sizes found.")
        return
        
    msg = "⚖️ Task Sizes:\n\n"
    for mag, count in magnitudes:
        msg += f"• {mag}: ({count} steps)\n"
    
    await update.message.reply_text(msg)

async def list_durations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    durations = database.get_all_durations()
    if not durations:
        await update.message.reply_text("No pending tasks with durations found.")
        return
        
    msg = "⏱️ Task Durations:\n\n"
    for dur, count in durations:
        msg += f"• {dur}: ({count} steps)\n"
    
    await update.message.reply_text(msg)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
        
    text = update.message.text.lower().strip()
    chat_id = update.effective_chat.id

    # 1. Universal Pull / Marker-Only Logic
    # Identify markers in the text
    ctx_match = re.search(r'\+(\w+)', text)
    dur_match = re.search(r'(\d+[mh])', text)
    mag_match = re.search(r'\b(small|medium|large)\b', text, re.IGNORECASE)
    tags_found = re.findall(r'#(\w+)', text)
    
    # Parse manual priority markers starting with !
    priority_matches = re.findall(r'!(\w+)', text)
    manual_urgent = None
    manual_important = None
    if priority_matches:
        manual_urgent = 0
        manual_important = 0
        for p in priority_matches:
            if 'u' in p.lower():
                manual_urgent = 1
            if 'i' in p.lower():
                manual_important = 1

    # Check for explicit AI-offloadable marker [ai], #ai, or word ai
    has_ai_marker = False
    if '[ai]' in text or '#ai' in text or re.search(r'\b(ai)\b', text):
        has_ai_marker = True

    # Check if the text consists ONLY of markers
    markers_text = re.sub(r'(\+\w+|#\w+|!\w+|\[ai\]|\b(ai)\b|\d+[mh]|\b(small|medium|large)\b)', '', text).strip()
    
    if not markers_text and (ctx_match or dur_match or mag_match or tags_found or has_ai_marker):
        # This is a direct pull request
        pull_ctx = ctx_match.group(1) if ctx_match else None
        pull_dur = dur_match.group(1) if dur_match else None
        pull_mag = mag_match.group(1).lower() if mag_match else None
        
        tasks = database.get_tasks(context=pull_ctx, duration=pull_dur, magnitude=pull_mag, tags=tags_found, limit=5, only_ai_offloadable=has_ai_marker)
        
        if tasks:
            await present_task_results(context.bot, chat_id, tasks, update, context)
        else:
            filters_desc = []
            if pull_ctx: filters_desc.append(f"+{pull_ctx}")
            if pull_dur: filters_desc.append(pull_dur)
            if pull_mag: filters_desc.append(pull_mag)
            if has_ai_marker: filters_desc.append("ai")
            for t in tags_found: filters_desc.append(f"#{t}")
            await update.message.reply_text(f"No active tasks found for: {' '.join(filters_desc)}")
        return

    # 2. Task Capture Logic
    status_msg = await update.message.reply_text("🧠...")
    
    task_ctx = ctx_match.group(1) if ctx_match else None
    task_dur = dur_match.group(1) if dur_match else None
    task_mag = mag_match.group(1).lower() if mag_match else None
    
    # Remove markers from raw text for cleaner decomposition
    clean_text = markers_text if markers_text else text
    clean_text = re.sub(r'\[ai\]', '', clean_text, flags=re.IGNORECASE)
    clean_text = re.sub(r'#ai\b', '', clean_text, flags=re.IGNORECASE).strip()
    
    # 3. AI Metadata and Decomposition with fallback
    use_fallback = False
    try:
        ai_meta = ai_handler.extract_metadata(clean_text)
        steps = ai_handler.decompose_task(clean_text)
    except Exception as e:
        logging.error(f"Gemini API error during task processing: {e}")
        use_fallback = True

    if not use_fallback:
        task_title = ai_meta.get('title', clean_text[:30])
        task_ctx = task_ctx or ai_meta.get('context', 'general')
        task_dur = task_dur or ai_meta.get('duration', 'unknown')
        task_mag = task_mag or ai_meta.get('magnitude', 'medium')
        task_scheduled = ai_meta.get('scheduled_at')
        
        # Merge manual tags with AI inferred tags
        ai_tags = ai_meta.get('tags', [])
        all_tags = list(set([f"#{t.lower().replace('#','')}" for t in tags_found + ai_tags]))
        task_tags_str = ",".join(all_tags) if all_tags else None
        
        # Priority logic: manual override first, then AI inference
        if manual_urgent is not None:
            task_urgent = manual_urgent
        else:
            task_urgent = 1 if ai_meta.get('urgent') else 0
            
        if manual_important is not None:
            task_important = manual_important
        else:
            task_important = 1 if ai_meta.get('important') else 0

        # priority text formatting
        p_text = ""
        if task_urgent and task_important:
            p_text = "🔥 *Urgent & Important (Q1)*"
        elif task_important:
            p_text = "⭐ *Important (Q2)*"
        elif task_urgent:
            p_text = "⚡ *Urgent (Q3)*"
        else:
            p_text = "📥 *Backlog (Q4)*"

        has_ai_steps = any(s.get("is_ai_offloadable") for s in steps) if isinstance(steps[0], dict) else has_ai_marker
        confirmation = f"✅ *{'🤖 ' if has_ai_steps else ''}{task_title}*\n"
        confirmation += f"+{task_ctx} • {task_dur} • {task_mag} • {len(steps)} steps"
        if has_ai_steps:
            confirmation += " (AI-Offloadable)"
        confirmation += "\n"
        confirmation += f"Priority: {p_text}\n"
        if task_scheduled:
            confirmation += f"⏰ Scheduled: {task_scheduled}\n"
        if all_tags:
            confirmation += f"{' • '.join(all_tags)}"
    else:
        # Fallback logging requested by user
        task_title = clean_text
        task_ctx = "fallback"
        task_dur = None
        task_mag = None
        task_scheduled = None
        # Preserve manual tags if any were specified
        task_tags_str = ",".join([f"#{t.lower()}" for t in tags_found]) if tags_found else None
        steps = [clean_text]
        
        task_urgent = manual_urgent if manual_urgent is not None else 0
        task_important = manual_important if manual_important is not None else 0

        # priority text formatting
        p_text = ""
        if task_urgent and task_important:
            p_text = "🔥 *Urgent & Important (Q1)*"
        elif task_important:
            p_text = "⭐ *Important (Q2)*"
        elif task_urgent:
            p_text = "⚡ *Urgent (Q3)*"
        else:
            p_text = "📥 *Backlog (Q4)*"
        
        confirmation = f"✅ *{task_title}*\n"
        confirmation += f"+{task_ctx}"
        if has_ai_marker:
            confirmation += " (AI-Offloadable)"
        confirmation += "\n"
        confirmation += f"Priority: {p_text}\n"
        if tags_found:
            confirmation += f"{' • '.join([f'#{t.lower()}' for t in tags_found])}"

    # 4. Save to Database (Local & fast, minimal timeout risk)
    try:
        task_id = database.add_task(clean_text, task_title, task_ctx, task_dur, task_mag, steps, tags=task_tags_str, scheduled_at=task_scheduled, is_urgent=task_urgent, is_important=task_important, force_ai_offloadable=has_ai_marker)
    except Exception as e:
        logging.error(f"Error saving task to DB: {e}")
        try:
            await status_msg.edit_text(f"❌ Database Error: {str(e)}", connect_timeout=5, write_timeout=5)
        except Exception as te:
            logging.error(f"Failed to send database error message: {te}")
        return

    # 5. Update UI (Network-dependent, wraps failures safely)
    try:
        await status_msg.edit_text(confirmation, parse_mode="Markdown", connect_timeout=5, write_timeout=5)
    except Exception as e:
        logging.warning(f"Failed to edit status message: {e}. Trying backup reply.")
        try:
            # Fallback to sending a new message if editing the existing one failed
            await update.message.reply_text(
                f"Saved: *{task_title}*\n+{task_ctx} (status message update failed)",
                parse_mode="Markdown",
                connect_timeout=5,
                write_timeout=5
            )
        except Exception as fallback_err:
            logging.error(f"Backup reply failed: {fallback_err}")

async def list_tags(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tags = database.get_all_tags()
    if not tags:
        await update.message.reply_text("No active tags found.")
        return
        
    msg = "🏷️ Active Tags:\n\n"
    for tag, count in tags:
        msg += f"• {tag} ({count} tasks)\n"
    
    await update.message.reply_text(msg)

async def present_task_results(bot, chat_id, tasks, update, context_obj=None, prefix="🎯 Next Project:"):
    if not tasks:
        return
        
    if len(tasks) == 1:
        await surface_task(bot, chat_id, tasks[0], context_obj, prefix=prefix)
    else:
        text = "🔍 *Multiple matching tasks found:*\n\n"
        keyboard = []
        row = []
        for idx, task in enumerate(tasks, 1):
            task_id, title, ctx, dur, mag, tags_str = task
            has_ai = database.task_has_ai_offloadable_steps(task_id)
            title_prefix = "🤖 " if has_ai else ""
            meta = f"+{ctx}"
            if dur and dur != 'unknown':
                meta += f" • {dur}"
            if mag and mag != 'medium':
                meta += f" • {mag}"
            
            text += f"{idx}. *{title_prefix}{title}* ({meta})\n"
            
            row.append(InlineKeyboardButton(f"Task {idx}", callback_data=f"selecttask_{task_id}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
            
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            if update.callback_query:
                await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown", connect_timeout=5, write_timeout=5)
            else:
                await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown", connect_timeout=5, write_timeout=5)
        except Exception as e:
            logging.error(f"Error displaying task selection menu: {e}")

async def surface_task(bot, chat_id, task_tuple, context_obj=None, prefix="🎯 Next Project:"):
    task_id, title, ctx, dur, mag, tags_str = task_tuple
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Accept", callback_data=f"taskaccept_{task_id}"),
            InlineKeyboardButton("⏭️ Not Now", callback_data=f"taskskip_{task_id}"),
        ],
        [
            InlineKeyboardButton("🏁 Complete All", callback_data=f"taskcomplete_{task_id}"),
            InlineKeyboardButton("🗑️ Delete", callback_data=f"taskdelete_{task_id}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    has_ai = database.task_has_ai_offloadable_steps(task_id)
    title_prefix = "🤖 " if has_ai else ""
    tags_text = f"\n\n{' • '.join(tags_str.split(','))}" if tags_str else ""
    meta_text = f"+{ctx} • {dur} • {mag}"
    
    for attempt in range(3):
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=f"{prefix}\n*{title_prefix}{title}*\n_{meta_text}_{tags_text}",
                reply_markup=reply_markup,
                parse_mode="Markdown",
                connect_timeout=5,
                write_timeout=5,
                read_timeout=5
            )
            return True
        except Exception as e:
            logging.warning(f"Error surfacing task (attempt {attempt+1}/3): {e}")
            if attempt == 2:
                logging.error(f"Failed to surface task after 3 attempts: {e}")
                raise e
            await asyncio.sleep(1)

async def surface_step(bot, chat_id, step_tuple, prefix="🛠️ Step:"):
    if len(step_tuple) == 3:
        step_id, description, task_id = step_tuple
        is_ai_offloadable = 0
    else:
        step_id, description, task_id, is_ai_offloadable = step_tuple
    
    keyboard_row = [
        InlineKeyboardButton("✅ Done", callback_data=f"done_{step_id}"),
        InlineKeyboardButton("🔄 Skip", callback_data=f"skip_{step_id}"),
        InlineKeyboardButton("❌ Not Now", callback_data=f"notnow_{step_id}"),
    ]
    
    if is_ai_offloadable:
        prefix = "🤖 " + prefix
        keyboard = [
            keyboard_row,
            [InlineKeyboardButton("🤖 Offload to AI", callback_data=f"offload_{step_id}")]
        ]
    else:
        keyboard = [keyboard_row]
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    for attempt in range(3):
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=f"{prefix} {description}",
                reply_markup=reply_markup,
                parse_mode="Markdown",
                connect_timeout=5,
                write_timeout=5,
                read_timeout=5
            )
            return True
        except Exception as e:
            logging.warning(f"Error surfacing step (attempt {attempt+1}/3): {e}")
            if attempt == 2:
                logging.error(f"Failed to surface step after 3 attempts: {e}")
                raise e
            await asyncio.sleep(1)

async def list_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contexts = database.get_all_contexts()
    magnitudes = database.get_all_magnitudes()
    durations = database.get_all_durations()
    tags = database.get_all_tags()
    ai_count = database.get_ai_offloadable_count()
    
    if not any([contexts, magnitudes, durations, tags, ai_count]):
        await update.message.reply_text("📭 Your task list is empty.")
        return

    msg = "📊 *Task Dashboard*\n\n"
    keyboard = []
    
    if ai_count > 0:
        msg += f"🤖 *AI-Offloadable:* {ai_count} steps\n\n"
        keyboard.append([InlineKeyboardButton("🤖 Pull AI Tasks", callback_data="pullai")])

    if contexts:
        msg += "*By Context:*\n"
        row = []
        for ctx, count in contexts:
            msg += f"• +{ctx} ({count})\n"
            row.append(InlineKeyboardButton(f"+{ctx}", callback_data=f"pullctx_{ctx}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row: keyboard.append(row)
        msg += "\n"

    if tags:
        msg += "*By Tag:*\n"
        row = []
        for tag, count in tags:
            msg += f"• {tag} ({count})\n"
            clean_tag = tag.replace('#','')
            row.append(InlineKeyboardButton(f"{tag}", callback_data=f"pulltag_{clean_tag}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row: keyboard.append(row)
        msg += "\n"

    if magnitudes:
        msg += "*By Size:*\n"
        row = []
        for mag, count in magnitudes:
            row.append(InlineKeyboardButton(f"{mag.capitalize()}", callback_data=f"pullmag_{mag}"))
        keyboard.append(row)
        msg += "\n"

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Handle Audit Actions
    if data.startswith("auditdelete_"):
        task_id = int(data.split("_")[1])
        database.delete_task(task_id)
        await present_audit_step(update, context)
        return
        
    if data.startswith("auditcomplete_"):
        task_id = int(data.split("_")[1])
        database.complete_task(task_id)
        await present_audit_step(update, context)
        return
        
    if data.startswith("auditkeep_"):
        task_id = int(data.split("_")[1])
        database.touch_task(task_id)
        await present_audit_step(update, context)
        return
        
    if data.startswith("auditnext_"):
        task_id = int(data.split("_")[1])
        if 'audit_skipped' not in context.user_data:
            context.user_data['audit_skipped'] = []
        context.user_data['audit_skipped'].append(task_id)
        await present_audit_step(update, context)
        return

    # Handle Dashboard/Message Pulls Selectors
    if data.startswith("selecttask_"):
        task_id = int(data.split("_")[1])
        task = database.get_task_by_id(task_id)
        if task:
            await query.edit_message_text(text="🎯 Pulling task...")
            await surface_task(context.bot, update.effective_chat.id, task, context)
        else:
            await query.edit_message_text(text="Error: Task not found.")
        return

    # Handle Dashboard Pulls
    if data == "pullai":
        tasks = database.get_tasks(limit=5, only_ai_offloadable=True)
        if tasks:
            await present_task_results(context.bot, update.effective_chat.id, tasks, update, context)
        else:
            await query.edit_message_text(text="No AI-offloadable tasks found.")
        return

    if data.startswith("pullctx_"):
        ctx_name = data.split("_")[1]
        tasks = database.get_tasks_by_context(ctx_name, limit=5)
        if tasks:
            await present_task_results(context.bot, update.effective_chat.id, tasks, update, context)
        else:
            await query.edit_message_text(text=f"No tasks for +{ctx_name}")
        return

    if data.startswith("pulltag_"):
        tag_name = data.split("_")[1]
        tasks = database.get_tasks_by_tag(tag_name, limit=5)
        if tasks:
            await present_task_results(context.bot, update.effective_chat.id, tasks, update, context)
        else:
            await query.edit_message_text(text=f"No tasks for #{tag_name}")
        return
        
    if data.startswith("pullmag_"):
        mag_name = data.split("_")[1]
        tasks = database.get_tasks_by_magnitude(mag_name, limit=5)
        if tasks:
            await present_task_results(context.bot, update.effective_chat.id, tasks, update, context)
        else:
            await query.edit_message_text(text=f"No tasks for size {mag_name}")
        return

    if data.startswith("offload_"):
        step_id = int(data.split("_")[1])
        await query.edit_message_text(text="🤖 *AI Agent working on this step...*", parse_mode="Markdown")
        try:
            step = database.get_step_by_id(step_id)
            if not step:
                await query.edit_message_text(text="Error: Step not found.")
                return
            _, step_desc, task_id, _ = step
            
            task = database.get_task_by_id(task_id)
            if not task:
                await query.edit_message_text(text="Error: Task not found.")
                return
            _, task_title, _, _, _, _ = task
            
            with database.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT raw_text FROM tasks WHERE id = ?", (task_id,))
                row = cursor.fetchone()
                raw_text = row[0] if row else task_title
                
            ai_output = ai_handler.offload_step(task_title, step_desc, raw_text)
            
            await query.edit_message_text(
                text=f"📋 *AI Output for step:*\n_{step_desc}_\n\n{ai_output}",
                parse_mode="Markdown"
            )
            
            follow_up_keyboard = [
                [
                    InlineKeyboardButton("✅ Complete Step", callback_data=f"done_{step_id}"),
                    InlineKeyboardButton("🔄 Keep Pending", callback_data=f"keep_{step_id}")
                ]
            ]
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Would you like to mark this step as completed?",
                reply_markup=InlineKeyboardMarkup(follow_up_keyboard)
            )
        except Exception as e:
            logging.error(f"Error during AI offloading: {e}")
            await query.edit_message_text(text=f"❌ AI Offloading failed: {str(e)}")
        return

    if data.startswith("keep_"):
        step_id = int(data.split("_")[1])
        database.reset_step_surface(step_id)
        await query.edit_message_text(text="🔄 Step kept pending. You can pull it again later.")
        return

    # Task/Step Actions
    parts = data.split('_')
    action = parts[0]
    id_val = int(parts[1])
    
    await process_action(action, id_val, update, context, is_query=True)

async def process_action(action, id_val, update, context, is_query=False):
    if action == "taskaccept":
        # Get the first step for this task
        next_step = database.get_next_step_for_task(id_val)
        if next_step:
            msg = "⚡ Task Accepted."
            if is_query: await update.callback_query.edit_message_text(text=msg)
            else: await update.message.reply_text(msg)
            await surface_step(context.bot, update.effective_chat.id, next_step)
        else:
            msg = "No pending steps found for this task."
            if is_query: await update.callback_query.edit_message_text(text=msg)
            else: await update.message.reply_text(msg)
        return

    if action == "taskskip":
        database.defer_task(id_val)
        msg = "⏭️ Task deferred."
        if is_query: await update.callback_query.edit_message_text(text=msg)
        else: await update.message.reply_text(msg)
        return

    if action == "taskcomplete":
        database.complete_task(id_val)
        msg = "🏁 Task and all steps completed."
        if is_query: await update.callback_query.edit_message_text(text=msg)
        else: await update.message.reply_text(msg)
        return

    if action == "taskdelete":
        database.delete_task(id_val)
        msg = "🗑️ Task deleted."
        if is_query: await update.callback_query.edit_message_text(text=msg)
        else: await update.message.reply_text(msg)
        return

    # Handle Step Actions
    row = database.get_step_by_id(id_val)
    
    if not row:
        msg = "Error: Step not found."
        if is_query: await update.callback_query.edit_message_text(text=msg)
        else: await update.message.reply_text(msg)
        return
        
    _, description, task_id = row

    if action == "done":
        database.mark_step_completed(id_val)
        msg = f"✅ Completed:\n{description}"
        if is_query: await update.callback_query.edit_message_text(text=msg)
        else: await update.message.reply_text(msg)
        
        # MOMENTUM: Look for the next step in the same task
        next_step = database.get_next_step_for_task(task_id)
        if next_step:
            await surface_step(context.bot, update.effective_chat.id, next_step)
    elif action == "skip":
        database.mark_step_skipped(id_val)
        msg = f"🔄 Skipped:\n{description}"
        if is_query: await update.callback_query.edit_message_text(text=msg)
        else: await update.message.reply_text(msg)
        
        # MOMENTUM: Look for the next step in the same task
        next_step = database.get_next_step_for_task(task_id)
        if next_step:
            await surface_step(context.bot, update.effective_chat.id, next_step)
        else:
            await update.message.reply_text("All steps for this task have been completed or skipped.")
    else:
        # 'notnow' action: return the step to the queue and defer the parent task
        database.defer_task(task_id)
        database.reset_step_surface(id_val)
        msg = "⏭️ Task deferred (Not Now)."
        if is_query: await update.callback_query.edit_message_text(text=msg)
        else: await update.message.reply_text(msg)

async def nudge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually trigger the morning nudge."""
    await update.message.reply_text("Generating nudge...")
    await daily_push(context.application, manual_chat_id=update.effective_chat.id)

async def nude_easter_egg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Easter Egg for /nudge typo."""
    import requests
    import io
    try:
        # Fetch a random cat from CATAAS (Cat as a Service)
        # Using the direct URL might be more robust if we download it
        response = requests.get("https://cataas.com/cat", timeout=10)
        if response.status_code == 200:
            # Wrap bytes in a file-like object
            photo_file = io.BytesIO(response.content)
            photo_file.name = "kitten.jpg"
            await update.message.reply_photo(
                photo=photo_file, 
                caption="Meow! I think you meant /nudge... but here's a kitten anyway. 🐈"
            )
        else:
            logging.warning(f"CATAAS returned status {response.status_code}")
            await update.message.reply_text("I couldn't find a kitten right now, but I know you meant /nudge! 🐈")
    except Exception as e:
        logging.error(f"Easter egg error: {e}")
        await update.message.reply_text("Meow! (I tried to find a kitten for your typo, but it ran away.) 🐈")

async def audit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually trigger task database cleanup/triage."""
    context.user_data['audit_skipped'] = []
    await present_audit_step(update, context)

async def present_audit_step(update, context):
    skipped_ids = context.user_data.get('audit_skipped', [])
    
    # Get active tasks older than 30 days
    stale_tasks = database.get_stale_tasks(days=30)
    
    # Filter out skipped ones
    remaining_tasks = [t for t in stale_tasks if t[0] not in skipped_ids]
    
    if not remaining_tasks:
        msg = "✨ *Audit complete!* No more stale tasks older than 30 days to review."
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(msg, parse_mode="Markdown", connect_timeout=5, write_timeout=5)
            except Exception:
                pass
        else:
            await update.message.reply_text(msg, parse_mode="Markdown")
        return
        
    task = remaining_tasks[0]
    task_id, title, ctx, dur, mag, tags_str = task
    total_stale = len(stale_tasks)
    reviewed_count = total_stale - len(remaining_tasks)
    
    text = (
        f"📋 *Task Audit ({reviewed_count + 1}/{total_stale})*\n"
        f"This task has been inactive for over 30 days. What should we do?\n\n"
        f"*{title}*\n"
        f"+{ctx} • {dur} • {mag}\n"
    )
    if tags_str:
        text += f"{' • '.join(tags_str.split(','))}\n"
        
    keyboard = [
        [
            InlineKeyboardButton("🗑️ Delete", callback_data=f"auditdelete_{task_id}"),
            InlineKeyboardButton("🏁 Complete", callback_data=f"auditcomplete_{task_id}"),
        ],
        [
            InlineKeyboardButton("⭐ Keep (Touch)", callback_data=f"auditkeep_{task_id}"),
            InlineKeyboardButton("⏭️ Next", callback_data=f"auditnext_{task_id}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown", connect_timeout=5, write_timeout=5)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown", connect_timeout=5, write_timeout=5)
    except Exception as e:
        logging.error(f"Error presenting audit step: {e}")

async def daily_push(application, manual_chat_id=None):
    target_chat_id = manual_chat_id or os.getenv("DAILY_PUSH_CHAT_ID")
    if not target_chat_id:
        logging.warning("Daily push skipped: No target chat ID.")
        return
        
    logging.info(f"Starting daily push for chat {target_chat_id}")
    try:
        # 1. Gather Reality Data
        weather = reality_handler.get_weather()
        calendar = reality_handler.get_today_events()
        
        # 2. Gather Task Summary
        contexts = database.get_all_contexts()
        summary_parts = [f"+{ctx} ({count})" for ctx, count in contexts]
        task_summary = ", ".join(summary_parts) if summary_parts else "No pending tasks."
        
        # 3. Generate Nudge via AI
        nudge_text = ai_handler.generate_morning_nudge(weather, calendar, task_summary)
        
        # 4. Send to user
        await application.bot.send_message(
            chat_id=target_chat_id,
            text=f"🌅 *Good Morning!*\n\n{nudge_text}",
            parse_mode="Markdown"
        )
        logging.info("Daily push sent successfully.")
    except Exception as e:
        logging.error(f"Error in daily push: {e}")
        if manual_chat_id:
            await application.bot.send_message(chat_id=manual_chat_id, text=f"❌ Nudge failed: {str(e)}")

async def check_schedules(application):
    """Checks for tasks that are due to be surfaced."""
    due_tasks = database.get_due_tasks()
    target_chat_id = os.getenv("DAILY_PUSH_CHAT_ID")
    
    if not due_tasks or not target_chat_id:
        return
        
    for task in due_tasks:
        await surface_task(application.bot, target_chat_id, task, None, prefix="⏰ Scheduled Task:")
        database.mark_task_scheduled_done(task[0])
    logging.info(f"Pushed {len(due_tasks)} scheduled tasks.")

async def run_pruning(application):
    try:
        count = database.prune_old_tasks(days=90)
        if count > 0:
            logging.info(f"Database pruned: permanently removed {count} tasks older than 90 days.")
    except Exception as e:
        logging.error(f"Error running database pruning: {e}")

async def post_init(application):
    # Scheduler
    scheduler = AsyncIOScheduler()
    # Runs at 06:00 daily
    scheduler.add_job(daily_push, CronTrigger(hour=6, minute=0), args=[application])
    # Runs every minute to check schedules
    scheduler.add_job(check_schedules, 'interval', minutes=1, args=[application])
    # Runs pruning daily at 03:00 AM
    scheduler.add_job(run_pruning, CronTrigger(hour=3, minute=0), args=[application])
    # Also run once immediately on startup to clean up right away!
    scheduler.add_job(run_pruning, 'date', run_date=datetime.now() + timedelta(seconds=10), args=[application])
    scheduler.start()
    logging.info("Scheduler started (06:00 daily + interval 1m + pruning daily 03:00).")

if __name__ == '__main__':
    database.init_db()
    
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("clear", clear_db))
    app.add_handler(CommandHandler("dash", list_dashboard))
    app.add_handler(CommandHandler("contexts", list_contexts))
    app.add_handler(CommandHandler("tags", list_tags))
    app.add_handler(CommandHandler("sizes", list_magnitudes))
    app.add_handler(CommandHandler("durations", list_durations))
    app.add_handler(CommandHandler("nudge", nudge_command))
    app.add_handler(CommandHandler("audit", audit_command))
    app.add_handler(CommandHandler("nude", nude_easter_egg))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("Bot is starting...")
    app.run_polling()
