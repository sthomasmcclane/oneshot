import sqlite3
from datetime import datetime
import os
import re
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "data/tasks.db")

@contextmanager
def get_db_connection():
    """Context manager for SQLite database connections."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()

def parse_duration(dur_str):
    """Converts duration strings like '1h 30m' or '15m' into total minutes."""
    if not dur_str or dur_str == 'unknown':
        return 9999 # Treat unknown as very long
    
    total_minutes = 0
    # Match patterns like "1h 30m", "45m", "2h"
    parts = re.findall(r'(\d+)([mh])', dur_str.lower())
    for val, unit in parts:
        if unit == 'h':
            total_minutes += int(val) * 60
        elif unit == 'm':
            total_minutes += int(val)
    
    return total_minutes if total_minutes > 0 else 9999

def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Tasks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                raw_text TEXT NOT NULL,
                context TEXT,
                duration TEXT,
                magnitude TEXT,
                tags TEXT,
                status TEXT DEFAULT 'active',
                last_deferred TIMESTAMP,
                last_active TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_urgent INTEGER DEFAULT 0,
                is_important INTEGER DEFAULT 0
            )
        ''')

        # Migration logic
        cursor.execute("PRAGMA table_info(tasks)")
        columns = [column[1] for column in cursor.fetchall()]
        migrations = [
            ('last_active', "ALTER TABLE tasks ADD COLUMN last_active TIMESTAMP"),
            ('title', "ALTER TABLE tasks ADD COLUMN title TEXT"),
            ('tags', "ALTER TABLE tasks ADD COLUMN tags TEXT"),
            ('status', "ALTER TABLE tasks ADD COLUMN status TEXT DEFAULT 'active'"),
            ('last_deferred', "ALTER TABLE tasks ADD COLUMN last_deferred TIMESTAMP"),
            ('scheduled_at', "ALTER TABLE tasks ADD COLUMN scheduled_at TIMESTAMP"),
            ('is_urgent', "ALTER TABLE tasks ADD COLUMN is_urgent INTEGER DEFAULT 0"),
            ('is_important', "ALTER TABLE tasks ADD COLUMN is_important INTEGER DEFAULT 0")
        ]
        for col, sql in migrations:
            if col not in columns:
                cursor.execute(sql)

        # Steps table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                sequence INTEGER,
                description TEXT NOT NULL,
                is_surfaced BOOLEAN DEFAULT 0,
                is_completed BOOLEAN DEFAULT 0,
                is_skipped BOOLEAN DEFAULT 0,
                surfaced_at TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks (id)
            )
        ''')
        
        # Migration logic for steps
        cursor.execute("PRAGMA table_info(steps)")
        columns = [column[1] for column in cursor.fetchall()]
        step_migrations = [
            ('is_completed', "ALTER TABLE steps ADD COLUMN is_completed BOOLEAN DEFAULT 0"),
            ('completed_at', "ALTER TABLE steps ADD COLUMN completed_at TIMESTAMP"),
            ('is_skipped', "ALTER TABLE steps ADD COLUMN is_skipped BOOLEAN DEFAULT 0")
        ]
        for col, sql in step_migrations:
            if col not in columns:
                cursor.execute(sql)
        
        # Startup: Reset any stuck 'surfaced' steps back to pending
        cursor.execute("UPDATE steps SET is_surfaced = 0 WHERE is_completed = 0")
        
        conn.commit()

def add_task(raw_text, title, context, duration, magnitude, steps_list, tags=None, scheduled_at=None, is_urgent=0, is_important=0):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO tasks (raw_text, title, context, duration, magnitude, tags, scheduled_at, is_urgent, is_important)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (raw_text, title, context, duration, magnitude, tags, scheduled_at, is_urgent, is_important))
            
            task_id = cursor.lastrowid
            
            for i, step_desc in enumerate(steps_list, 1):
                cursor.execute('''
                    INSERT INTO steps (task_id, sequence, description)
                    VALUES (?, ?, ?)
                ''', (task_id, i, f"{i:02d} - Step: {step_desc} (task: {title})"))
                
            conn.commit()
            return task_id
        except Exception as e:
            conn.rollback()
            raise e

def get_tasks(context=None, duration=None, magnitude=None, tags=None, limit=1):
    """
    Flexible task retrieval supporting multiple filters.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        query = '''
            SELECT DISTINCT t.id, t.title, t.context, t.duration, t.magnitude, t.tags
            FROM tasks t
            JOIN steps s ON t.id = s.task_id
            WHERE s.is_completed = 0 AND s.is_skipped = 0 AND t.status = 'active'
        '''
        params = []
        
        if context:
            query += " AND LOWER(t.context) = ?"
            params.append(context.lower())
        
        if magnitude:
            query += " AND LOWER(t.magnitude) = ?"
            params.append(magnitude.lower())
            
        if tags:
            # Expecting tags as a list of strings without #
            for tag in tags:
                query += " AND t.tags LIKE ?"
                params.append(f"%#{tag.lower()}%")
                
        # Ordering logic: Deferred tasks go to the back, sorted by priority (Important first, then Urgent)
        query += " ORDER BY (t.last_deferred IS NOT NULL) ASC, t.is_important DESC, t.is_urgent DESC, t.last_active DESC, t.last_deferred ASC, t.created_at ASC"
        
        cursor.execute(query, params)
        all_tasks = cursor.fetchall()
    
    filtered_tasks = []
    if duration:
        req_minutes = parse_duration(duration)
        for t in all_tasks:
            # t[3] is duration
            if parse_duration(t[3]) <= req_minutes:
                filtered_tasks.append(t)
                if len(filtered_tasks) >= limit:
                    break
    else:
        filtered_tasks = all_tasks[:limit]
                
    return filtered_tasks

def get_next_tasks(limit=1):
    """Wrapper for get_tasks without filters."""
    return get_tasks(limit=limit)

def get_task_by_id(task_id):
    """Gets a specific task by its ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, title, context, duration, magnitude, tags
            FROM tasks
            WHERE id = ?
        ''', (task_id,))
        return cursor.fetchone()

def get_tasks_by_context(context, limit=1):
    return get_tasks(context=context, limit=limit)

def get_tasks_by_magnitude(magnitude, limit=1):
    return get_tasks(magnitude=magnitude, limit=limit)

def get_tasks_by_duration(duration_str, limit=1):
    return get_tasks(duration=duration_str, limit=limit)

def get_tasks_by_tag(tag, limit=1):
    return get_tasks(tags=[tag], limit=limit)

def defer_task(task_id):
    """Mark a task as deferred so it isn't shown immediately again."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE tasks 
            SET last_deferred = ?
            WHERE id = ?
        ''', (now, task_id))
        conn.commit()

def mark_step_surfaced(step_id):
    """Mark a step as being shown to the user."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE steps 
            SET is_surfaced = 1, surfaced_at = ?
            WHERE id = ?
        ''', (now, step_id))
        conn.commit()

def mark_step_completed(step_id):
    """Mark a step as actually finished."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        
        # Get task_id for this step
        cursor.execute("SELECT task_id FROM steps WHERE id = ?", (step_id,))
        row = cursor.fetchone()
        if row:
            task_id = row[0]
            # Update step
            cursor.execute('''
                UPDATE steps 
                SET is_completed = 1, completed_at = ?, is_surfaced = 0
                WHERE id = ?
            ''', (now, step_id))
            # Update task activity
            cursor.execute('UPDATE tasks SET last_active = ? WHERE id = ?', (now, task_id))
        conn.commit()

def mark_step_skipped(step_id):
    """Mark a step as skipped so it's not shown again, but allows momentum."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE steps 
            SET is_skipped = 1, is_surfaced = 0
            WHERE id = ?
        ''', (step_id,))
        conn.commit()

def reset_step_surface(step_id):
    """Put a surfaced step back into the un-surfaced pool."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE steps 
            SET is_surfaced = 0, surfaced_at = NULL
            WHERE id = ?
        ''', (step_id,))
        conn.commit()

def _get_counts(field):
    """Helper to get counts grouped by a specific task field."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f'''
            SELECT t.{field}, COUNT(s.id) 
            FROM tasks t
            JOIN steps s ON t.id = s.task_id
            WHERE s.is_completed = 0 AND s.is_skipped = 0 AND t.status = 'active'
            GROUP BY t.{field}
            ORDER BY t.{field} ASC
        ''')
        return cursor.fetchall()

def get_all_contexts():
    return _get_counts('context')

def get_all_magnitudes():
    return _get_counts('magnitude')

def get_all_durations():
    return _get_counts('duration')

def get_next_step_for_task(task_id):
    """Gets the next un-completed and un-skipped step for a specific task."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, description, task_id 
            FROM steps 
            WHERE task_id = ? AND is_completed = 0 AND is_skipped = 0
            ORDER BY sequence ASC
            LIMIT 1
        ''', (task_id,))
        return cursor.fetchone()

def get_step_by_id(step_id):
    """Gets details for a specific step by its ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, description, task_id FROM steps WHERE id = ?", (step_id,))
        return cursor.fetchone()

def get_all_tags():
    """Returns a list of (tag, count) for all pending steps."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.tags 
            FROM tasks t
            JOIN steps s ON t.id = s.task_id
            WHERE s.is_completed = 0 AND s.is_skipped = 0 AND t.status = 'active' AND t.tags IS NOT NULL
        ''')
        rows = cursor.fetchall()
    
    tag_counts = {}
    for row in rows:
        # Better tag parsing
        tags_raw = row[0]
        if not tags_raw:
            continue
        # Split by comma or space, remove common artifacts
        tags = re.split(r'[,\s]+', tags_raw.replace('[','').replace(']','').replace('"','').replace("'",''))
        for t in tags:
            t = t.strip().lower()
            if t:
                # Remove leading # if present for internal counting, but let's keep consistency
                t = t.lstrip('#')
                tag_counts[t] = tag_counts.get(t, 0) + 1
                
    return sorted(tag_counts.items(), key=lambda x: x[0])

def get_due_tasks():
    """Finds tasks with a scheduled_at time that has passed but are still active."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('''
            SELECT DISTINCT t.id, t.title, t.context, t.duration, t.magnitude, t.tags
            FROM tasks t
            JOIN steps s ON t.id = s.task_id
            WHERE t.status = 'active' 
              AND t.scheduled_at IS NOT NULL 
              AND t.scheduled_at <= ?
              AND s.is_completed = 0
              AND s.is_skipped = 0
        ''', (now,))
        return cursor.fetchall()

def mark_task_scheduled_done(task_id):
    """Clears the scheduled_at field so the task isn't repeatedly pushed."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE tasks SET scheduled_at = NULL WHERE id = ?', (task_id,))
        conn.commit()

def complete_task(task_id):
    """Mark all steps of a task and the task itself as completed."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        try:
            cursor.execute('''
                UPDATE steps
                SET is_completed = 1, completed_at = ?, is_surfaced = 0
                WHERE task_id = ? AND is_completed = 0 AND is_skipped = 0
            ''', (now, task_id))
            cursor.execute('''
                UPDATE tasks
                SET status = 'completed', last_active = ?
                WHERE id = ?
            ''', (now, task_id))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e

def delete_task(task_id):
    """Mark a task status as deleted and reset any surfaced steps."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        try:
            cursor.execute('''
                UPDATE tasks
                SET status = 'deleted', last_active = ?
                WHERE id = ?
            ''', (now, task_id))
            cursor.execute('''
                UPDATE steps
                SET is_surfaced = 0
                WHERE task_id = ?
            ''', (task_id,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e

def prune_old_tasks(days=90):
    """Permanently deletes tasks and steps that were completed or deleted more than X days ago."""
    from datetime import timedelta
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        try:
            # First, find task IDs that match the criteria
            cursor.execute('''
                SELECT id FROM tasks
                WHERE status IN ('completed', 'deleted') AND last_active <= ?
            ''', (cutoff,))
            task_ids = [row[0] for row in cursor.fetchall()]
            
            if task_ids:
                # Placeholders for IN query
                placeholders = ','.join('?' for _ in task_ids)
                # Delete steps
                cursor.execute(f'DELETE FROM steps WHERE task_id IN ({placeholders})', task_ids)
                # Delete tasks
                cursor.execute(f'DELETE FROM tasks WHERE id IN ({placeholders})', task_ids)
                conn.commit()
                return len(task_ids)
            return 0
        except Exception as e:
            conn.rollback()
            raise e

def get_stale_tasks(days=30):
    """Gets active tasks that have been inactive/un-updated for more than X days."""
    from datetime import timedelta
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        cursor.execute('''
            SELECT DISTINCT t.id, t.title, t.context, t.duration, t.magnitude, t.tags
            FROM tasks t
            JOIN steps s ON t.id = s.task_id
            WHERE t.status = 'active'
              AND s.is_completed = 0
              AND s.is_skipped = 0
              AND t.created_at <= ?
              AND (t.last_active IS NULL OR t.last_active <= ?)
            ORDER BY t.created_at ASC
        ''', (cutoff, cutoff))
        return cursor.fetchall()

def touch_task(task_id):
    """Updates a task's last_active timestamp to today to show it was reviewed."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('UPDATE tasks SET last_active = ? WHERE id = ?', (now, task_id))
        conn.commit()

def clear_all_data():
    """Wipes all tasks and steps. Dangerous!"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM steps')
        cursor.execute('DELETE FROM tasks')
        conn.commit()

def reinstate_recent_steps(hours=48):
    """Returns recently surfaced steps back to the queue."""
    from datetime import timedelta
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        # Find steps
        cursor.execute('''
            SELECT id, description, surfaced_at 
            FROM steps 
            WHERE is_surfaced = 1 AND surfaced_at > ?
        ''', (cutoff,))
        recent_steps = cursor.fetchall()
        
        if recent_steps:
            cursor.execute('''
                UPDATE steps 
                SET is_surfaced = 0, surfaced_at = NULL 
                WHERE id IN (SELECT id FROM steps WHERE is_surfaced = 1 AND surfaced_at > ?)
            ''', (cutoff,))
            conn.commit()
            
        return recent_steps

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
