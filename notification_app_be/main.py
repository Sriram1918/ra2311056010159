import requests
import os
import sys
from datetime import datetime
from fastapi import FastAPI

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from logging_middleware.logger import Log

load_dotenv()

app = FastAPI()

AUTH_TOKEN = os.getenv('ACCESS_TOKEN')
NOTIF_API = "http://20.207.122.201/evaluation-service/notifications"


WEIGHTS = {
    "Placement": 3,
    "Result": 2,
    "Event": 1
}


def get_notifications():
    Log("backend", "info", "service", "fetching notifications from server")
    res = requests.get(NOTIF_API, headers={"Authorization": f"Bearer {AUTH_TOKEN}"})
    if res.status_code != 200:
        Log("backend", "error", "service", f"notif api returned {res.status_code}")
        return []
    notifs = res.json().get("notifications", [])
    Log("backend", "info", "service", f"got {len(notifs)} notifications")
    return notifs


def calculate_score(notif):
   
    weight = WEIGHTS.get(notif["Type"], 0)

    try:
        created = datetime.strptime(notif["Timestamp"], "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        hours_old = (now - created).total_seconds() / 3600
    except Exception:
        hours_old = 9999  

    # multiply weight by 100 so priority matters more than age
    score = (weight * 100) - hours_old
    return score


def get_top_n(notifs, n=10):
    Log("backend", "debug", "service", f"calculating top {n} priority notifs")

    # add score to each notif
    scored = []
    for n_item in notifs:
        s = calculate_score(n_item)
        scored.append((s, n_item))

    # sort descending by score
    scored.sort(key=lambda x: x[0], reverse=True)

    top = [item[1] for item in scored[:n]]
    Log("backend", "info", "service", f"selected top {len(top)} notifications")
    return top


@app.get("/inbox")
def inbox():
    Log("backend", "info", "handler", "inbox request received")

    notifs = get_notifications()
    if not notifs:
        Log("backend", "error", "handler", "no notifications, returning empty")
        return {"inbox": []}

    top = get_top_n(notifs, 10)

    Log("backend", "info", "handler", "returning top 10 inbox items")
    return {"inbox": top, "count": len(top)}


if __name__ == "__main__":
    Log("backend", "info", "config", "running notification inbox script directly")
    notifs = get_notifications()
    top = get_top_n(notifs, 10)

    print("\n=== TOP 10 PRIORITY NOTIFICATIONS ===")
    for i, n in enumerate(top, 1):
        print(f"{i}. [{n['Type']}] {n['Message']} ({n['Timestamp']})")
