import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request, Response

DB_PATH = "tasks.db"
ALLOWED_PRIORITIES = ("low", "medium", "high")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    completed INTEGER NOT NULL DEFAULT 0,
    priority TEXT NOT NULL DEFAULT 'medium',
    created_at TEXT NOT NULL
)
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()
    finally:
        conn.close()


app = FastAPI()


@app.on_event("startup")
def startup_event() -> None:
    init_db()


init_db()


async def read_json_object(request: Request, allow_empty: bool = False) -> dict:
    try:
        body = await request.body()
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid request body")

    if allow_empty and body.strip() == b"":
        return {}

    try:
        data = json.loads(body)
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid JSON body")

    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object")

    return data


def validate_title(value: object) -> str:
    if not isinstance(value, str):
        raise HTTPException(status_code=422, detail="title must be a string")

    stripped = value.strip()
    if not stripped or len(stripped) > 200:
        raise HTTPException(
            status_code=422,
            detail="title must be between 1 and 200 characters after trimming",
        )

    return stripped


def validate_description(value: object) -> Optional[str]:
    if value is not None and not isinstance(value, str):
        raise HTTPException(status_code=422, detail="description must be a string or null")
    return value


def validate_priority(value: object) -> str:
    if not isinstance(value, str) or value not in ALLOWED_PRIORITIES:
        raise HTTPException(status_code=422, detail="priority must be one of low, medium, high")
    return value


def parse_bool_query(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None

    value = value.strip().lower()
    if value in ("true", "1"):
        return True
    if value in ("false", "0"):
        return False

    raise HTTPException(status_code=422, detail="completed must be a boolean")


def task_from_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "completed": bool(row["completed"]),
        "priority": row["priority"],
        "created_at": row["created_at"],
    }


@app.post("/tasks", status_code=201)
async def create_task(request: Request):
    payload = await read_json_object(request, allow_empty=True)

    if "title" not in payload:
        raise HTTPException(status_code=422, detail="title is required")

    title = validate_title(payload["title"])
    description = (
        validate_description(payload["description"]) if "description" in payload else None
    )
    priority = (
        validate_priority(payload["priority"]) if "priority" in payload else "medium"
    )

    created_at = datetime.now(timezone.utc).isoformat()

    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO tasks (title, description, completed, priority, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (title, description, 0, priority, created_at),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)).fetchone()
    finally:
        conn.close()

    return task_from_row(row)


@app.get("/tasks")
def list_tasks(
    completed: Optional[str] = Query(default=None),
    priority: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
):
    completed_filter = parse_bool_query(completed)

    if priority is not None:
        priority = validate_priority(priority)

    where_clauses = []
    params = []

    if completed_filter is not None:
        where_clauses.append("completed = ?")
        params.append(1 if completed_filter else 0)

    if priority is not None:
        where_clauses.append("priority = ?")
        params.append(priority)

    where_sql = "" if not where_clauses else " WHERE " + " AND ".join(where_clauses)

    conn = get_connection()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) FROM tasks{where_sql}",
            params,
        ).fetchone()[0]

        offset = (page - 1) * page_size
        rows = conn.execute(
            f"SELECT * FROM tasks{where_sql} ORDER BY id ASC LIMIT ? OFFSET ?",
            params + [page_size, offset],
        ).fetchall()
    finally:
        conn.close()

    return {
        "items": [task_from_row(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@app.get("/tasks/{id}")
def get_task(id: int):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (id,)).fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return task_from_row(row)


@app.put("/tasks/{id}")
async def update_task(id: int, request: Request):
    payload = await read_json_object(request, allow_empty=True)
    updates = {}

    if "title" in payload:
        updates["title"] = validate_title(payload["title"])

    if "description" in payload:
        updates["description"] = validate_description(payload["description"])

    if "completed" in payload:
        value = payload["completed"]
        if not isinstance(value, bool):
            raise HTTPException(status_code=422, detail="completed must be a boolean")
        updates["completed"] = 1 if value else 0

    if "priority" in payload:
        updates["priority"] = validate_priority(payload["priority"])

    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Task not found")

        if updates:
            set_clauses = ", ".join(f"{key} = ?" for key in updates.keys())
            values = list(updates.values()) + [id]
            conn.execute(f"UPDATE tasks SET {set_clauses} WHERE id = ?", values)
            conn.commit()
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (id,)).fetchone()

            if row is None:
                raise HTTPException(status_code=404, detail="Task not found")
    finally:
        conn.close()

    return task_from_row(row)


@app.delete("/tasks/{id}", status_code=204)
def delete_task(id: int):
    conn = get_connection()
    try:
        cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (id,))
        conn.commit()

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Task not found")

        return Response(status_code=204)
    finally:
        conn.close()
