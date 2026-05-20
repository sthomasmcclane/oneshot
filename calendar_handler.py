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

        # Get the start and end of today in local time, then convert to UTC for API
        from datetime import timezone
        now = datetime.datetime.now().astimezone()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        end = now.replace(hour=23, minute=59, second=59, microsecond=0).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

        # List all calendars
        calendar_list = service.calendarList().list().execute()
        calendar_items = calendar_list.get('items', [])
        
        # Build list of IDs to check
        ids_to_check = {item['id'] for item in calendar_items}
        
        # Add explicit IDs from environment variable
        env_ids = os.getenv("CALENDAR_IDS", "s.thomasmcclane@gmail.com")
        for eid in env_ids.split(','):
            eid = eid.strip()
            if eid:
                ids_to_check.add(eid)

        all_events = []

        for cal_id in ids_to_check:
            events_result = service.events().list(
                calendarId=cal_id, timeMin=start, timeMax=end,
                singleEvents=True, orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])
            
            for event in events:
                start_raw = event['start'].get('dateTime', event['start'].get('date'))
                end_raw = event['end'].get('dateTime', event['end'].get('date'))
                
                if 'T' in start_raw and 'T' in end_raw:
                    start_time = start_raw.split('T')[1][:5]
                    end_time = end_raw.split('T')[1][:5]
                    time_part = f"{start_time}-{end_time}"
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
