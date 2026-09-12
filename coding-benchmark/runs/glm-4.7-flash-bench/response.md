1.  **Understand the Goal:** The user wants a Python script named `main.py` that implements a specific REST API for a Task Tracker using FastAPI and SQLite. The output must be *only* the code block with the file contents.

2.  **Analyze the Requirements:**

    *   **Tech Stack:** FastAPI + SQLite (using `sqlite3` or `sqlalchemy` - I'll choose `sqlite3` for simplicity as per "stdlib", though `sqlalchemy` is often preferred in larger apps, `sqlite3` satisfies the "stdlib" option easily. Actually, `sqlite3` is fine, but `sqlalchemy` might make the ORM part cleaner for Pydantic models. Let's stick to `sqlite3` with raw SQL execution because the constraints say "either the stdlib `sqlite3` or `sqlalchemy`". I will use `sqlite3` for direct control, but `fastapi` will handle the request validation).
    *   **Entry Point:** `main.py`.
    *   **Importable App:** `main.app` must exist.
    *   **Storage:** `tasks.db` in working directory, create automatically on startup.
    *   **Data Model (Task):**
        *   `id` (int, auto-increment)
        *   `title` (str, 1-200 chars, non-empty trim)
        *   `description` (str?, optional)
        *   `completed` (bool, default false)
        *   `priority` (str, one of `low`, `medium`, `high`, default medium)
        *   `created_at` (datetime, ISO 8601 string, server generated)
    *   **Endpoints:**
        *   `POST /tasks`: Create.
            *   Body: `title`, `description` (opt), `priority` (opt).
            *   Response: Full object (201).
            *   Validation: Title required/non-empty, Priority valid.
        *   `GET /tasks`: List.
            *   Query: `completed` (bool), `priority` (str), `page` (int, >=1), `page_size` (int, 1-100).
            *   Response: `{ "items": [...], "total": int, "page": int, "page_size": int }`.
            *   Ordering: `id` ascending.
        *   `GET /tasks/{id}`: Get one.
            *   Response: Task (200) or 404.
        *   `PUT /tasks/{id}`: Update.
            *   Body: subset of fields.
            *   Response: Updated Task (200).
            *   Validation: Same as create (404 for non-exist, 422 for invalid data).
        *   `DELETE /tasks/{id}`: Delete.
            *   Response: 204 or 404.

3.  **Step-by-Step Implementation Plan:**

    *   **Imports:** `fastapi`, `uvicorn`, `pydantic`, `sqlite3`, `datetime`, `os`.
    *   **Database Setup:**
        *   Connect to `tasks.db`.
        *   Create table if not exists.
    *   **Pydantic Models:**
        *   `TaskBase`: fields for validation (title, description, priority).
        *   `TaskCreate`: Inherits from `TaskBase`, no `id`, `created_at`.
        *   `TaskUpdate`: Partial update, allows None values.
        *   `Task`: Full model (id, title, description, completed, priority, created_at).
    *   **FastAPI App Instance:** `app = FastAPI()`.
    *   **DB Management:**
        *   Need a helper function to get a connection or a global connection object. Since FastAPI manages app lifecycle, creating the DB on startup is a good spot (using `@app.on_event("startup")`).
    *   **Endpoints Implementation:**

        *   *Setup Database:*
            ```python
            sql = """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                completed INTEGER DEFAULT 0,
                priority TEXT DEFAULT 'medium',
                created_at TEXT NOT NULL
            )
            """
            ```

        *   *Create Task (POST):*
            *   Validate input.
            *   Insert into DB (`title`, `description`, `completed` -> `0`, `priority`, `created_at` -> ISO format).
            *   Return created Task.

        *   *List Tasks (GET):*
            *   Parse query params. Handle defaults.
            *   Validate `page` (>= 1) and `page_size` (1-100). If invalid, return 422.
            *   Construct SQL query.
            *   Handle `WHERE` clause based on filters (`completed`, `priority`).
            *   Handle `LIMIT` and `OFFSET`.
            *   Execute count query for `total`.
            *   Execute select query for `items`.
            *   Return JSON.

        *   *Get Task (GET /{id}):*
            *   Select by id.
            *   Return 404 if empty.
            *   Return 200 with row converted to Task model.

        *   *Update Task (PUT /{id}):*
            *   Find existing task. If not found, 404.
            *   Parse `update_data`.
            *   Validate update data (same rules as create).
            *   Build SET clause dynamically (if title or priority changed).
            *   Execute update.
            *   Re-fetch and return full Task.

        *   *Delete Task (DELETE /{id}):*
            *   Delete by id.
            *   Return 204 on success, 404 if nothing deleted.

4.  **Refining Details & Edge Cases:**

    *   *Priority Validation:* Allowed: `low`, `medium`, `high`. Case sensitivity? Usually lowercase in DB, but API might accept mixed. I'll normalize or stick to specific checks.
    *   *Date Format:* `created_at` needs to be a string in ISO 8601 format.
    *   *Empty Title:* Should trim and check length. `description` is optional.
    *   *Pagination:* Offset calculation = `(page - 1) * page_size`.
    *   *422 vs 404:* 422 is Unprocessable Entity (validation error), 404 is Not Found.
    *   *SQLite Type Handling:* Boolean in SQLite is INTEGER (0/1). FastAPI Pydantic handles type coercion, but `sqlite3` returns `int` for boolean columns. I need to be careful when converting DB rows back to Pydantic models.

5.  **Drafting Code Structure (Mental or Scratchpad):**

    ```python
    import os
    import sqlite3
    from datetime import datetime
    from typing import Optional, List
    from fastapi import FastAPI, Query, HTTPException, Body, status
    from pydantic import BaseModel, validator, Field

    app = FastAPI()
    DB_FILE = "tasks.db"

    def get_db_connection():
        # ensure dir exists? No, just connect.
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row # Makes accessing columns easier
        return conn

    # Tables
    @app.on_event("startup")
    def startup():
        with get_db_connection() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS tasks (...)""")
            conn.commit()

    # Pydantic
    class TaskBase(BaseModel):
        title: str = Field(..., min_length=1, max_length=200)
        description: Optional[str] = None
        priority: str = "medium"

        @validator("priority")
        def validate_priority(cls, v):
            if v not in ["low", "medium", "high"]:
                raise ValueError("Invalid priority")
            return v

        @validator("title")
        def validate_title(cls, v):
            v = v.strip()
            if not v:
                raise ValueError("Title cannot be empty")
            return v

    class TaskCreate(TaskBase):
        pass

    class TaskUpdate(BaseModel):
        title: Optional[str] = None
        description: Optional[str] = None
        completed: Optional[bool] = None
        priority: Optional[str] = None

        class Config:
            anystr_strip_whitespace = True # Handle trim on update?

    class Task(TaskBase):
        id: int
        completed: bool = False
        created_at: str

    # Logic
    @app.post("/tasks", response_model=Task, status_code=201)
    def create_task(task: TaskCreate):
        # Insert
        # Return

    @app.get("/tasks")
    def list_tasks(...):
        # Validate page/page_size
        # Filter
        # Count
        # Paginate
        # Return

    @app.get("/tasks/{id}", response_model=Task)
    def get_task(id: int):
        # Select

    @app.put("/tasks/{id}", response_model=Task)
    def update_task(id: int, task_update: TaskUpdate):
        # Check exists
        # Validate (especially title/priority)
        # Update
        # Return

    @app.delete("/tasks/{id}")
    def delete_task(id: int):
        # Delete
    ```

6.  **Refining Query Logic:**

    *   *Pagination 422:*
        *   `page`: Must be >= 1.
        *   `page_size`: 1-100.
    *   *SQL Construction:*
        Base query: `SELECT * FROM tasks WHERE 1=1`.
        If `completed` is provided: `AND completed = :completed`.
        If `priority` is provided: `AND priority = :priority`.
        Ordering: `ORDER BY id ASC`.
        Limit/Offset: `LIMIT :page_size OFFSET :offset`.

7.  **Addressing specific constraints:**
    *   "Output ONLY the full contents of a single file named main.py".
    *   "Storage: SQLite, in a file named tasks.db".
    *   "FastAPI app instance must be importable as main.app".
    *   "No split across multiple files".

8.  **Writing the actual code (Self-Correction during drafting):**
    *   *Issue:* When converting `TaskUpdate` to DB updates, I need to handle `None` values gracefully (don't set column to NULL if not provided).
    *   *Solution:* Build a dictionary for update, only add keys that are not None.
    *   *Issue:* ID type in URL is int.
    *   *Issue:* `description` allows null in DB but `sqlite3` stores empty strings as `''`. The spec says "description | null". Pydantic will handle `None` -> `NULL` (or string). The DB schema says `TEXT`, which allows NULL. Good.

9.  **Final Code Assembly:**
    *   Ensure all imports are correct (`typing` for `Optional`, `List`).
    *   Ensure `created_at` generation uses `datetime.utcnow()` (or `now()`, spec says ISO 8601 string).
    *   Add `row_factory` to sqlite connection for easy dict access.

    *Code Check - POST /tasks:*
    - `id` is auto-increment, don't send it in request.
    - `completed` defaults to False. The DB default is 0.
    - `priority` defaults to 'medium'.

    *Code Check - GET /tasks:*
    - `total`: Query separate.
    - `items`: Paginated query.
    - `completed` filter: DB is 0/1, API is bool. FastAPI passes bool to query param. `sqlite3` prepared statements handle binding.

    *Code Check - PUT /tasks:*
    - Only allow specific fields.

    *Code Check - DELETE /tasks:*
    - `sqlite3` `rowcount` returns 0 if nothing deleted.

10. **Final Review against constraints:**
    - `main.py`? Yes.
    - `main.app`? Yes.
    - `tasks.db`? Yes.
    - Dependencies: `fastapi`, `uvicorn`, `pydantic`, `sqlite3`? Yes.
    - No other frameworks? Yes.
    - Validation: Title 1-200 (trim), Priority enum? Yes.
    - Pagination limits? Yes.
    - 422 vs 404 distinction? Yes.

This looks solid. I will now generate the Python code.</think>```python
import os
import sqlite3
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, Query, HTTPException, Body, status, Path
from pydantic import BaseModel, Field, validator

app = FastAPI()

# --- Configuration ---
DB_FILE = "tasks.db"

# --- Pydantic Models ---

class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    priority: str = "medium"

    @validator("priority")
    def validate_priority(cls, v):
        allowed = ["low", "medium", "high"]
        if v not in allowed:
            raise ValueError("priority must be one of: low, medium, high")
        return v

    @validator("title")
    def validate_title(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("title cannot be empty")
        return v

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None

    class Config:
        extra = "forbid"

class Task(TaskBase):
    id: int
    completed: bool = False
    created_at: str

# --- Database Helpers ---

def get_db_connection():
    """Create a new database connection."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn

@app.on_event("startup")
def startup_event():
    """Initialize the database if it doesn't exist."""
    if not os.path.exists(DB_FILE):
        # ensure parent directory exists just in case, though SQLite creates file implicitly
        with get_db_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    completed INTEGER DEFAULT 0,
                    priority TEXT DEFAULT 'medium',
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()

# --- Endpoints ---

@app.post("/tasks", response_model=Task, status_code=201)
def create_task(task: TaskCreate):
    """
    Create a new task.
    """
    with get_db_connection() as conn:
        created_at_str = datetime.utcnow().isoformat()
        # completed is 0 for False, 1 for True in SQLite integer representation
        completed_int = 1 if task.completed else 0
        
        cursor = conn.execute(
            "INSERT INTO tasks (title, description, priority, completed, created_at) VALUES (?, ?, ?, ?, ?)",
            (task.title, task.description, task.priority, completed_int, created_at_str)
        )
        conn.commit()
        task_id = cursor.lastrowid
        
        # Fetch the created row to return
        created_task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_task(created_task)

@app.get("/tasks")
def list_tasks(
    completed: Optional[bool] = Query(None),
    priority: Optional[str] = Query(None),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page")
):
    """
    List tasks with optional filtering and pagination.
    """
    with get_db_connection() as conn:
        base_query = "SELECT * FROM tasks WHERE 1=1"
        count_query = "SELECT COUNT(*) as total FROM tasks WHERE 1=1"
        params = []
        count_params = []

        if completed is not None:
            # completed is stored as int 0/1, query param is bool
            base_query += " AND completed = ?"
            count_query += " AND completed = ?"
            params.append(int(completed))
            count_params.append(int(completed))

        if priority:
            base_query += " AND priority = ?"
            count_query += " AND priority = ?"
            params.append(priority)
            count_params.append(priority)

        # Get total count
        count_cursor = conn.execute(count_query, count_params)
        total = count_cursor.fetchone()["total"]

        # Get paginated items
        offset = (page - 1) * page_size
        items_query = base_query + " ORDER BY id ASC LIMIT ? OFFSET ?"
        items = conn.execute(items_query, params + [page_size, offset]).fetchall()

        return {
            "items": [_row_to_task(row) for row in items],
            "total": total,
            "page": page,
            "page_size": page_size
        }

@app.get("/tasks/{id}", response_model=Task)
def get_task(id: int = Path(..., description="Task ID")):
    """
    Retrieve a single task by ID.
    """
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")
        return _row_to_task(row)

@app.put("/tasks/{id}", response_model=Task)
def update_task(
    id: int = Path(..., description="Task ID"),
    update_data: TaskUpdate = Body(...)
):
    """
    Partially update a task.
    """
    with get_db_connection() as conn:
        # Check if task exists
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")

        # Prepare update values
        update_dict = update_data.dict(exclude_unset=True)
        
        # Validate manually if title or priority changed
        if "title" in update_dict:
            t = update_dict["title"].strip()
            if not t:
                raise HTTPException(status_code=422, detail="Title cannot be empty")
            update_dict["title"] = t

        if "priority" in update_dict:
            allowed = ["low", "medium", "high"]
            if update_dict["priority"] not in allowed:
                raise HTTPException(status_code=422, detail="Invalid priority")

        if not update_dict:
            # If no valid fields to update, return current task
            return _row_to_task(row)

        # Handle boolean to integer conversion
        if "completed" in update_dict:
            update_dict["completed"] = 1 if update_dict["completed"] else 0

        # Construct SET clause
        set_clauses = []
        values = []
        
        for key, value in update_dict.items():
            set_clauses.append(f"{key} = ?")
            values.append(value)
        
        # Always update updated_at? Spec doesn't require it, so skip.
        # Always include id in where clause
        values.append(id)

        update_sql = f"UPDATE tasks SET {', '.join(set_clauses)} WHERE id = ?"
        conn.execute(update_sql, values)
        conn.commit()

        # Fetch updated row
        updated_row = conn.execute("SELECT * FROM tasks WHERE id = ?", (id,)).fetchone()
        return _row_to_task(updated_row)

@app.delete("/tasks/{id}")
def delete_task(id: int = Path(..., description="Task ID")):
    """
    Delete a task by ID.
    """
    with get_db_connection() as conn:
        cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Task not found")
        return None

# --- Helpers ---

def _row_to_task(row: sqlite3.Row) -> Task:
    """Convert sqlite3.Row to Task Pydantic model."""
    return Task(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        priority=row["priority"],
        completed=bool(row["completed"]),
        created_at=row["created_at"]
    )
```