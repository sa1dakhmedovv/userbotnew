import json
import os

CONFIG_FILE = 'data/config.json'

# Config faylini o'qish
def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

# Config faylini yozish
def save_config(data):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# Session qo'shish yoki yangilash
def add_or_update_session(session_name, session_data):
    config = load_config()
    config[session_name] = session_data
    save_config(config)

# Session o'chirish
def remove_session(session_name):
    config = load_config()
    if session_name in config:
        del config[session_name]
        save_config(config)

# Sessionlar ro'yxatini olish
def list_sessions():
    return load_config()

# Sessionni olish
def get_session(session_name):
    return load_config().get(session_name)
