```python
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, JSONResponse, Query, Request, Response

DB_PATH = "tasks.db"
VALID_PRIORITIES = {"low", "medium", "high"}


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                completed INTEGER NOT NULL DEFAULT 0,
                priority TEXT NOT NULL DEFAULT 'medium',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


init_db()

app = FastAPI()


def parse_json_body(request: Request) -> Dict[str, Any]:
    raw = await request.body()
    if not raw:
        return {}

    try:
        body = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="Invalid JSON body")
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Invalid JSON body")

    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object")

    return body


def validate_title(title: Any) -> str:
    if not isinstance(title, str):
        raise HTTPException(status_code=422, detail="Title must be a string")

    stripped = title.strip()
    if not stripped or len(stripped) > 200:
        raise HTTPException(
            status_code=422,
            detail="Title must be 1-200 characters and non-empty after trim"
        )

    return stripped


def validate_priority(priority: Any) -> str:
    if not isinstance(priority, str) or priority not in VALID_PRIORITIES:
        raise HTTPException(
            status_code=422,
            detail="Priority must be one of: low, medium, high"
        )
    return priority


def validate_description(description: Any) -> Optional[str]:
    if description is None:
        return None
    if not isinstance(description, str):
        raise HTTPException(status_code=422, detail="Description must be a string or null")
    return description


def validate_completed(completed: Any) -> bool:
    if not isinstance(completed, bool):
        raise HTTPException(status_code=422, detail="Completed must be a boolean")
    return completed


def row_to_task(row: tuple) -> Dict[str, Any]:
    return {
        "id": row[0],
        "title": row[1],
        "description": row[2],
        "completed": bool(row[3]),
        "priority": row[4],
        "created_at": row[5],
    }


@app.post("/tasks")
async def create_task(request: Request):
    body = await parse_json_body(request)

    if "title" not in body:
        raise HTTPException(status_code=422, detail="Title is required")

    title = validate_title(body["title"])

    description = None
    if "description" in body:
        description = validate_description(body["description"])

    priority = "medium"
    if "priority" in body:
        if body["priority"] is None:
            raise HTTPException(
                status_code=422,
                detail="Priority must be one of: low, medium, high"
            )
        priority = validate_priority(body["priority"])

    created_at = datetime.now(timezone.utc).isoformat()

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            """
            INSERT INTO tasks (title, description, completed, priority, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (title, description, 0, priority, created_at),
        )
        new_id = cur.lastrowid
        conn.commit()

        row = conn.execute(
            """
            SELECT id, title, description, completed, priority, created_at
            FROM tasks
            WHERE id = ?
            """,
            (new_id,),
        ).fetchone()
    finally:
        conn.close()

    return JSONResponse(status_code=201, content=row_to_task(row))


@app.get("/tasks")
def list_tasks(
    completed: Optional[bool] = Query(default=None),
    priority: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
):
    if priority is not None:
        if not isinstance(priority, str) or priority not in VALID_PRIORITIES:
            raise HTTPException(
                status_code=422,
                detail="Priority must be one of: low, medium, high"
            )

    where_clauses = []
    params: list = []

    if completed is not None:
        where_clauses.append("completed = ?")
        params.append(1 if completed else 0)

    if priority is not None:
        where_clauses.append("priority = ?")
        params.append(priority)

    where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    conn = sqlite3.connect(DB_PATH)
    try:
        total = conn.execute(
            f"SELECT COUNT(*) FROM tasks{where_sql}",
            params,
        ).fetchone()[0]

        offset = (page - 1) * page_size
        rows = conn.execute(
            f"""
            SELECT id, title, description, completed, priority, created_at
            FROM tasks{where_sql}
            ORDER BY id ASC
            LIMIT ? OFFSET ?
            """,
            params + [page_size, offset],
        ).fetchall()
    finally:
        conn.close()

    return {
        "items": [row_to_task(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            """
            SELECT id, title, description, completed, priority, created_at
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return row_to_task(row)


@app.put("/tasks/{task_id}")
async def update_task(task_id: int, request: Request):
    body = await parse_json_body(request)
    updates: Dict[str, Any] = {}

    if "title" in body:
        updates["title"] = validate_title(body["title"])

    if "description" in body:
        updates["description"] = validate_description(body["description"])

    if "completed" in body:
        updates["completed"] = validate_completed(body["completed"])

    if "priority" in body:
        if body["priority"] is None:
            raise HTTPException(
                status_code=422,
                detail="Priority must be one of: low, medium, high"
            )
        updates["priority"] = validate_priority(body["priority"])

    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            """
            SELECT id, title, description, completed, priority, created_at
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Task not found")

        if updates:
            set_clauses = []
            params = []

            if "title" in updates:
                set_clauses.append("title = ?")
                params.append(updates["title"])

            if "description" in updates:
                set_clauses.append("description = ?")
                params.append(updates["description"])

            if "completed" in updates:
                set_clauses.append("completed = ?")
                params.append(int(updates["completed"]))

            if "priority" in updates:
                set_clauses.append("priority = ?")
                params.append(updates["priority"])

            conn.execute(
                f"UPDATE tasks SET {', '.join(set_clauses)} WHERE id = ?",
                params + [task_id],
            )
            conn.commit()

            row = conn.execute(
                """
                SELECT id, title, description, completed, priority, created_at
                FROM tasks
                WHERE id = ?
                """,
                (task_id,),
            ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return row_to_task(row)


@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    conn = sqlite3.connect(DB_PATH)
    try:
        existing = conn.execute(
            "SELECT 1 FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

        if existing is None:
            raise HTTPException(status_code=404, detail="Task not found")

        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
    finally:
        conn.close()

    return Response(status_code=204)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
```