from fastapi.testclient import TestClient
from wenyi_desktop.main import create_app, create_context

HEADERS = {
    "Authorization": "Bearer fake-portable-token",
    "Origin": "tauri://localhost",
}


def test_create_lock_unlock_and_change_passphrase(tmp_path):
    context = create_context(tmp_path, portable=True, api_token="fake-portable-token")
    try:
        with TestClient(create_app(context=context)) as client:
            status = client.get("/desktop/portable-credentials", headers=HEADERS)
            assert status.status_code == 200
            assert status.json() == {
                "supported": True,
                "present": False,
                "unlocked": False,
                "auto_unlock": False,
            }
            assert (
                client.post(
                    "/desktop/portable-credentials/create",
                    headers=HEADERS,
                    json={"passphrase": "short"},
                ).status_code
                == 422
            )
            created = client.post(
                "/desktop/portable-credentials/create",
                headers=HEADERS,
                json={"passphrase": "correct horse battery"},
            )
            assert created.status_code == 200
            assert created.json()["unlocked"] is True
            locked = client.post("/desktop/portable-credentials/lock", headers=HEADERS)
            assert locked.json()["unlocked"] is False
            assert (
                client.post(
                    "/desktop/portable-credentials/unlock",
                    headers=HEADERS,
                    json={"passphrase": "wrong passphrase"},
                ).status_code
                == 400
            )
            assert (
                client.post(
                    "/desktop/portable-credentials/unlock",
                    headers=HEADERS,
                    json={"passphrase": "correct horse battery"},
                ).json()["unlocked"]
                is True
            )
            changed = client.post(
                "/desktop/portable-credentials/passphrase",
                headers=HEADERS,
                json={
                    "current": "correct horse battery",
                    "next": "another correct horse",
                },
            )
            assert changed.status_code == 200
    finally:
        context.repository.close()


def test_non_portable_build_reports_unsupported(tmp_path):
    context = create_context(tmp_path, api_token="fake-portable-token")
    try:
        with TestClient(create_app(context=context)) as client:
            assert client.get("/desktop/portable-credentials", headers=HEADERS).json() == {
                "supported": False,
                "present": False,
                "unlocked": False,
                "auto_unlock": False,
            }
            assert (
                client.post("/desktop/portable-credentials/lock", headers=HEADERS).status_code
                == 400
            )
    finally:
        context.repository.close()
