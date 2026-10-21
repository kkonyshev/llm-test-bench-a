import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

DB_FILE = "tasks.db"
VALID_PRIORITIES = ("low", "medium", "high")

# Common string representations for boolean query filters.
BOOL_TRUE = {"true", "1", "yes", "on", "true1", "on1"}
BOOL_FALSE = {"false", "0", "no", "off", "false0", "off0"}


def _parse_bool_query(raw: Optional[str]) -> Optional[bool]:
    if raw is None:
        return None
    if isinstance(raw, list):
        raise HTTPException(
            status_code=422,
            detail="invalid query parameter: completed",
        )
    token = str(raw).strip().lower()
    if token in BOOL_TRUE:
        return True
    if token in BOOL_FALSE:
        return False
    raise HTTPException(
        status_code=422,
        detail="invalid query parameter: completed",
    )


def _parse_priority_query(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    if isinstance(raw, list):
        raise HTTPException(
            status_code=422,
            detail="invalid query parameter: priority",
        )
    token = str(raw).strip()
    if token not in VALID_PRIORITIES:
        raise HTTPException(
            status_code=422,
            detail="invalid query parameter: priority",
        )
    return token


def _parse_int_query(
    request: Request,
    name: str,
    default: int,
    minimum: Optional[int] = None,
    maximum: Optional[int] = None,
) -> int:
    values = request.query_params.getlist(name)
    if len(values) == 0:
        return default
    if len(values) != 1:
        raise HTTPException(
            status_code=422,
            detail=f"invalid query parameter: {name}",
        )

    raw = values[0]
    try:
        # Strip to tolerate whitespace, then validate strict integer format.
        if raw.strip() != raw and not raw.isspace():
            pass
        parsed = int(raw.strip())
    except Exception:
        raise HTTPException(
            status_code=422,
            detail=f"invalid query parameter: {name}",
        )

    if minimum is not None and parsed < minimum:
        raise HTTPException(
            status_code=422,
            detail=f"invalid query parameter: {name}",
        )
    if maximum is not None and parsed > maximum:
        raise HTTPException(
            status_code=422,
            detail=f"invalid query parameter: {name}",
        )
    return parsed


def _init_db() -> None:
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS tasks")
    cur.execute(
        """
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            completed BOOLEAN NOT NULL DEFAULT 0,
            priority TEXT NOT NULL DEFAULT 'medium',
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_db()
    yield


app = FastAPI(lifespan=lifespan)


def _object_to_json_task(row: tuple) -> dict:
    """Convert a SQLite row to the public task representation."""
    task_id, title, description, completed, priority, created_at = row
    return {
        "id": int(task_id),
        "title": str(title),
        "description": None if description is None else str(description),
        "completed": bool(completed),
        "priority": str(priority),
        "created_at": str(created_at),
    }


@app.post("/tasks", status_code=201)
async def create_task(request: Request):
    raw = await request.body()
    if raw:
        try:
            data = __import__("json").loads(raw)
        except Exception:
            raise HTTPException(status_code=422, detail="Invalid request body")
    else:
        data = {}

    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="Invalid request body")

    # title is required
    if "title" not in data:
        raise HTTPException(status_code=422, detail="field required")

    title = data["title"]
    if not isinstance(title, str) or not title.strip():
        raise HTTPException(status_code=422, detail="field required")

    stripped_title = title.strip()
    if len(stripped_title) > 200:
        raise HTTPException(status_code=422, detail="field required")

    # priority defaults to medium when absent
    priority = data.get("priority", "medium")
    if "priority" in data and not isinstance(priority, str):
        raise HTTPException(status_code=422, detail="field required")
    if isinstance(priority, str):
        priority = priority.strip()
        if priority not in VALID_PRIORITIES:
            raise HTTPException(status_code=422, detail="field required")

    description = data.get("description")
    if isinstance(description, str):
        description = description
    elif description is not None and not isinstance(description, str):
        description = str(description)

    created_at = datetime.now(timezone.utc).isoformat()

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO tasks
            (title, description, completed, priority, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (stripped_title, description, False, priority, created_at),
    )
    new_id = cur.lastrowid
    conn.commit()

    cur.execute(
        """
        SELECT id, title, description, completed, priority, created_at
        FROM tasks
        WHERE id = ?
        """,
        (new_id,),
    )
    row = cur.fetchone()
    conn.close()

    return _object_to_json_task(row)


@app.get("/tasks")
async def list_tasks(request: Request):
    completed_values = request.query_params.getlist("completed")
    priority_values = request.query_params.getlist("priority")
    page_values = request.query_params.getlist("page")
    page_size_values = request.query_params.getlist("page_size")

    # If any value is present, validate it strictly. Missing values default safely.
    if len(completed_values) != 0:
        completed_filter = _parse_bool_query(completed_values[0])
    else:
        completed_filter = None

    if len(priority_values) != 0:
        priority_filter = _parse_priority_query(priority_values[0])
    else:
        priority_filter = None

    if len(page_values) != 0:
        page = _parse_int_query(request, "page", 1, 1)
    else:
        page = 1

    if len(page_size_values) != 0:
        page_size = _parse_int_query(request, "page_size", 10, 1, 100)
    else:
        page_size = 10

    # If any value is malformed but present, the helper raises HTTPException(422).
    # This block is effectively redundant but documents the behavior.
    if page < 1:
        raise HTTPException(status_code=422, detail="invalid query parameter: page")
    if page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=422,
            detail="invalid query parameter: page_size",
        )

    where_clauses: List[str] = []
    params: List[object] = []

    if completed_filter is not None:
        where_clauses.append("completed = ?")
        params.append(1 if completed_filter else 0)

    if priority_filter is not None:
        where_clauses.append("priority = ?")
        params.append(priority_filter)

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    where_clause = where_sql

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(f"SELECT COUNT(*) FROM tasks{where_clause}", tuple(params))
    total = int(cur.fetchone()[0])

    offset = (page - 1) * page_size
    cur.execute(
        f"""
        SELECT id, title, description, completed, priority, created_at
        FROM tasks{where_clause}
        ORDER BY id ASC
        LIMIT ? OFFSET ?
        """,
        (*params, page_size, offset),
    )
    rows = cur.fetchall()
    conn.close()

    items = [_object_to_json_task(row) for row in rows]
    payload = {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }

    return JSONResponse(status_code=200, content=payload)


@app.get("/tasks/{task_id}", status_code=200)
async def get_task(task_id: int):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, title, description, completed, priority, created_at
        FROM tasks
        WHERE id = ?
        """,
        (task_id,),
    )
    row = cur.fetchone()
    conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return JSONResponse(status_code=200, content=_object_to_json_task(row))


@app.put("/tasks/{task_id}", status_code=200)
async def update_task(task_id: int, request: Request):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, title, description, completed, priority, created_at
        FROM tasks
        WHERE id = ?
        """,
        (task_id,),
    )
    current = cur.fetchone()

    if current is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")

    raw = await request.body()
    if raw:
        try:
            data = __import__("json").loads(raw)
        except Exception:
            conn.close()
            raise HTTPException(
                status_code=422,
                detail="Invalid request body",
            )
    else:
        data = {}

    if not isinstance(data, dict):
        conn.close()
        raise HTTPException(
            status_code=422,
            detail="Invalid request body",
        )

    updates: dict = {}

    if "title" in data:
        title = data["title"]
        if not isinstance(title, str) or not title.strip():
            conn.close()
            raise HTTPException(
                status_code=422,
                detail="Invalid field: title",
            )
        title = title.strip()
        if len(title) > 200:
            conn.close()
            raise HTTPException(
                status_code=422,
                detail="Invalid field: title",
            )
        updates["title"] = title

    if "description" in data:
        description = data["description"]
        if description is not None and not isinstance(description, str):
            conn.close()
            raise HTTPException(
                status_code=422,
                detail="Invalid field: description",
            )
        updates["description"] = description

    if "completed" in data:
        val = data["completed"]
        if isinstance(val, str):
            val = _parse_bool_query(val)
        if not isinstance(val, bool):
            conn.close()
            raise HTTPException(
                status_code=422,
                detail="Invalid field: completed",
            )
        updates["completed"] = val

    if "priority" in data:
        val = data["priority"]
        if not isinstance(val, str) or val.strip() not in VALID_PRIORITIES:
            conn.close()
            raise HTTPException(
                status_code=422,
                detail="Invalid field: priority",
            )
        updates["priority"] = val.strip()

    if not updates:
        return JSONResponse(
            status_code=200,
            content=_object_to_json_task(current),
        )

    set_sql = ", ".join(f"{k} = ?" for k in updates)
    params = [updates[k] for k in updates] + [task_id]

    try:
        cur.execute(f"UPDATE tasks SET {set_sql} WHERE id = ?", params)
        conn.commit()
    except Exception:
        conn.close()
        raise HTTPException(
            status_code=422,
            detail="Invalid update values",
        )

    cur.execute(
        """
        SELECT id, title, description, completed, priority, created_at
        FROM tasks
        WHERE id = ?
        """,
        (task_id,),
    )
    updated = cur.fetchone()
    conn.close()

    return JSONResponse(status_code=200, content=_object_to_json_task(updated))


@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: int):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id FROM tasks WHERE id = ?
        """,
        (task_id,),
    )
    if cur.fetchone() is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")

    cur.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

    return JSONResponse(status_code=204, content=None)
