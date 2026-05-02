import requests
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from dotenv import load_dotenv
from logging_middleware.logger import Log

load_dotenv()

app = FastAPI()

AUTH_TOKEN = os.getenv('ACCESS_TOKEN')
API_BASE = "http://20.207.122.201/evaluation-service"


def get_depots():
    Log("backend", "info", "service", "hitting depots endpoint")
    url = f"{API_BASE}/depots"
    res = requests.get(url, headers={"Authorization": f"Bearer {AUTH_TOKEN}"})
    if res.status_code == 200:
        return res.json()["depots"]
    Log("backend", "error", "service", f"depots api gave {res.status_code}, something went wrong")
    return []


def get_vehicles():
    Log("backend", "info", "service", "hitting vehicles api")
    url = f"{API_BASE}/vehicles"
    res = requests.get(url, headers={"Authorization": f"Bearer {AUTH_TOKEN}"})
    if res.status_code == 200:
        return res.json()["vehicles"]
    Log("backend", "error", "service", f"vehicles api gave {res.status_code}")
    return []

def pick_best_tasks(tasks, max_hours):
    Log("backend", "debug", "service", f"starting dp, available hours = {max_hours}")
    n = len(tasks)

    dp = [[0] * (max_hours + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        hrs = tasks[i-1]["Duration"]
        score = tasks[i-1]["Impact"]
        for h in range(max_hours + 1):
            if hrs > h:
                dp[i][h] = dp[i-1][h]
            else:
                dp[i][h] = max(dp[i-1][h], dp[i-1][h - hrs] + score)

    # backtrack to see which tasks were picked
    chosen = []
    h = max_hours
    for i in range(n, 0, -1):
        if dp[i][h] != dp[i-1][h]:
            chosen.append(tasks[i-1]["TaskID"])
            h -= tasks[i-1]["Duration"]

    Log("backend", "debug", "service", f"dp done, picked {len(chosen)} tasks")
    return chosen, dp[n][max_hours]


@app.get("/schedule")
def schedule():
    Log("backend", "info", "handler", "got request to /schedule")

    depots = get_depots()
    vehicles = get_vehicles()

    if not depots or not vehicles:
        Log("backend", "error", "handler", "depots or vehicles empty, cant proceed")
        return {"error": "could not get data"}

    Log("backend", "info", "handler", f"{len(depots)} depots, {len(vehicles)} vehicles fetched")

    final = []
    for d in depots:
        budget = d["MechanicHours"]
        Log("backend", "debug", "service", f"depot {d['ID']}, budget is {budget}hrs")

        picked, impact = pick_best_tasks(vehicles, budget)
        hours_used = sum(v["Duration"] for v in vehicles if v["TaskID"] in picked)

        Log("backend", "info", "service", f"depot {d['ID']} done, impact={impact}, used {hours_used}/{budget} hrs")

        final.append({
            "depotID": d["ID"],
            "budgetHours": budget,
            "hoursUsed": hours_used,
            "impactScore": impact,
            "tasks": picked
        })

    Log("backend", "info", "handler", "done processing all depots")
    return {"result": final}
