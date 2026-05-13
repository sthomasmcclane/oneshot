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

def test_pull(query_text):
    print(f"\n>>> Simulating message: '{query_text}'")
    text = query_text.lower().strip()
    
    # regex from bot.py
    ctx_match = re.search(r'@(\w+)', text)
    dur_match = re.search(r'(\d+[mh])', text)
    mag_match = re.search(r'\b(small|medium|large)\b', text, re.IGNORECASE)
    tags_found = re.findall(r'#(\w+)', text)
    
    # Marker-only check: strip markers and see if anything is left
    markers_text = re.sub(r'(@\w+|#\w+|\d+[mh]|\b(small|medium|large)\b)', '', text).strip()
    
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
                print(f"  - [{t[1]}] @{t[2]} | {t[3]} | {t[4]} | Tags: {t[5]}")
        else:
            print("MATCHED: None")
    else:
        print(f"RESULT: Not a Marker-only Pull (Remaining text: '{markers_text}')")

if __name__ == "__main__":
    setup_test_data()
    
    # 1. Single Context Pull
    test_pull("@office")
    
    # 2. Context + Duration
    test_pull("@home 15m")
    
    # 3. Size Pull
    test_pull("large")
    
    # 4. Single Tag
    test_pull("#ai")
    
    # 5. Multi-Tag Pull (Intersection)
    test_pull("#ai #coding")
    
    # 6. Complex Triple Filter
    test_pull("@office 1h #ai")
    
    # 7. Capture (Not a Pull)
    test_pull("Buy milk @home")
    
    # 8. No Match Case
    test_pull("@office 10m") 
    
    # Clean up test DB
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
