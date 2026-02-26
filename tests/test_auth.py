import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_guest_auth():
    print("Testing Guest Auth...")
    # 1. Get Guest Token
    resp = requests.post(f"{BASE_URL}/auth/guest")
    assert resp.status_code == 200
    data = resp.json()
    token = data["access_token"]
    owner_id = data["owner_id"]
    print(f"Guest Token created for {owner_id}")

    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get Config (Public but now auth'd)
    resp = requests.get(f"{BASE_URL}/api/config", headers=headers)
    assert resp.status_code == 200

    # 3. Create a fake YouTube task
    payload = {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
    resp = requests.post(f"{BASE_URL}/api/youtube/analyze", json=payload, headers=headers)
    assert resp.status_code == 201
    task_id = resp.json()["id"]
    print(f"Created Task {task_id}")

    # 4. List tasks (Should see only 1)
    resp = requests.get(f"{BASE_URL}/api/youtube", headers=headers)
    tasks = resp.json()
    assert len(tasks) >= 1
    assert any(t["id"] == task_id for t in tasks)

    # 5. Access without token should fail
    resp = requests.get(f"{BASE_URL}/api/youtube")
    assert resp.status_code == 401

    # 6. Delete task
    resp = requests.delete(f"{BASE_URL}/api/youtube/{task_id}", headers=headers)
    assert resp.status_code == 204

    print("✅ Guest Auth Test Passed!")


if __name__ == "__main__":
    time.sleep(1) # wait for server config
    test_guest_auth()
