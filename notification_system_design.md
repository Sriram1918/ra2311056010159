# Notification System Design

## Stage 1

### REST API Design

The notification platform needs to support these core actions:
- Get all notifications for a logged-in student
- Get only unread notifications
- Mark a notification as read
- Mark all as read
- Get a single notification by id
- Real time delivery when new notification comes

#### Endpoints

**1. GET /api/notifications**
Fetch all notifications for the logged-in student (paginated)

Headers:
```
Authorization: Bearer <token>
```

Query params:
```
?page=1&limit=20&type=Placement
```

Response:
```json
{
  "page": 1,
  "limit": 20,
  "total": 145,
  "notifications": [
    {
      "id": "uuid-here",
      "type": "Placement",
      "message": "CSX Corporation hiring",
      "isRead": false,
      "createdAt": "2026-04-22T17:51:18Z"
    }
  ]
}
```

**2. GET /api/notifications/unread**
Fetch only unread notifications

Response:
```json
{
  "count": 12,
  "notifications": [...]
}
```

**3. PATCH /api/notifications/:id/read**
Mark a single notification as read

Response:
```json
{
  "id": "uuid-here",
  "isRead": true
}
```

**4. PATCH /api/notifications/read-all**
Mark all notifications as read for the user

Response:
```json
{
  "updatedCount": 12
}
```

**5. GET /api/notifications/:id**
Get single notification details

### Real-Time Notification Mechanism

For real time delivery I would use **WebSockets** since notifications need to come instantly (placement alerts especially).

When a student logs in:
1. Frontend opens a websocket connection to `/ws/notifications`
2. Server keeps the connection alive
3. When a new notification comes in (placement, result, event), backend pushes it through the socket
4. Frontend gets it without refreshing

Why websockets and not polling?
- Polling every few seconds wastes server resources
- 50,000 students polling = huge load
- Websocket is one persistent connection, much cheaper

Alternative: Server-Sent Events (SSE) if we only need server-to-client push.

---

## Stage 2

### Choosing the Database

I would go with **PostgreSQL** for this.

Why PostgreSQL:
- Notifications are structured (id, type, message, timestamp, isRead) — relational fits well
- We need ACID for marking-as-read (must be reliable)
- Strong indexing support for queries like "unread for user X"
- Free, open source, scales fine for our case

Why not NoSQL like MongoDB?
- Notifications have fixed fields, no flexible schema needed
- We need fast filtering on userId + isRead — relational does this well
- Joins might be needed (user table, notification table)

### Schema

```sql
CREATE TABLE students (
    id BIGINT PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(150) UNIQUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TYPE notification_type AS ENUM ('Event', 'Result', 'Placement');

CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id BIGINT REFERENCES students(id),
    notification_type notification_type NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Problems as data grows

When notifications grow to millions:
- `SELECT * FROM notifications WHERE student_id=? AND is_read=false` becomes slow without indexes
- Old notifications take up disk space
- Queries scan more rows

### How to fix
- Add composite index on (student_id, is_read, created_at DESC)
- Archive old notifications (older than 6 months) to a separate table
- Use partitioning by month if data is huge
- Cache frequently accessed unread counts in Redis

---

## Stage 3

### Analyzing the slow query

```sql
SELECT * FROM notifications
WHERE studentID = 1042 AND isRead = false
ORDER BY createdAt DESC;
```

**Is the query accurate?** Yes, logically it is correct — fetches unread notifications for student 1042 sorted by latest first.

**Why is it slow?**
- 5 million rows means a full table scan if no indexes exist
- `ORDER BY createdAt DESC` requires sorting all matching rows
- `SELECT *` pulls every column even if only some are needed

### What I would change

1. Add a composite index:
```sql
CREATE INDEX idx_unread_notifs ON notifications(studentID, isRead, createdAt DESC);
```
This index covers the WHERE clause and the ORDER BY in one shot.

2. Replace `SELECT *` with only needed columns:
```sql
SELECT id, notificationType, message, createdAt
FROM notifications
WHERE studentID = 1042 AND isRead = false
ORDER BY createdAt DESC
LIMIT 20;
```

3. Add LIMIT — students don't need all 100s of unread at once.

### Computation cost

- Without index: O(N) scan, N=5M rows → very slow
- With composite index: O(log N) lookup + small scan → fast (probably <50ms)

### Is "indexes on every column" advice safe?

**No, this is bad advice.** Indexes have tradeoffs:
- Each index slows down INSERT/UPDATE/DELETE because index has to be updated too
- Indexes take disk space
- Too many indexes confuse the query planner
- Index on low-cardinality columns (like a boolean) wastes space

Only index columns used in WHERE, JOIN, ORDER BY frequently.

### Query for placement notifications in last 7 days

```sql
SELECT DISTINCT studentID
FROM notifications
WHERE notificationType = 'Placement'
  AND createdAt >= NOW() - INTERVAL '7 days';
```

Add an index to make this fast:
```sql
CREATE INDEX idx_type_date ON notifications(notificationType, createdAt);
```

---

## Stage 4

### Problem

Notifications fetched on every page load — DB getting hammered. Bad UX.

### Solution: Caching

Use **Redis** as a caching layer between app and DB.

**Strategy:**
1. When student opens dashboard, check Redis first: `GET notifs:student_1042`
2. If found in cache → return instantly (no DB hit)
3. If not found → query DB → store in Redis with 60-second TTL → return

**Cache invalidation:**
- When a new notification is created → delete the cached entry for that student
- When student marks as read → delete the cached entry
- TTL of 60 seconds as safety net

### Other strategies

**a) HTTP caching (ETag/Last-Modified)**
Browser caches the response. Good for repeated reloads.

**b) Pagination + lazy load**
Don't load 100s of notifications at once. Load 20, scroll for more.

**c) CDN edge caching**
Not great here because notifications are user-specific.

### Tradeoffs

| Strategy | Pro | Con |
|----------|-----|-----|
| Redis | Super fast, easy invalidation | Extra infra, stale data risk |
| HTTP cache | No backend changes | Hard to invalidate on new notif |
| Pagination | Less load per request | Multiple round trips |

**My pick:** Redis + Pagination together. Redis handles repeat requests, pagination keeps response sizes small.

---

## Stage 5

### Problems with the current pseudocode

```
function notify_all(student_ids, message):
    for student_id in student_ids:
        send_email(student_id, message)
        save_to_db(student_id, message)
        push_to_app(student_id, message)
```

Issues I can see:
1. **Sequential** — one student at a time, 50,000 students will take forever
2. **Failure handling missing** — if email fails for student 200, what about students 201-50000?
3. **No retry** — failed sends are just lost
4. **No transaction** — DB save and push could be inconsistent
5. **Blocks the HTTP request** — HR clicks "Notify All" and waits 10 minutes for response

### Should DB save and email send happen together?

**No, they should be separated.**

Why?
- Email is external (slow, can fail)
- DB save is internal (fast, reliable)
- If email API is down, we still want the notification saved
- Saving first, sending email later (async) is the right pattern

### Redesigned approach

Use a **message queue** like Kafka or RabbitMQ.

```
function notify_all(student_ids, message):
    # save all to DB first in a batch
    save_batch_to_db(student_ids, message)
    
    # push each student to a queue for async processing
    for student_id in student_ids:
        queue.push({
            "student_id": student_id,
            "message": message,
            "channel": "email"
        })
        queue.push({
            "student_id": student_id,
            "message": message,
            "channel": "push"
        })
    
    return {"status": "queued", "count": len(student_ids)}
```

Then a **worker process** reads from the queue:
```
worker():
    while True:
        job = queue.pop()
        try:
            if job.channel == "email":
                send_email(job.student_id, job.message)
            else:
                push_to_app(job.student_id, job.message)
        except Exception as e:
            # retry up to 3 times with backoff
            if job.retries < 3:
                job.retries += 1
                queue.push(job, delay=2**job.retries)
            else:
                log_failed(job)
```

### Benefits
- HR gets instant response (job queued)
- Workers process in parallel
- If email fails for 200 students → those go back in queue and retry automatically
- Saves to DB don't depend on email success
- Can scale horizontally — add more workers if queue grows

### What about the 200 failed emails?

Since they are in the queue with retry logic, they get retried automatically. After 3 failed attempts, log them to a "failed_notifications" table so admin can investigate.

---

## Stage 6

### Priority Inbox

Need to show top 10 notifications based on **priority weight + recency**.

**Priority weights:**
- Placement = 3 (highest)
- Result = 2
- Event = 1 (lowest)

**Recency:**
- Newer notifications get higher score
- Use timestamp diff from now

### Approach

Final score = (priority_weight × 100) - (hours_since_created)

This way:
- A Placement notification will always rank higher than Event even if older (within reason)
- Within same type, newer ones rank higher
- Multiplying weight by 100 makes priority matter more than recency for short time windows

### Code

See `notification_app_be/main.py`

### Maintaining top 10 efficiently as new notifications come in

Currently the code sorts the full list every time. For real-time updates, better approach:

**Use a min-heap of size 10:**
- Heap stores top 10 by score
- When new notification comes in, calculate its score
- If score > heap minimum → pop the min, push the new one
- Heap size stays at 10
- Each insertion is O(log 10) = constant time

This way we never re-sort the entire list.

For real production, recompute scores periodically (every minute) since recency changes over time.

---
