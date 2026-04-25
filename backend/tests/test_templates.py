def test_templates_endpoints_removed(client):
    response = client.get("/api/templates")
    assert response.status_code == 404
