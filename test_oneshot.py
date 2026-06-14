import os
import sys
import sqlite3
import re

# Since this script is now inside the source directory, we can import directly
# or ensure the current directory is in the path.
sys.path.append(os.getcwd())

import database

# Use a temporary test database
TEST_DB = "test_tasks.db"
database.DB_PATH = TEST_DB

def setup_test_data():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    database.init_db()
    
    # Add various tasks to test multi-filtering
    # add_task(raw_text, title, context, duration, magnitude, steps_list, tags=None)
    database.add_task("Fix the leaky faucet", "Faucet Fix", "home", "15m", "small", ["Find wrench", "Tighten nut"], tags="#plumbing")
    database.add_task("Write blog post about AI", "AI Blog", "office", "2h", "large", ["Outline", "Draft", "Edit"], tags="#ai,#writing")
    database.add_task("Buy groceries", "Groceries", "general", "45m", "medium", ["Milk", "Eggs", "Bread"], tags="#errands")
    database.add_task("Refactor Oneshot Bot", "Oneshot Refactor", "office", "1h", "large", ["Design", "Test", "Merge"], tags="#ai,#coding")
    database.add_task("Water plants", "Watering", "home", "5m", "small", ["Fill can", "Water"], tags="#garden")
    
    # Add structured AI offloadable tasks/steps
    database.add_task(
        "Write article about agent coding",
        "Agent Article",
        "office",
        "1h",
        "medium",
        [
            {"description": "Brainstorm topics", "is_ai_offloadable": True},
            {"description": "Draft content", "is_ai_offloadable": True},
            {"description": "Upload to CMS", "is_ai_offloadable": False}
        ],
        tags="#writing"
    )
    # Add manually forced AI task
    database.add_task(
        "Generate a workout plan [ai]",
        "Workout Generation",
        "home",
        "30m",
        "small",
        ["Plan routine", "Find videos"],
        tags="#fitness",
        force_ai_offloadable=True
    )

def test_pull(query_text):
    print(f"\n>>> Simulating message: '{query_text}'")
    text = query_text.lower().strip()
    
    # regex from bot.py
    ctx_match = re.search(r'\+(\w+)', text)
    dur_match = re.search(r'(\d+[mh])', text)
    mag_match = re.search(r'\b(small|medium|large)\b', text, re.IGNORECASE)
    tags_found = re.findall(r'#(\w+)', text)
    
    # Marker-only check: strip markers and see if anything is left
    markers_text = re.sub(r'(\+\w+|#\w+|\d+[mh]|\b(small|medium|large)\b)', '', text).strip()
    
    if not markers_text and (ctx_match or dur_match or mag_match or tags_found):
        print("RESULT: Detected as 'Marker-only Pull'")
        pull_ctx = ctx_match.group(1) if ctx_match else None
        pull_dur = dur_match.group(1) if dur_match else None
        pull_mag = mag_match.group(1).lower() if mag_match else None
        
        # Call the new database.get_tasks function
        tasks = database.get_tasks(context=pull_ctx, duration=pull_dur, magnitude=pull_mag, tags=tags_found, limit=5)
        
        if tasks:
            print(f"MATCHED: {len(tasks)} tasks")
            for t in tasks:
                print(f"  - [{t[1]}] +{t[2]} | {t[3]} | {t[4]} | Tags: {t[5]}")
        else:
            print("MATCHED: None")
    else:
        print(f"RESULT: Not a Marker-only Pull (Remaining text: '{markers_text}')")

def test_audit_and_pruning():
    print("\n>>> Testing Audit and Pruning functions...")
    setup_test_data()
    
    # Let's insert custom tasks directly with old timestamps
    from datetime import datetime, timedelta
    cutoff_35d = (datetime.now() - timedelta(days=35)).isoformat()
    cutoff_95d = (datetime.now() - timedelta(days=95)).isoformat()
    
    with database.get_db_connection() as conn:
        cursor = conn.cursor()
        # 1. Stale Active task (created 35 days ago, last_active 35 days ago or NULL)
        cursor.execute('''
            INSERT INTO tasks (title, raw_text, context, duration, magnitude, status, created_at, last_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ("Stale Task", "Do something stale", "home", "15m", "small", "active", cutoff_35d, cutoff_35d))
        stale_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO steps (task_id, sequence, description, is_completed, is_skipped)
            VALUES (?, ?, ?, 0, 0)
        ''', (stale_id, 1, "Step 1"))
        
        # 2. Prunable completed task (completed/last_active 95 days ago)
        cursor.execute('''
            INSERT INTO tasks (title, raw_text, context, duration, magnitude, status, created_at, last_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ("Old Completed Task", "Completed long ago", "office", "1h", "medium", "completed", cutoff_95d, cutoff_95d))
        old_completed_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO steps (task_id, sequence, description, is_completed)
            VALUES (?, ?, ?, 1)
        ''', (old_completed_id, 1, "Completed Step 1"))
        
        # 3. Old active task (created 95 days ago, last_active 95 days ago, but active!)
        # This should NOT be pruned because status is 'active'
        cursor.execute('''
            INSERT INTO tasks (title, raw_text, context, duration, magnitude, status, created_at, last_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ("Old Active Task", "Active long ago", "home", "2h", "large", "active", cutoff_95d, cutoff_95d))
        old_active_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO steps (task_id, sequence, description, is_completed)
            VALUES (?, ?, ?, 0)
        ''', (old_active_id, 1, "Active Step 1"))
        
        conn.commit()
        
    # Check stale tasks (should include Stale Task and Old Active Task, but not others)
    stale_tasks = database.get_stale_tasks(days=30)
    stale_titles = [t[1] for t in stale_tasks]
    print(f"Stale tasks older than 30 days: {stale_titles}")
    assert "Stale Task" in stale_titles, "Stale Task should be in stale tasks list"
    assert "Old Active Task" in stale_titles, "Old Active Task should be in stale tasks list"
    
    # Touch stale task
    database.touch_task(stale_id)
    stale_tasks_after = database.get_stale_tasks(days=30)
    stale_titles_after = [t[1] for t in stale_tasks_after]
    print(f"Stale tasks after touch: {stale_titles_after}")
    assert "Stale Task" not in stale_titles_after, "Touched task should no longer be stale"
    
    # Prune tasks older than 90 days
    pruned_count = database.prune_old_tasks(days=90)
    print(f"Pruned {pruned_count} tasks")
    assert pruned_count == 1, f"Expected 1 task to be pruned, got {pruned_count}"
    
    # Verify the database state
    with database.get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM tasks WHERE id = ?", (old_completed_id,))
        assert cursor.fetchone() is None, "Old completed task should be deleted"
        
        cursor.execute("SELECT id FROM steps WHERE task_id = ?", (old_completed_id,))
        assert cursor.fetchone() is None, "Steps for old completed task should be deleted"
        
        cursor.execute("SELECT id FROM tasks WHERE id = ?", (old_active_id,))
        assert cursor.fetchone() is not None, "Old active task should NOT be deleted"
        
    print(">>> Audit and Pruning tests passed successfully!")

def test_ai_offload():
    print("\n>>> Testing AI Offloadable Tasks & Steps...")
    # Get total AI count
    total_ai_steps = database.get_ai_offloadable_count()
    print(f"Total AI-offloadable steps: {total_ai_steps}")
    # Agent Article (2 steps) + Workout Generation (2 steps) = 4 steps
    assert total_ai_steps == 4, f"Expected 4 AI steps, got {total_ai_steps}"
    
    # Check task level helpers
    # Find task IDs
    with database.get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM tasks WHERE title = 'Agent Article'")
        article_task_id = cursor.fetchone()[0]
        cursor.execute("SELECT id FROM tasks WHERE title = 'Faucet Fix'")
        faucet_task_id = cursor.fetchone()[0]
        cursor.execute("SELECT id FROM tasks WHERE title = 'Workout Generation'")
        workout_task_id = cursor.fetchone()[0]
        
    assert database.task_has_ai_offloadable_steps(article_task_id) is True, "Agent Article should have AI-offloadable steps"
    assert database.task_has_ai_offloadable_steps(faucet_task_id) is False, "Faucet Fix should NOT have AI-offloadable steps"
    assert database.task_has_ai_offloadable_steps(workout_task_id) is True, "Workout Generation should have AI-offloadable steps"
    
    # Check get_next_step_for_task returns 4 elements and correct offloadable status
    next_step_article = database.get_next_step_for_task(article_task_id)
    print(f"Next step for Agent Article: {next_step_article}")
    # Should be a 4-tuple: (id, description, task_id, is_ai_offloadable)
    assert len(next_step_article) == 4, f"Expected next_step to be 4-tuple, got length {len(next_step_article)}"
    assert next_step_article[3] == 1, "First step of Agent Article should be AI-offloadable"
    
    # Check pull AI tasks
    ai_tasks = database.get_tasks(only_ai_offloadable=True, limit=5)
    ai_titles = [t[1] for t in ai_tasks]
    print(f"AI-offloadable tasks: {ai_titles}")
    assert "Agent Article" in ai_titles, "Agent Article should be in AI tasks pull"
    assert "Workout Generation" in ai_titles, "Workout Generation should be in AI tasks pull"
    assert "Faucet Fix" not in ai_titles, "Faucet Fix should NOT be in AI tasks pull"
    
    print(">>> AI Offload tests passed successfully!")

if __name__ == "__main__":
    setup_test_data()
    
    # 1. Single Context Pull
    test_pull("+office")
    
    # 2. Context + Duration
    test_pull("+home 15m")
    
    # 3. Size Pull
    test_pull("large")
    
    # 4. Single Tag
    test_pull("#ai")
    
    # 5. Multi-Tag Pull (Intersection)
    test_pull("#ai #coding")
    
    # 6. Complex Triple Filter
    test_pull("+office 1h #ai")
    
    # 7. Capture (Not a Pull)
    test_pull("Buy milk +home")
    
    # 8. No Match Case
    test_pull("+office 10m") 
    
    # 9. Test Audit and Pruning
    test_audit_and_pruning()
    
    # 10. Test AI Offload features
    test_ai_offload()
    
    # Clean up test DB
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

