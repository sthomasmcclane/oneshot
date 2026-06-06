import os
import json
from datetime import datetime
from google import genai

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

# Use the 2.5 Flash model for consistency
MODEL_ID = 'gemini-2.5-flash'

def decompose_task(task_text):
    """
    Asks Gemini to break a task into discrete steps.
    Returns a list of strings (steps).
    """
    prompt = f"""
    You are a task management expert. Break the following task into discrete, sequential, and actionable steps.
    Each step should be clear and concise. 
    
    Task: {task_text}
    
    Return the steps ONLY as a JSON array of strings. 
    Example format: ["Step 1 description", "Step 2 description"]
    """
    
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt
    )
    # Attempt to parse JSON from the response
    content = response.text.strip()
    # Handle cases where Gemini wraps JSON in markdown blocks
    if content.startswith("```json"):
        content = content.split("```json")[1].split("```")[0].strip()
    elif content.startswith("```"):
        content = content.split("```")[1].split("```")[0].strip()
        
    steps = json.loads(content)
    return steps

def extract_metadata(task_text):
    """
    Analyzes task text to extract metadata and a concise title.
    """
    prompt = f"""
    Analyze the following task and extract or infer the following parameters:
    1. Concise Title: A short, actionable version of the task.
    2. Context: (e.g., office, house, shed, car, shops, laptop) - single word.
    3. Duration: (e.g., 15m, 1h, 4h).
    4. Magnitude: (small, medium, large).
    5. Tags: Extract any hashtags from the text (e.g., #git, #shopping).
    6. Schedule: Extract any time-based scheduling information (e.g., "#schedule 15:30", "tomorrow 9am", "9am", "at 4pm", "tonight"). Convert this to an ISO 8601 timestamp string (e.g., "2026-05-11T15:30:00"). Use the current date and time as a reference: {datetime.now().isoformat()}. If the user provides a time without a date, assume today. If the time has already passed today, assume tomorrow. If no schedule is found, return null.
    
    Task: {task_text}
    
    Return the result ONLY as a JSON object.
    Example: {{"title": "Order batteries", "context": "office", "duration": "30m", "magnitude": "small", "tags": ["#electronics", "#shopping"], "scheduled_at": "2026-05-11T15:30:00"}}
    """
    
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt
    )
    content = response.text.strip()
    if content.startswith("```json"):
        content = content.split("```json")[1].split("```")[0].strip()
    elif content.startswith("```"):
        content = content.split("```")[1].split("```")[0].strip()
        
    metadata = json.loads(content)
    return metadata

def generate_morning_nudge(weather_data, calendar_data, task_summary):
    """
    Synthesizes reality data into a conversational morning nudge.
    """
    prompt = f"""
    You are a supportive personal assistant. It is 06:00 AM. 
    Review the following reality data and write a short, conversational morning nudge for the user.
    Do NOT use headings, bold labels, or bullet points. Use 2-3 sentences of cohesive prose.
    
    WEATHER: {weather_data}
    CALENDAR: {calendar_data}
    PENDING TASKS: {task_summary}
    
    GUIDELINES:
    1. Be nuanced with weather. If current is sunny but forecast says patchy rain, don't dismiss the whole day as "rainy".
    2. Provide a gentle, realistic suggestion for the day's focus based on his schedule and the weather.
    3. Keep it encouraging but brief.
    
    Example: Good morning! It's looking like a clear day in Brisbane and your calendar is relatively light, so it might be a perfect time to tackle some of those @yard tasks before it gets too hot. Otherwise, you've got plenty of @laptop items ready whenever you're settled.
    """
    
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"Error generating nudge: {e}")
        return "Good morning! I had trouble reaching the AI, but I hope you have a productive day."
