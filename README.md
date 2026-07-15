# 🎯 OneShot Tasks V2

**The AI-First Task Manager for High-Speed Capture and Intelligent Surfacing.**

OneShot Tasks is a minimalist, Telegram-based task manager designed around a "Zero Syntax" GTD philosophy. It removes the friction of task organization by using AI to decompose broad goals into actionable steps, securely syncing them directly to Google Tasks.

---

## ✨ Features

### 1. Zero-Syntax High-Speed Capture
Just send a natural language message to the bot (e.g., "Mow the lawn and trim the hedges"). 
- **AI Decomposition**: The task is automatically broken down into discrete, sequential steps using Gemini.
- **Implicit Metadata**: The AI infers Context (home, office, errands), Duration, and the Physical/Mental Energy Required (1-3 scale) entirely from context. No `#hashtags` or `+markers` needed.
- **Google Tasks Sync**: The parent task and its decomposed steps are instantly saved as native tasks and subtasks in a dedicated "OneShot Tasks" list in your personal Google account. Metadata is neatly stored in the task notes.

### 2. The "Now" View (Empathy Surfacing)
Stop digging through lists and experiencing decision fatigue.
- Send a simple period (`.`) or type `now` to the bot.
- The bot queries your active Google Tasks and uses an empathy algorithm to surface **exactly one** high-leverage task you can do right now based on time of day and inferred energy.
- Accept and complete it directly via inline Telegram buttons, or skip it to get a new suggestion.

### 3. Reality Integration
- **Morning Nudges**: Every morning at 06:00, the bot synthesizes your weather, calendar, and pending tasks into a conversational nudge (e.g., "It's sunny and your morning is clear, tackle those yard tasks").

### 4. Shiny Object Incubator
Combat "Shiny Object Syndrome" by quarantining new project ideas so they don't distract you.
- **Auto-Detection & Flags**: Gemini infers if a task is a shiny new project, or you can explicitly flag it by starting your message with `idea:` (e.g., `idea: Build a laser cutter`).
- **30-Day Maturation**: The bot bypasses decomposition and quietly places the idea in a separate "Incubator" Google Tasks list with a 30-day maturity timer.
- **Accountability Nudge**: After 30 days, the bot's morning job will ping you via Telegram. You can then `✅ Start Project` (which decomposes it into actionable steps and moves it to active tasks) or `🗑️ Trash it`.

---

## 🛠️ Implementation Details

### Tech Stack
- **Language**: Python 3.10+
- **Bot Framework**: `python-telegram-bot`
- **Intelligence**: Google Gemini (via `google-genai`)
- **Storage**: Google Tasks API (OAuth 2.0 User Credentials)
- **Scheduling**: `apscheduler`
- **Deployment**: Docker Compose

---

## 🚀 Installation & Setup

### Prerequisites
1.  **Telegram Bot Token**: Create one via [@BotFather](https://t.me/botfather).
2.  **Gemini API Key**: Obtain from [Google AI Studio](https://aistudio.google.com/).
3.  **Google OAuth Credentials**: 
    - Create a Desktop OAuth Client ID in Google Cloud Console.
    - Save the downloaded JSON as `data/credentials.json`.
    - Run `python3 oauth_setup.py` locally to authenticate and generate `data/token.json`.

### Docker Deployment
1.  Clone the repository.
2.  Create a `.env` file based on the environment variables in `compose.yaml`:
    ```env
    TELEGRAM_BOT_TOKEN=your_token_here
    GEMINI_API_KEY=your_key_here
    DAILY_PUSH_CHAT_ID=your_telegram_id
    AUTHORIZED_USER_ID=your_telegram_id
    ```
3.  Launch the container:
    ```bash
    docker compose up -d --build
    ```
