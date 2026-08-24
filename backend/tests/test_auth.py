def test_register_creates_user(client):
    res = client.post("/api/auth/register", json={"name": "Alice", "email": "alice@example.com", "password": "secret123"})
    assert res.status_code == 201
    body = res.json()
    assert body["user"]["email"] == "alice@example.com"
    assert "access_token" in body


def test_register_duplicate_email_rejected(client):
    client.post("/api/auth/register", json={"name": "Alice", "email": "alice@example.com", "password": "secret123"})
    res = client.post("/api/auth/register", json={"name": "Alice 2", "email": "alice@example.com", "password": "secret123"})
    assert res.status_code == 400


def test_login_wrong_password_rejected(client):
    client.post("/api/auth/register", json={"name": "Bob", "email": "bob@example.com", "password": "secret123"})
    res = client.post("/api/auth/login", json={"email": "bob@example.com", "password": "wrongpass"})
    assert res.status_code == 401


def test_me_requires_auth(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_me_returns_current_user(client, auth_headers):
    res = client.get("/api/auth/me", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["email"] == "test@example.com"
