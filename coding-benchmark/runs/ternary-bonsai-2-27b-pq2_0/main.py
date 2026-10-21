import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel

TABLE_SQL = (
    "CREATE TABLE IF NOT EXISTS tasks ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT,"
    "title TEXT NOT NULL,"
    "description TEXT,"
    "completed INTEGER NOT NULL DEFAULT 0,"
    "priority TEXT NOT NULL,"
    "created_at TEXT NOT NULL"
    ")"
)

VALID_PRIORITIES = {"low", "medium", "high"}


class Task(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    completed: bool
    priority: str
    created_at: str


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Optional[str] = None


def get_connection():
    conn = sqlite3.connect("tasks.db")
    conn.execute(TABLE_SQL)
    conn.commit()
    return conn


def init_db():
    conn = get_connection()
    conn.close()


def row_to_task(row):
    return Task(
        id=row[0],
        title=row[1],
        description=row[2],
        completed=bool(row[3]),
        priority=row[4],
        created_at=row[5],
    )


app = FastAPI()


@app.on_event("startup")
def startup():
    init_db()


@app.post("/tasks", status_code=201, response_model=Task)
def create_task(payload: TaskCreate):
    title = payload.title
    if len(title) > 200 or not title.strip():
        raise HTTPException(
            status_code=422,
            detail="title must be a non-empty string of at most 200 characters",
        )

    priority = payload.priority
    if priority is not None and priority not in VALID_PRIORITIES:
        raise HTTPException(
            status_code=422,
            detail="priority must be one of low, medium, high",
        )
    if priority is None:
        priority = "medium"

    created_at = datetime.now(timezone.utc).isoformat()

    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO tasks (title, description, completed, priority, created_at)
            VALUES (?, ?, 0, ?, ?)
            """,
            (title, payload.description, priority, created_at),
        )
        conn.commit()
        new_id = cur.lastrowid

        return Task(
            id=new_id,
            title=title,
            description=payload.description,
            completed=False,
            priority=priority,
            created_at=created_at,
        )
    finally:
        conn.close()


@app.get("/tasks")
def list_tasks(
    completed: Optional[bool] = None,
    priority: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    if priority is not None and priority not in VALID_PRIORITIES:
        raise HTTPException(
            status_code=422,
            detail="priority must be one of low, medium, high",
        )

    where = []
    params = []

    if completed is not None:
        where.append("completed = ?")
        params.append(1 if completed else 0)

    if priority is not None:
        where.append("priority = ?")
        params.append(priority)

    count_sql = "SELECT COUNT(*) FROM tasks"
    if where:
        count_sql += " WHERE " + " AND ".join(where)

    if where:
        list_sql = (
            "SELECT id, title, description, completed, priority, created_at "
            "FROM tasks "
            "WHERE " + " AND ".join(where)
            + " ORDER BY id ASC LIMIT ? OFFSET ?"
        )
    else:
        list_sql = (
            "SELECT id, title, description, completed, priority, created_at "
            "FROM tasks "
            "ORDER BY id ASC LIMIT ? OFFSET ?"
        )

    offset = (page - 1) * page_size

    conn = get_connection()
    try:
        total = conn.execute(count_sql, params).fetchone()[0]
        rows = conn.execute(list_sql, params + [page_size, offset]).fetchall()
        items = [row_to_task(row) for row in rows]

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    finally:
        conn.close()


@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: int):
    conn = get_connection()
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
    body = await request.body()

    if body:
        try:
            data = json.loads(body)
        except ValueError:
            raise HTTPException(status_code=422, detail="Request body must be JSON")
    else:
        data = {}

    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object")

    updates = {}

    if "title" in data:
        title = data["title"]
        if not isinstance(title, str):
            raise HTTPException(status_code=422, detail="title must be a string")
        if len(title) > 200 or not title.strip():
            raise HTTPException(
                status_code=422,
                detail="title must be a non-empty string of at most 200 characters",
            )
        updates["title"] = title

    if "description" in data:
        description = data["description"]
        if description is None or isinstance(description, str):
            updates["description"] = description
        else:
            raise HTTPException(
                status_code=422,
                detail="description must be a string or null",
            )

    if "completed" in data:
        completed = data["completed"]
        if not isinstance(completed, bool):
            raise HTTPException(status_code=422, detail="completed must be a boolean")
        updates["completed"] = completed

    if "priority" in data:
        priority = data["priority"]
        if priority not in VALID_PRIORITIES:
            raise HTTPException(
                status_code=422,
                detail="priority must be one of low, medium, high",
            )
        updates["priority"] = priority

    conn = get_connection()
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
            fields = []
            values = []

            for key, value in updates.items():
                if key == "completed":
                    fields.append("completed = ?")
                    values.append(1 if value else 0)
                else:
                    fields.append(f"{key} = ?")
                    values.append(value)

            conn.execute(
                f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?",
                values + [task_id],
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

        return row_to_task(row)
    finally:
        conn.close()


@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Task not found")

        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
    finally:
        conn.close()

    return Response(status_code=204)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
