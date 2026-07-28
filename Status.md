# Oneshot Tasks Status

### Current Status
* **Bot Status:** Pivoted to V2 Architecture (Google Tasks Backend + Zero Syntax).
* **API Key Verification:** Confirmed unlinked API key works successfully on the standard Free Tier.
* **Storage backend:** Google Tasks API (OAuth 2.0 user credentials). Local SQLite `database.py` deprecated.
* **Deployment:** V2 changes successfully deployed to `/opt/docker/`.

---

### Recent Changes (2026-07-21) - Energy Profiler MVP
* **Energy & Mood Profiler:** Implemented a background-polling mechanism in `bot.py` via `APScheduler` to check in on the user's energy levels (🔋, 🪫, 🧠, 🌫️).
* **Strict Timezone Handling:** Polling is explicitly tied to Brisbane time (`ZoneInfo("Australia/Brisbane")`) and restricted to waking hours (9:00 AM, 1:00 PM, 5:00 PM, 9:00 PM) to avoid disruptive night-time notifications.
* **Database Tracking:** Re-activated `database.py` functionality exclusively for logging these check-ins to an `energy_logs` table, allowing us to build a baseline profile over time.

### Recent Changes (2026-07-16) - V2 Overhaul
* **Shiny Object Incubator**: Added a dedicated flow for capturing non-urgent project ideas. Ideas (auto-detected or manually flagged with `idea:`) bypass decomposition and are sent to a separate "Incubator" Google Tasks list. A 30-day scheduled job automatically pings the user via Telegram to either officially start the project (which then decomposes and promotes it) or trash it.
* **Google Tasks Pivot**: Removed SQLite (`database.py`) and integrated `tasks_handler.py` to sync all tasks and decomposed steps directly to the user's personal Google Tasks list ("OneShot Tasks").
* **Zero Syntax Capture**: Updated `ai_handler.py` to infer all metadata (Context, Duration, Energy Required) purely from natural language. Explicit syntax markers are no longer required.
* **The "Now" View**: Completely overhauled `bot.py` to remove `/dash` and manual pull logic. Sending a `.` to the bot now automatically evaluates active tasks in Google Tasks and surfaces exactly one optimized task.
* **OAuth 2.0 Auth Flow**: Added `oauth_setup.py` to generate user-level `token.json` credentials for full access to the Google Tasks API (since Service Accounts cannot access personal task lists).

### Recent Changes (2026-06-15)
* **Reply-to-Done / Triage (`done` / `delete`)**:
  - Implemented the ability to explicitly reply (e.g. swipe to reply or long-press > Reply) to a task-confirmation message to mark the entire task completed or delete it.
  - Replying with anything else surfaces the inline action keyboard for that task.
  - Updated the in-bot `/help` text and [README.md](file:///home/scott/git/oneshot/README.md) documentation.
* **Single Step Bypass (`[single]` / `#single`)**:
  - Implemented the ability to bypass AI decomposition and add a task as a single step.
  - Filtered markers from clean task text and verified with a new unit test suite in [test_oneshot.py](file:///home/scott/git/oneshot/test_oneshot.py).
  - Updated [README.md](file:///home/scott/git/oneshot/README.md) marker list.
* **AI Task Offloading (`[ai]` / `#ai` / `🤖 Offload to AI`)**:
  - Implemented automatic step-by-step AI-offloadability evaluation during decomposition using Gemini (`ai_handler.py`).
  - Added support for explicit manual markers `[ai]` and `#ai` during task capture to force all steps as AI-offloadable.
  - Added `🤖 Offload to AI` inline keyboard button for surfaced steps. When clicked, it drafts the material using Gemini and prompts the user to complete the step.
  - Added dashboard integration showing pending AI-offloadable steps and a `🤖 Pull AI Tasks` button, plus `ai` keyword support in search filters.
  - Added migration column `is_ai_offloadable` (INTEGER) to the `steps` table schema.
  - Executed a retroactive batch classification script to update all 149 active steps, identifying and updating **93 steps** as AI-offloadable.

### Recent Changes (2026-06-08)
* **Telegram Timeout Crash Fix & Retries**:
  * Separated local database insertion (SQLite) from UI updates so network failures do not falsely report as DB errors or crash task captures.
  * Wrapped `surface_task` and `surface_step` in 3-attempt retry loops with explicit 5-second connect/read/write timeouts to handle transient Telegram API lags.
* **Context Prefix Shift (`@` ➔ `+`)**:
  * Shifted the task context prefix from `@` to `+` (e.g. `+laptop`) to prevent native Telegram UI from rendering them as clickable username links.
* **Eisenhower Priority Matrix (`!u`/`!i`/`!ui`)**:
  * Implemented priority markers: `!u` (Urgent), `!i` (Important), `!ui`/`!iu` (Urgent & Important).
  * Added database support (`is_urgent`, `is_important` columns with migration) and updated the query ordering to prioritize tasks by matrix quadrant (Q1 ➔ Q2 ➔ Q3 ➔ Q4).
  * Included Gemini-powered priority auto-inference in metadata extraction if markers are omitted, with manual markers acting as overrides.
* **Interactive Pull Menus**:
  * Direct pulls and dashboard selections now query up to 5 matching tasks. If multiple tasks match, the bot presents a numbered selection menu with inline buttons instead of randomly picking a task.
* **Top-Level Task Controls**:
  * Added `Complete All` and `Delete` buttons next to `Accept`/`Not Now` on surfaced task cards, instantly database-marking them and updating dashboard counts.
* **Database Pruning & Stale Task Auditing**:
  * Added `/audit` command to manually triage active tasks that have been inactive for over 30 days, using a session-isolated skipped task list.
  * Implemented a daily database pruning task (running at 03:00 AM and once on startup) that permanently deletes tasks marked `'completed'` or `'deleted'` older than 90 days.
* **Documentation & Staging Cleanup**:
  * Updated `README.md` and `/help` command text.
  * Edited `GEMINI.md` to remove all references to the obsolete `oneshot_stage` staging area.

### Recent Changes (2026-06-06)
* **Bug Fix:** Fixed an unbound reference to `response` inside `ai_handler.py`'s exception handler.
* **Graceful API Fallback:**
  * When Gemini API rate limits (429) or other API exceptions occur, the bot now falls back to saving the task exactly as entered without crashing.
  * Fallback tasks are automatically assigned the context `@fallback` and have their duration/size/steps details omitted for easy review and clean logging.
  * Confirmed Telegram notifications will display `@fallback` and the raw text without size/step info.
* **GCP API Audit & Cleanup:**
  * Streamlined enabled APIs across all projects linked to the shared billing account (`018791-6FD35D-B436D9`) to prevent unexpected prepayment credit depletion.
  * **rclone-491307 (RClone):** Disabled Cloud Storage, BigQuery, and Dataform/Dataplex APIs (retained only Google Drive API).
  * **sublime-vial-474408-f6 (GEM Tool):** Disabled Cloud Storage, BigQuery, Custom Search, and Text-to-Speech APIs.
  * **oneshotbot (OneShotBot):** Disabled Cloud Storage, BigQuery, and Dataform/Dataplex APIs (retained only Google Calendar API).
  * **gen-lang-client-0810836254 (Gemini CLI Personal):** Verified clean state (only Gemini API enabled).

---

### 🚨 Critical Rethink: Energy-Aware Surfacing
Based on months of real-world use, frictionless capture is working, but task surfacing is ineffective. The bot surfaces tasks without regarding the user's biological reality (e.g., suggesting "Mow the lawn" on a Saturday morning when the user is historically drained). 

**The Plan for Oneshot V2 Surfacing & ADHD Accommodation:**
*The core philosophy: The system must work despite inconsistent use and must not require consistency to function. Remove the need to use features correctly.*

1. **The Energy & Mood Profiler:** Implement an adaptive, background-polling mechanism (via APScheduler and inline keyboards: 🔋, 🪫, 🧠, 🌫️). The polling frequency will decay over time as the bot builds a reliable baseline profile of the user's weekly energy fluctuations.
2. **Implicit Tagging (Zero New Syntax):** Update the Gemini decomposition step to automatically rate the physical/mental energy required (1-3), infer the context (work/personal) from the time/calendar, and estimate the duration, eliminating the need for manual markers like `+work {30}m`.
3. **The "Now" View as Default (Empathy Algorithm):** When opening the bot or sending a simple `.`, it surfaces exactly *one* highest-priority task you can do right now based on time, location, and inferred energy. No lists, no choices.
4. **Shame-Free Decay (DONE):** After 14 days of inactivity, tasks automatically archive to a "someday" pile so they don't accumulate guilt-debt. A monthly, pressure-free review prompt will summarize what was archived.
5. **Automatic Rescue:** If a specific context pull (like `+work`) yields zero results, the bot silently searches for unmarked tasks mentioning work keywords or overdue tasks, offering them instead of a blank screen.
6. **Sequential Step Surfacing (Option B Accountability):** Instead of a rigid timer, the bot naturally proves user engagement by surfacing the task's decomposed steps one by one. *Note: Task steps are now hardcoded with numerical prefixes during creation (e.g., `01 - `) to harden sequential surfacing against backward/reversed bulk uploads into Google Tasks.*
7. ~~**One-Tap Focus & Escalation:**~~ *(WILL NOT IMPLEMENT. Replaced by Sequential Step Surfacing above, which naturally measures engagement far more effectively without redundant timer notifications.)*
