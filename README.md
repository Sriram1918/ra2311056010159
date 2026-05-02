# Backend Assessment

A backend assessment project built with Python and FastAPI. Contains three modules — a logging middleware, a vehicle maintenance scheduler, and a campus notification system.

---

## Tech Stack

- Python 3.12
- FastAPI
- Uvicorn
- Requests
- Python-dotenv

---

## Project Structure

```
├── logging_middleware/        # reusable logging package
│   ├── __init__.py
│   └── logger.py
├── vehicle_scheduler/         # vehicle maintenance optimization API
│   └── main.py
├── notification_app_be/       # campus notification priority inbox
│   └── main.py
├── notification_system_design.md   # system design document (stages 1-6)
├── screenshots/               # output screenshots
├── requirements.txt
└── .gitignore
```

---

## Setup

**1. Clone the repo:**
```bash
git clone https://github.com/Sriram1918/ra2311056010159.git
cd ra2311056010159
```

**2. Install dependencies:**
```bash
pip install -r requirements.txt
```

**3. Create a `.env` file in the root:**
```
ACCESS_TOKEN=your_token_here
```

---

## Modules

### 1. Logging Middleware

A reusable logging package that sends structured logs to an external evaluation server.

**Usage:**
```python
from logging_middleware.logger import Log

Log("backend", "info", "handler", "server started on port 8000")
Log("backend", "error", "db", "database connection failed")
```

Supported levels: `debug`, `info`, `warn`, `error`, `fatal`

Supported packages: `handler`, `service`, `db`, `controller`, `repository`, `route`, `middleware`, `config`, `utils`

---

### 2. Vehicle Maintenance Scheduler

A FastAPI service that figures out the best set of vehicle maintenance tasks to complete for each depot within their available mechanic-hour budget.

**Problem:** Each depot has a limited number of mechanic hours per day. There are many vehicles needing maintenance, each with a time requirement and an importance score. The goal is to pick tasks that maximize total importance without going over the hour limit.

**Approach:** Uses dynamic programming (0/1 knapsack) to find the optimal selection.

**Run:**
```bash
cd vehicle_scheduler
uvicorn main:app --reload --port 8000
```

**Endpoint:**
```
GET http://localhost:8000/schedule
```

**Sample Response:**
```json
{
  "result": [
    {
      "depotID": 1,
      "budgetHours": 60,
      "hoursUsed": 59,
      "impactScore": 145,
      "tasks": ["uuid-1", "uuid-2", "..."]
    }
  ]
}
```

---

### 3. Campus Notification Priority Inbox

A FastAPI service that fetches campus notifications and returns the top 10 most important ones based on type priority and recency.

**Priority weights:**
- Placement = 3
- Result = 2
- Event = 1

**Scoring formula:**
```
score = (weight × 100) - hours_since_created
```

This ensures placement notifications always rank higher than results/events, and within the same type, newer ones come first.

**Run:**
```bash
cd notification_app_be
uvicorn main:app --reload --port 8001
```

**Endpoint:**
```
GET http://localhost:8001/inbox
```

**Sample Response:**
```json
{
  "inbox": [
    {
      "ID": "uuid",
      "Type": "Placement",
      "Message": "Amgen Inc. hiring",
      "Timestamp": "2026-05-02 05:34:03"
    }
  ],
  "count": 10
}
```

**For new notifications coming in continuously:**
The current approach re-fetches and re-sorts on every request. For a production system with real-time updates, a min-heap of size 10 would be more efficient — insert in O(log 10) constant time without re-sorting the full list each time.

---

### 4. Notification System Design

See [notification_system_design.md](./notification_system_design.md) for the full system design covering:

- Stage 1: REST API design and real-time notification mechanism
- Stage 2: Database schema and storage strategy
- Stage 3: Query optimization and indexing
- Stage 4: Caching and performance improvements
- Stage 5: Async notifications and fault tolerance
- Stage 6: Priority inbox implementation and approach

---

## Screenshots

Output screenshots are in the `screenshots/` folder.

---

## Notes

- Token expires every 15 minutes — re-run the auth endpoint to get a fresh one
- `.env` file is gitignored — never committed to the repo
- All modules use the logging middleware for structured logging
