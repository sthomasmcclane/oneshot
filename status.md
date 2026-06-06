# Oneshot Tasks Status

### Current Status
* **Bot Status:** Operational and healthy.
* **Last Issue Fixed:** Fixed UnboundLocalError when Gemini API rate limiting (429) occurs.
* **Deployment:** Applied to production container and rebuilt on 2026-06-06.

---

### Recent Changes (2026-06-06)
* **Bug Fix:** Fixed an unbound reference to `response` inside `ai_handler.py`'s exception handler.
* **Graceful API Fallback:**
  * When Gemini API rate limits (429) or other API exceptions occur, the bot now falls back to saving the task exactly as entered without crashing.
  * Fallback tasks are automatically assigned the context `@fallback` and have their duration/size/steps details omitted for easy review and clean logging.
  * Confirmed Telegram notifications will display `@fallback` and the raw text without size/step info.
