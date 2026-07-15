import os
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/tasks']
TOKEN_FILE = 'data/token.json'
TASK_LIST_TITLE = 'OneShot Tasks'

def get_service():
    """Authenticates and returns the Google Tasks service."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
        else:
            raise Exception("Valid token.json not found. Please run oauth_setup.py first.")
    return build('tasks', 'v1', credentials=creds)

def get_or_create_tasklist(service):
    """Finds the 'OneShot Tasks' list, or creates it if it doesn't exist."""
    results = service.tasklists().list(maxResults=50).execute()
    items = results.get('items', [])
    for item in items:
        if item['title'] == TASK_LIST_TITLE:
            return item['id']
            
    # Create it if not found
    new_list = service.tasklists().insert(body={'title': TASK_LIST_TITLE}).execute()
    return new_list['id']

def create_task(title, metadata, steps):
    """
    Creates a parent task with metadata in the notes, and adds steps as subtasks.
    metadata should be a dict containing context, duration, energy, etc.
    """
    service = get_service()
    tasklist_id = get_or_create_tasklist(service)
    
    # Format metadata for the notes field
    notes = (
        f"[Context: {metadata.get('context', 'none')}]\n"
        f"[Duration: {metadata.get('duration', 'unknown')}]\n"
        f"[Energy: {metadata.get('energy', 2)}]\n"
    )
    
    task_body = {
        'title': title,
        'notes': notes
    }
    
    parent_task = service.tasks().insert(tasklist=tasklist_id, body=task_body).execute()
    parent_id = parent_task['id']
    
    # Create subtasks (reversed so they appear in correct chronological order in the UI)
    for step in reversed(steps):
        step_desc = step.get('description', step) if isinstance(step, dict) else step
        is_ai = step.get('is_ai_offloadable', False) if isinstance(step, dict) else False
        
        prefix = "🤖 " if is_ai else ""
        subtask_body = {
            'title': f"{prefix}{step_desc}"
        }
        # Insert subtask and link to parent
        service.tasks().insert(tasklist=tasklist_id, body=subtask_body, parent=parent_id).execute()
        
    return parent_task

def get_active_tasks():
    """Retrieves all incomplete parent tasks and parses their metadata."""
    service = get_service()
    tasklist_id = get_or_create_tasklist(service)
    
    # Get all tasks (parents and subtasks are returned flat, with 'parent' fields)
    results = service.tasks().list(tasklist=tasklist_id, showCompleted=False, showHidden=False).execute()
    items = results.get('items', [])
    
    tasks_with_meta = []
    
    for item in items:
        # We only want parent tasks here (they don't have a 'parent' field)
        if 'parent' not in item:
            notes = item.get('notes', '')
            
            # Simple metadata extraction from notes
            meta = {
                'id': item['id'],
                'title': item['title'],
                'context': 'general',
                'duration': 'unknown',
                'energy': 2
            }
            
            import re
            ctx_match = re.search(r'\[Context: (.*?)\]', notes)
            dur_match = re.search(r'\[Duration: (.*?)\]', notes)
            eng_match = re.search(r'\[Energy: (\d+)\]', notes)
            
            if ctx_match: meta['context'] = ctx_match.group(1)
            if dur_match: meta['duration'] = dur_match.group(1)
            if eng_match: meta['energy'] = int(eng_match.group(1))
            
            tasks_with_meta.append(meta)
            
    return tasks_with_meta

def complete_task(task_id):
    """Marks a task as completed in Google Tasks."""
    service = get_service()
    tasklist_id = get_or_create_tasklist(service)
    
    task = service.tasks().get(tasklist=tasklist_id, task=task_id).execute()
    task['status'] = 'completed'
    service.tasks().update(tasklist=tasklist_id, task=task_id, body=task).execute()

def delete_task(task_id):
    """Deletes a task from Google Tasks."""
    service = get_service()
    tasklist_id = get_or_create_tasklist(service)
    service.tasks().delete(tasklist=tasklist_id, task=task_id).execute()
