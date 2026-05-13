import os
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
KEY_FILE = "data/google_credentials.json"

def get_today_events():
    """
    Fetches events for the current day from all shared calendars.
    """
    if not os.path.exists(KEY_FILE):
        return "Calendar access not configured (key file missing)."

    try:
        creds = service_account.Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
        service = build('calendar', 'v3', credentials=creds)

        # Get the start and end of today
        now = datetime.datetime.utcnow()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'
        end = now.replace(hour=23, minute=59, second=59, microsecond=0).isoformat() + 'Z'

        # List all calendars
        calendar_list = service.calendarList().list().execute()
        all_events = []

        for calendar_entry in calendar_list.get('items', []):
            cal_id = calendar_entry['id']
            events_result = service.events().list(
                calendarId=cal_id, timeMin=start, timeMax=end,
                singleEvents=True, orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])
            
            for event in events:
                start_time = event['start'].get('dateTime', event['start'].get('date'))
                # Extract simple time if possible
                if 'T' in start_time:
                    time_part = start_time.split('T')[1][:5]
                else:
                    time_part = "All Day"
                all_events.append(f"{time_part}: {event['summary']}")

        if not all_events:
            return "Your calendar is clear today."
        
        return "Today's Schedule: " + ", ".join(all_events)

    except Exception as e:
        return f"Error fetching calendar: {str(e)}"

if __name__ == "__main__":
    # Test
    print(get_today_events())
