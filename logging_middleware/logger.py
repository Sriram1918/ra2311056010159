import requests
import os
from dotenv import load_dotenv

load_dotenv()

token = os.getenv('ACCESS_TOKEN')

def Log(stack, level, package, message):
    # sends log to server
    global token

    if not token:
        print("ERROR: No token found")
        return

    url = "http://20.207.122.201/evaluation-service/logs"

    data = {
        "stack": stack,
        "level": level,
        "package": package,
        "message": message
    }

    headers = {
        "Authorization": f"Bearer {token}"
    }

    try:
        r = requests.post(url, json=data, headers=headers)
        if r.status_code == 200:
            print(f"[{level}] logged: {message}")
            return r.json()
        else:
            print(f"log failed: {r.status_code}")
    except Exception as e:
        print(f"error sending log: {e}")
