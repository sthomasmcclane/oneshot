# 🎯 OneShot Tasks

**The AI-First Task Manager for High-Speed Capture and Intelligent Pulling.**

OneShot Tasks is a minimalist, Telegram-based task manager designed for the "Getting Things Done" (GTD) philosophy. It removes the friction of task organization by using AI to decompose broad goals into actionable steps and providing a high-speed, marker-based filtering system.

---

## ✨ Features

### 1. High-Speed Capture
Just send a message to the bot. 
- **AI Decomposition**: Every task is automatically broken down into discrete, sequential steps using Gemini.
- **Auto-Metadata**: The AI infers context, duration, magnitude, and tags even if you don't explicitly provide them.
- **Inline Markers**: Use `@context`, `{N}m`, `small|medium|large`, or `#tag` directly in your capture message to override AI inference.
- **Intelligent Scheduling**: Add a schedule marker (e.g., `#schedule 15:30`, `tomorrow 9am`, or just `9am`) to have the bot automatically surface the task at that time.

### 2. The "Marker Pull" System
Stop digging through lists. Get the right task for the right moment.
- Send just the markers (e.g., `@laptop 15m #coding`) to instantly retrieve the highest-priority task matching those criteria.
- **Combined Filters**: Supports intersection filtering across Context, Duration, Magnitude, and Hashtags.

### 3. Reality Integration
- **Morning Nudges**: Every morning at 06:00, the bot synthesizes your weather, calendar, and pending tasks into a conversational nudge.
- **Context Awareness**: Suggestions are tailored to your actual schedule and environmental conditions (e.g., "It's sunny and your morning is clear, tackle those @yard tasks").

### 4. Minimalist Interface
- `/dash`: A unified dashboard for quick pulls by context, size, or tag.
- `/tags`: Overview of all active project hashtags.
- `/nudge`: Manually trigger a morning nudge (useful for testing or afternoon planning).

---

## 🛠️ Implementation Details

### Tech Stack
- **Language**: Python 3.10+
- **Bot Framework**: `python-telegram-bot`
- **Intelligence**: Google Gemini (via `google-generativeai`)
- **Database**: SQLite3 (Local, volume-mapped)
- **Scheduling**: `apscheduler`
- **Deployment**: Docker Compose

### Data Model
- **Tasks**: Stores high-level goals and metadata.
- **Steps**: Stores the AI-generated actionable sequence. A task is only "complete" when all its steps are finished.
- **Momentum Logic**: Completing a step immediately surfaces the next step in that project to maintain flow.

---

## 🚀 Installation & Setup

### Prerequisites
1.  **Telegram Bot Token**: Create one via [@BotFather](https://t.me/botfather).
2.  **Gemini API Key**: Obtain from [Google AI Studio](https://aistudio.google.com/).
3.  **Google Calendar API (Optional)**: A `google_credentials.json` file in the `data/` directory for calendar integration.

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

---
