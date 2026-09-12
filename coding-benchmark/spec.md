# Task Tracker API — Spec

Build a REST API for tracking tasks, using **FastAPI** + **SQLite**.

## Technical constraints (fixed, so output is testable across models)

- Entrypoint file: `main.py`, at the project root.
- The FastAPI app instance must be importable as `main.app`.
- Storage: SQLite, in a file named `tasks.db` in the working directory. Create the DB/table automatically on startup if it doesn't exist (no manual migration step).
- Allowed dependencies: `fastapi`, `uvicorn`, `pydantic`, and either the stdlib `sqlite3` or `sqlalchemy`. No other framework substitutions (e.g. no Flask/Django).
- No authentication, no multi-user concerns — single shared task list.

## Data model: Task

| Field | Type | Notes |
|---|---|---|
| id | int | auto-increment, assigned by the server |
| title | str | required, 1–200 chars (non-empty after trim) |
| description | str \| null | optional, no length limit |
| completed | bool | defaults to `false` on creation |
| priority | str | one of `low`, `medium`, `high`; defaults to `medium` |
| created_at | datetime (ISO 8601 string) | set by the server on creation, never client-supplied |

## Endpoints

### `POST /tasks` — create a task
- Body: `{ "title": str, "description"?: str, "priority"?: str }`
- On success: `201`, returns the full Task object (including generated `id`, `completed=false`, `created_at`).
- `422` if `title` missing/empty, or `priority` not one of the allowed values.

### `GET /tasks` — list tasks
- Query params (all optional):
  - `completed`: bool — filter by completion state
  - `priority`: str — filter by priority (`422` if not a valid value)
  - `page`: int, default `1`, must be `>= 1` (`422` otherwise)
  - `page_size`: int, default `10`, must be `1–100` inclusive (`422` otherwise)
- Response `200`: `{ "items": [Task, ...], "total": int, "page": int, "page_size": int }`
  - `total` is the count matching the filters (not just the current page).
  - Tasks ordered by `id` ascending.

### `GET /tasks/{id}` — get one task
- `200` with the Task if found.
- `404` if no task with that id exists.

### `PUT /tasks/{id}` — partial update
- Body: any subset of `{ "title", "description", "completed", "priority" }`. Omitted fields are left unchanged.
- `200` with the updated Task on success.
- `404` if the task doesn't exist.
- `422` if a provided field fails the same validation as on create (empty title, bad priority).

### `DELETE /tasks/{id}` — delete a task
- `204` (empty body) on success.
- `404` if the task doesn't exist.

## Non-goals
Auth, users/ownership, sorting options beyond `id`, soft-delete, rate limiting — none of this is required. Keep it focused on the endpoints above.
