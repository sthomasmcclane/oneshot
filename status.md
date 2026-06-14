# Oneshot Tasks Status

### Current Status
* **Bot Status:** Operational and healthy (verified container logs).
* **API Key Verification:** Confirmed unlinked API key works successfully on the standard Free Tier.
* **Last Issue Fixed:** Fixed Telegram API timeout crashes by separating DB saves from UI edits, and wrapping surfacing logic in retry loops.
* **Deployment:** Applied to production container and rebuilt on 2026-06-15.
* **Billing Optimization:** Streamlined enabled GCP APIs in all projects on 2026-06-06 to prevent accidental charges.


---

### Recent Changes (2026-06-15)
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
