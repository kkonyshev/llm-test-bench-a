import os
import pytest
from fastapi.testclient import TestClient

DB_PATH = "tasks.db"


@pytest.fixture(autouse=True)
def clean_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)


@pytest.fixture
def client():
    import importlib
    import main
    importlib.reload(main)
    with TestClient(main.app) as c:
        yield c


def create_task(client, **overrides):
    body = {"title": "Test task"}
    body.update(overrides)
    return client.post("/tasks", json=body)


# --- create ---

def test_create_task_minimal(client):
    r = create_task(client)
    assert r.status_code == 201
    data = r.json()
    assert data["title"] == "Test task"
    assert data["description"] is None
    assert data["completed"] is False
    assert data["priority"] == "medium"
    assert isinstance(data["id"], int)
    assert "created_at" in data and data["created_at"]


def test_create_task_full(client):
    r = create_task(client, title="Buy milk", description="2%", priority="high")
    assert r.status_code == 201
    data = r.json()
    assert data["title"] == "Buy milk"
    assert data["description"] == "2%"
    assert data["priority"] == "high"


def test_create_task_missing_title(client):
    r = client.post("/tasks", json={"description": "no title"})
    assert r.status_code == 422


def test_create_task_empty_title(client):
    r = create_task(client, title="")
    assert r.status_code == 422


def test_create_task_invalid_priority(client):
    r = create_task(client, priority="urgent")
    assert r.status_code == 422


def test_create_task_title_too_long(client):
    r = create_task(client, title="x" * 201)
    assert r.status_code == 422


# --- get single ---

def test_get_task_found(client):
    created = create_task(client, title="Findme").json()
    r = client.get(f"/tasks/{created['id']}")
    assert r.status_code == 200
    assert r.json()["title"] == "Findme"


def test_get_task_not_found(client):
    r = client.get("/tasks/99999")
    assert r.status_code == 404


# --- list / filtering / pagination ---

def test_list_empty(client):
    r = client.get("/tasks")
    assert r.status_code == 200
    data = r.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["page_size"] == 10


def test_list_returns_all_and_ordered(client):
    ids = [create_task(client, title=f"t{i}").json()["id"] for i in range(3)]
    r = client.get("/tasks")
    data = r.json()
    assert data["total"] == 3
    assert [t["id"] for t in data["items"]] == ids


def test_list_filter_by_completed(client):
    a = create_task(client, title="a").json()
    create_task(client, title="b")
    client.put(f"/tasks/{a['id']}", json={"completed": True})

    r = client.get("/tasks", params={"completed": True})
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == a["id"]

    r = client.get("/tasks", params={"completed": False})
    assert r.json()["total"] == 1


def test_list_filter_by_priority(client):
    create_task(client, title="a", priority="low")
    create_task(client, title="b", priority="high")
    r = client.get("/tasks", params={"priority": "high"})
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["priority"] == "high"


def test_list_filter_invalid_priority(client):
    r = client.get("/tasks", params={"priority": "urgent"})
    assert r.status_code == 422


def test_list_pagination(client):
    for i in range(15):
        create_task(client, title=f"t{i}")

    r = client.get("/tasks", params={"page": 1, "page_size": 10})
    data = r.json()
    assert len(data["items"]) == 10
    assert data["total"] == 15
    assert data["page"] == 1

    r = client.get("/tasks", params={"page": 2, "page_size": 10})
    data = r.json()
    assert len(data["items"]) == 5
    assert data["page"] == 2


def test_list_invalid_page(client):
    r = client.get("/tasks", params={"page": 0})
    assert r.status_code == 422


def test_list_invalid_page_size(client):
    r = client.get("/tasks", params={"page_size": 101})
    assert r.status_code == 422
    r = client.get("/tasks", params={"page_size": 0})
    assert r.status_code == 422


# --- update ---

def test_update_partial_field(client):
    created = create_task(client, title="orig", description="d", priority="low").json()
    r = client.put(f"/tasks/{created['id']}", json={"completed": True})
    assert r.status_code == 200
    data = r.json()
    assert data["completed"] is True
    assert data["title"] == "orig"
    assert data["description"] == "d"
    assert data["priority"] == "low"


def test_update_multiple_fields(client):
    created = create_task(client).json()
    r = client.put(
        f"/tasks/{created['id']}",
        json={"title": "new title", "priority": "high"},
    )
    data = r.json()
    assert data["title"] == "new title"
    assert data["priority"] == "high"


def test_update_not_found(client):
    r = client.put("/tasks/99999", json={"completed": True})
    assert r.status_code == 404


def test_update_invalid_priority(client):
    created = create_task(client).json()
    r = client.put(f"/tasks/{created['id']}", json={"priority": "urgent"})
    assert r.status_code == 422


def test_update_empty_title(client):
    created = create_task(client).json()
    r = client.put(f"/tasks/{created['id']}", json={"title": ""})
    assert r.status_code == 422


# --- delete ---

def test_delete_found(client):
    created = create_task(client).json()
    r = client.delete(f"/tasks/{created['id']}")
    assert r.status_code == 204
    r = client.get(f"/tasks/{created['id']}")
    assert r.status_code == 404


def test_delete_not_found(client):
    r = client.delete("/tasks/99999")
    assert r.status_code == 404
