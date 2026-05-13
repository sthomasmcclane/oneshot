import database

def reinstate_recent_steps():
    recent_steps = database.reinstate_recent_steps(hours=48)
    
    if not recent_steps:
        print("No recently surfaced steps found to reinstate.")
        return
        
    print(f"Found {len(recent_steps)} steps to reinstate:")
    for s in recent_steps:
        # s is (id, description, surfaced_at)
        print(f"- {s[1]} (surfaced at {s[2]})")
        
    print("\n✅ Steps successfully returned to the queue.")

if __name__ == "__main__":
    reinstate_recent_steps()
