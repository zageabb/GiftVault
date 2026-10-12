import io
import pytest
from app import create_app

@pytest.fixture
def client(tmp_path):
    app=create_app({"TESTING":True,"DATA_DIR":str(tmp_path),
                    "TRUSTED_PROXY_IPS":"127.0.0.1","USERS":"gez,tanya"})
    return app.test_client()

def headers(user="gez"):
    return {"X-UDA-User":user}

def post(client,path, data, user="gez"):
    return client.post(path,data=data,headers={**headers(user),"Origin":"http://localhost"})

def test_identity_required(client):
    assert client.get("/").status_code==403
    assert client.get("/",headers=headers("unknown")).status_code==403

def test_health_does_not_require_identity(client):
    assert client.get("/health").get_json()=={"status":"ok"}

def test_uda_forwarded_prefix_is_used_for_links_and_redirects(client):
    prefixed={**headers(),"X-Forwarded-Prefix":"/apps/giftvault"}
    page=client.get("/",headers=prefixed)
    assert b'action="/apps/giftvault/recipients"' in page.data
    response=client.post(
        "/recipients",
        data={"name":"Tanya"},
        headers={**prefixed,"Origin":"http://localhost"},
    )
    assert response.headers["Location"]=="/apps/giftvault/"

def test_private_gifts_invisible_in_totals(client):
    assert post(client,"/recipients",{"name":"Tanya"}).status_code==302
    assert post(client,"/gifts",{"recipient_id":"1","year":"2026","title":"Secret surprise","actual":"150","visibility":"private"}).status_code==302
    mine=client.get("/?year=2026",headers=headers("gez")).data
    other=client.get("/?year=2026",headers=headers("tanya")).data
    assert b"Secret surprise" in mine
    assert b"150.00" in mine
    assert b"Secret surprise" not in other
    assert b"150.00" not in other
    assert client.get("/gifts/1/photo",headers=headers("tanya")).status_code==404
    assert post(client,"/gifts/1/visibility",{"visibility":"shared"},user="tanya").status_code==404
    assert post(client,"/gifts/1/visibility",{"visibility":"shared"}).status_code==302
    assert b"Secret surprise" in client.get("/?year=2026",headers=headers("tanya")).data

def test_photo_protected(client):
    from PIL import Image
    img=Image.new("RGB",(8,8),"green")
    buf=io.BytesIO()
    img.save(buf,format="PNG")
    post(client,"/recipients",{"name":"Courtney"})
    post(client,"/gifts",{"recipient_id":"1","year":"2026","title":"Secret","visibility":"private"})
    response=post(client,"/gifts/1/photo",{"photo":(io.BytesIO(buf.getvalue()),"photo.png")})
    assert response.status_code==302
    assert client.get("/gifts/1/photo",headers=headers("gez")).status_code==200
    assert client.get("/gifts/1/photo",headers=headers("tanya")).status_code==404

def test_csrf_origin_required(client):
    assert client.post("/recipients",data={"name":"Bad"},headers=headers()).status_code==403
