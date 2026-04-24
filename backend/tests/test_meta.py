def test_root_status(client):
    response = client.get("/api/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "service" in data
