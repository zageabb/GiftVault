from app import create_app


def test_uda_subpath_probe(tmp_path):
    app = create_app({
        "TESTING": True,
        "DATA_DIR": str(tmp_path),
        "TRUSTED_PROXY_IPS": "127.0.0.1",
        "USERS": "probe@example.test",
        "AUTH_HEADER": "X-UDA-User",
    })
    response = app.test_client().get("/", headers={
        "X-UDA-User": "probe@example.test",
        "X-Forwarded-Prefix": "/apps/giftvault",
    })
    assert response.status_code == 200
    assert b'/apps/giftvault/' in response.data
