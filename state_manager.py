# === state_manager.py (Ensure new key handled) ===
import json
import os
import config

def save_state(current_state):
    """Saves the provided bot state dictionary to the JSON file."""
    try:
        with open(config.STATE_FILE, 'w') as f:
            json.dump(current_state, f, indent=4)
        # print(f"State saved: {current_state}") # Debug
    except Exception as e:
        print(f"!!! Error saving state: {e}")

def load_state():
    """Loads bot state from JSON file or returns initial state."""
    loaded_state = config.INITIAL_STATE.copy() # Start with default
    try:
        if os.path.exists(config.STATE_FILE):
            with open(config.STATE_FILE, 'r') as f:
                state_from_file = json.load(f)
                # Update default state with values from file, preserving all keys
                loaded_state.update(state_from_file)
                print(f"State loaded from {config.STATE_FILE}")
        else:
            print("State file not found, using default initial state.")
    except Exception as e:
        print(f"!!! Error loading state: {e}. Using default initial state.")
        loaded_state = config.INITIAL_STATE.copy() # Reset to default on error

    # Ensure all expected keys exist, even if file was old/malformed
    for key, default_value in config.INITIAL_STATE.items():
        if key not in loaded_state:
            loaded_state[key] = default_value

    return loaded_state