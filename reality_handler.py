import requests
import json
import logging
import os
import calendar_handler

def get_weather():
    """Fetches a robust weather summary for the given location using wttr.in."""
    location = os.getenv("LOCATION", "Brisbane")
    try:
        response = requests.get(f"https://wttr.in/{location}?format=j1", timeout=10)
        data = response.json()
        
        # Current status
        current = data['current_condition'][0]
        curr_desc = current['weatherDesc'][0]['value']
        curr_temp = current['temp_C']
        
        # Daily outlook
        day = data['weather'][0]
        max_temp = day['maxtempC']
        min_temp = day['mintempC']
        
        # Determine overall condition from hourly data to be more representative
        hourly = day['hourly']
        descriptions = [h['weatherDesc'][0]['value'] for h in hourly]
        rain_chances = [int(h['chanceofrain']) for h in hourly]
        max_rain_chance = max(rain_chances)
        
        # Simple frequency-based summary
        from collections import Counter
        most_common_desc = Counter(descriptions).most_common(1)[0][0]
        
        summary = (
            f"Current: {curr_desc} ({curr_temp}°C). "
            f"Today's Outlook: {most_common_desc} with a high of {max_temp}°C and low of {min_temp}°C. "
            f"Max rain chance: {max_rain_chance}%."
        )
        return summary
    except Exception as e:
        logging.error(f"Weather error: {e}")
        return "Weather unavailable."

def get_today_events():
    """Passthrough to calendar_handler."""
    return calendar_handler.get_today_events()

def get_reality_summary():
    """Consolidates weather and calendar for the AI."""
    weather = get_weather()
    calendar = calendar_handler.get_today_events()
    return f"WEATHER: {weather} | CALENDAR: {calendar}"
