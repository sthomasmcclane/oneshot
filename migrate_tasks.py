import sqlite3
import tasks_handler
import logging
import time

logging.basicConfig(level=logging.INFO)

DB_PATH = '/opt/docker/appdata/oneshot-tasks/tasks.db'

def migrate():
    print(f"Connecting to legacy database at {DB_PATH}...")
    try:
        conn = sqlite3.connect(DB_PATH)
    except sqlite3.OperationalError:
        print(f"Error: Could not open {DB_PATH}. Check permissions.")
        return
        
    cursor = conn.cursor()
    
    # Get all active tasks
    cursor.execute('''
        SELECT id, title, context, duration, magnitude 
        FROM tasks 
        WHERE status = 'active'
    ''')
    active_tasks = cursor.fetchall()
    
    print(f"Found {len(active_tasks)} active tasks in SQLite.")
    
    success_count = 0
    for task in active_tasks:
        task_id, title, context, duration, magnitude = task
        
        # Get active steps for this task
        cursor.execute('''
            SELECT description, is_ai_offloadable 
            FROM steps 
            WHERE task_id = ? AND is_completed = 0 AND is_skipped = 0
            ORDER BY sequence ASC
        ''', (task_id,))
        steps_raw = cursor.fetchall()
        
        if not steps_raw:
            print(f"Skipping task '{title}' (no active steps).")
            continue
            
        steps = []
        for desc, is_ai in steps_raw:
            steps.append({
                'description': desc,
                'is_ai_offloadable': bool(is_ai)
            })
            
        # Map old DB values to new metadata format.
        # Since 'Energy' didn't exist, we default to 2 (Medium)
        metadata = {
            'context': context if context else 'general',
            'duration': duration if duration else 'unknown',
            'energy': 2
        }
        
        print(f"Migrating: {title} ({len(steps)} steps)...")
        try:
            tasks_handler.create_task(title, metadata, steps)
            success_count += 1
            # Sleep briefly to avoid Google Tasks API rate limits on bulk inserts
            time.sleep(1)
        except Exception as e:
            print(f"Failed to migrate task '{title}': {e}")
            
    print(f"Migration complete! Successfully synced {success_count} tasks to Google Tasks.")

if __name__ == '__main__':
    migrate()
