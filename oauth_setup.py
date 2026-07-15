import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Scopes needed for Tasks and Calendar (if you want to pivot Calendar to use this too)
SCOPES = [
    'https://www.googleapis.com/auth/tasks',
    'https://www.googleapis.com/auth/calendar.readonly'
]

def authenticate():
    creds = None
    token_path = 'data/token.json'
    credentials_path = 'data/credentials.json'
    
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired credentials...")
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                print(f"Error: {credentials_path} not found.")
                print("Please download your OAuth 2.0 Client ID JSON file from Google Cloud Console and save it as data/credentials.json")
                return None
            
            print("Starting local browser for authentication...")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            # This opens a local web server to receive the auth code
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for the next run
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
            print(f"Authentication successful! Token saved to {token_path}")
            
    return creds

if __name__ == '__main__':
    print("Setting up OneShot V2 Google OAuth...")
    authenticate()
