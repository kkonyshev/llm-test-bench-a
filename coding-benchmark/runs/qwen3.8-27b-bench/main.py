import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

from fastapi import Body, FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, Field

DB_FILE = "tasks.db"

TABLE_SQL = """
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
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute(TABLE_SQL)
    conn.commit()
    return conn


def init_db() -> None:
    conn = get_connection()
    conn.close()


init_db()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    priority: Literal["low", "medium", "high"] = "medium"


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[Literal["low", "medium", "high"]] = None


class Task(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    completed: bool
    priority: str
    created_at: str


class TaskList(BaseModel):
    items: List[Task]
    total: int
    page: int
    page_size: int


def row_to_task(row: sqlite3.Row) -> Task:
    return Task(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        completed=bool(row["completed"]),
        priority=row["priority"],
        created_at=row["created_at"],
    )


def validate_title(title) -> None:
    if (
        not isinstance(title, str)
        or len(title) == 0
        or len(title) > 200
        or not title.strip()
    ):
        raise HTTPException(
            status_code=422,
            detail="title must be a non-empty string of at most 200 characters after trimming",
        )


def get_explicit_values(model: TaskUpdate) -> Dict[str, object]:
    try:
        return model.model_dump(exclude_unset=True)
    except AttributeError:
        return model.dict(exclude_unset=True)


@app.post("/tasks", response_model=Task, status_code=201)
def create_task(payload: TaskCreate) -> Task:
    validate_title(payload.title)
    created_at = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO tasks (title, description, completed, priority, created_at) VALUES (?, ?, 0, ?, ?)",
            (payload.title, payload.description, payload.priority, created_at),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)).fetchone()
    finally:
        conn.close()
    return row_to_task(row)


@app.get("/tasks", response_model=TaskList)
def list_tasks(
    completed: Optional[bool] = Query(None),
    priority: Optional[Literal["low", "medium", "high"]] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
) -> TaskList:
    where_clauses = []
    params = []

    if completed is not None:
        where_clauses.append("completed = ?")
        params.append(1 if completed else 0)
    if priority is not None:
        where_clauses.append("priority = ?")
        params.append(priority)

    where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    conn = get_connection()
    try:
        total = conn.execute(f"SELECT COUNT(*) FROM tasks{where_sql}", params).fetchone()[0]
        offset = (page - 1) * page_size
        rows = conn.execute(
            f"SELECT * FROM tasks{where_sql} ORDER BY id ASC LIMIT ? OFFSET ?",
            params + [page_size, offset],
        ).fetchall()
    finally:
        conn.close()

    return TaskList(
        items=[row_to_task(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: int) -> Task:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return row_to_task(row)


@app.put("/tasks/{task_id}", response_model=Task)
def update_task(task_id: int, payload: Optional[TaskUpdate] = Body(None)) -> Task:
    explicit: Dict[str, object] = {}
    if payload is not None:
        explicit = get_explicit_values(payload)

    if "title" in explicit:
        validate_title(explicit["title"])
    if "priority" in explicit and explicit["priority"] is None:
        raise HTTPException(status_code=422, detail="priority must be one of low, medium, high")
    if "completed" in explicit and explicit["completed"] is None:
        raise HTTPException(status_code=422, detail="completed must be a boolean")

    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Task not found")

        updates = []
        params = []

        if "title" in explicit:
            updates.append("title = ?")
            params.append(explicit["title"])
        if "description" in explicit:
            updates.append("description = ?")
            params.append(explicit["description"])
        if "completed" in explicit:
            updates.append("completed = ?")
            params.append(1 if explicit["completed"] else 0)
        if "priority" in explicit:
            updates.append("priority = ?")
            params.append(explicit["priority"])

        if updates:
            params.append(task_id)
            conn.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    finally:
        conn.close()

    return row_to_task(row)


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int) -> Response:
    conn = get_connection()
    try:
        cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        deleted = cursor.rowcount
    finally:
        conn.close()

    if deleted == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return Response(status_code=204)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
