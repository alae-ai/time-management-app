from __future__ import annotations

from datetime import timedelta

from tm.dates import today


def _create_task(client, future_day, **overrides):
    payload = {
        "title": "TP report",
        "project": "TP",
        "notes": "",
        "deadline": future_day.isoformat(),
    }
    payload.update(overrides)
    response = client.post("/api/tasks", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["llm_configured"] is False


def test_settings_defaults_and_update(client, future_day):
    data = client.get("/api/settings").json()
    assert data["day_start"] == "08:00"
    assert data["day_end"] == "22:00"
    assert data["granularity_min"] == 30

    updated = client.patch(
        "/api/settings",
        json={"day_start": "09:00", "day_end": "18:00", "granularity_min": 15},
    )
    assert updated.status_code == 200
    assert updated.json()["day_start"] == "09:00"

    slots = client.get(
        "/api/free-slots",
        params={"from": future_day.isoformat(), "to": future_day.isoformat()},
    ).json()
    assert slots["window"] == {"start": "09:00", "end": "18:00"}
    assert slots["slots"][0]["start"] == "09:00"
    assert slots["slots"][0]["end"] == "18:00"


def test_invalid_settings_rejected(client):
    response = client.patch(
        "/api/settings", json={"day_start": "21:00", "day_end": "08:00"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


def test_task_lifecycle_and_deadline_formats(client, future_day):
    deadline = future_day.strftime("%d/%m/%Y")
    task = _create_task(
        client,
        future_day,
        deadline=deadline,
        deadline_time="17:00",
    )
    assert task["deadline"] == future_day.isoformat()
    assert task["deadline_time"] == "17:00"
    assert task["done"] is False

    listed = client.get("/api/tasks").json()
    assert [item["id"] for item in listed] == [task["id"]]

    done = client.patch(f"/api/tasks/{task['id']}", json={"done": True})
    assert done.status_code == 200
    assert done.json()["done"] is True
    assert done.json()["done_at"] is not None

    assert client.get("/api/tasks", params={"status": "open"}).json() == []

    reopened = client.patch(f"/api/tasks/{task['id']}", json={"done": False})
    assert reopened.json()["done"] is False
    assert reopened.json()["done_at"] is None


def test_invalid_task_payload(client):
    response = client.post("/api/tasks", json={"title": "   "})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"

    response = client.post("/api/tasks", json={"title": "x", "deadline": "31/02/2030"})
    assert response.status_code == 400

    response = client.post(
        "/api/tasks", json={"title": "x", "deadline_time": "17:00"}
    )
    assert response.status_code == 400


def test_schedule_session_and_free_slots(client, future_day):
    task = _create_task(client, future_day)
    response = client.post(
        f"/api/tasks/{task['id']}/sessions",
        json={
            "date": future_day.isoformat(),
            "start": "10:00",
            "end": "12:00",
        },
    )
    assert response.status_code == 201, response.text
    block = response.json()
    assert block["kind"] == "session"
    assert block["task_id"] == task["id"]
    assert block["task_title"] == task["title"]

    slots = client.get(
        "/api/free-slots",
        params={"from": future_day.isoformat(), "to": future_day.isoformat()},
    ).json()
    assert [(slot["start"], slot["end"]) for slot in slots["slots"]] == [
        ("08:00", "10:00"),
        ("12:00", "22:00"),
    ]


def test_all_day_session(client, future_day):
    task = _create_task(client, future_day)
    response = client.post(
        f"/api/tasks/{task['id']}/sessions",
        json={"date": future_day.isoformat(), "all_day": True},
    )
    assert response.status_code == 201
    block = response.json()
    assert block["all_day"] is True
    assert block["start"] is None

    slots = client.get(
        "/api/free-slots",
        params={"from": future_day.isoformat(), "to": future_day.isoformat()},
    ).json()
    assert slots["slots"] == []


def test_conflict_returns_409_and_can_be_forced(client, future_day):
    first = client.post(
        "/api/blocks",
        json={
            "title": "Dentist",
            "kind": "appointment",
            "date": future_day.isoformat(),
            "start": "10:00",
            "end": "11:00",
        },
    )
    assert first.status_code == 201

    payload = {
        "title": "Overlap",
        "kind": "appointment",
        "date": future_day.isoformat(),
        "start": "10:30",
        "end": "11:30",
    }
    conflict = client.post("/api/blocks", json=payload)
    assert conflict.status_code == 409
    error = conflict.json()["error"]
    assert error["code"] == "conflict"
    assert len(error["details"]) == 1
    assert error["details"][0]["title"] == "Dentist"

    forced = client.post("/api/blocks", json={**payload, "allow_overlap": True})
    assert forced.status_code == 201


def test_all_day_block_conflicts_with_timed_block(client, future_day):
    client.post(
        "/api/blocks",
        json={
            "title": "Conference",
            "kind": "appointment",
            "date": future_day.isoformat(),
        },
    )
    response = client.post(
        "/api/blocks",
        json={
            "title": "Coffee",
            "kind": "appointment",
            "date": future_day.isoformat(),
            "start": "10:00",
            "end": "11:00",
        },
    )
    assert response.status_code == 409


def test_update_block_checks_conflicts(client, future_day):
    client.post(
        "/api/blocks",
        json={
            "title": "A",
            "kind": "appointment",
            "date": future_day.isoformat(),
            "start": "09:00",
            "end": "10:00",
        },
    ).json()
    second = client.post(
        "/api/blocks",
        json={
            "title": "B",
            "kind": "appointment",
            "date": future_day.isoformat(),
            "start": "11:00",
            "end": "12:00",
        },
    ).json()

    response = client.patch(
        f"/api/blocks/{second['id']}",
        json={"start": "09:30", "end": "10:30"},
    )
    assert response.status_code == 409

    moved = client.patch(
        f"/api/blocks/{second['id']}",
        json={"start": "09:30", "end": "10:30", "allow_overlap": True},
    )
    assert moved.status_code == 200
    assert moved.json()["start"] == "09:30"


def test_delete_task_cascades_sessions(client, future_day):
    task = _create_task(client, future_day)
    block = client.post(
        f"/api/tasks/{task['id']}/sessions",
        json={
            "date": future_day.isoformat(),
            "start": "10:00",
            "end": "11:00",
        },
    ).json()

    response = client.delete(f"/api/tasks/{task['id']}")
    assert response.status_code == 204
    assert client.get(f"/api/blocks/{block['id']}").status_code == 404
    assert client.get(f"/api/tasks/{task['id']}").status_code == 404


def test_done_task_frees_its_sessions(client, future_day):
    task = _create_task(client, future_day)
    client.post(
        f"/api/tasks/{task['id']}/sessions",
        json={
            "date": future_day.isoformat(),
            "start": "10:00",
            "end": "12:00",
        },
    )
    client.patch(f"/api/tasks/{task['id']}", json={"done": True})

    slots = client.get(
        "/api/free-slots",
        params={"from": future_day.isoformat(), "to": future_day.isoformat()},
    ).json()
    assert len(slots["slots"]) == 1
    assert slots["slots"][0]["all_day"] is True


def test_state_and_export(client, future_day):
    task = _create_task(client, future_day)
    client.post(
        "/api/blocks",
        json={
            "title": "Dentist",
            "kind": "appointment",
            "date": future_day.isoformat(),
            "start": "09:00",
            "end": "10:00",
        },
    )

    state = client.get(
        "/api/state",
        params={"from": future_day.isoformat(), "to": future_day.isoformat()},
    ).json()
    assert state["tasks"][0]["id"] == task["id"]
    assert state["blocks"][0]["title"] == "Dentist"
    assert state["settings"]["day_start"] == "08:00"

    exported = client.get("/api/export").json()
    assert exported["tasks"][0]["id"] == task["id"]
    assert len(exported["blocks"]) == 1


def test_state_defaults_to_a_month(client):
    response = client.get("/api/state")
    assert response.status_code == 200
    assert response.json()["today"] == today().isoformat()


def test_free_slots_range_validation(client, future_day):
    response = client.get(
        "/api/free-slots",
        params={
            "from": (future_day + timedelta(days=2)).isoformat(),
            "to": future_day.isoformat(),
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


def test_unknown_ids_return_404(client):
    assert client.get("/api/tasks/nope").status_code == 404
    assert client.get("/api/blocks/nope").status_code == 404
    assert client.delete("/api/tasks/nope").status_code == 404
