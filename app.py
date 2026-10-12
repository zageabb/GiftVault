"""GiftVault MVP. All gift access decisions happen on the server."""
import ipaddress
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, abort, g, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

STATUSES = ("idea", "planned", "ordered", "bought", "received", "wrapped", "given")
MAX_PHOTO_BYTES = 8 * 1024 * 1024
PHOTO_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        DATA_DIR=os.environ.get("GIFT_DATA_DIR", ".local-data"),
        AUTH_HEADER=os.environ.get("GIFT_AUTH_HEADER", "X-Authenticated-User"),
        TRUSTED_PROXY_IPS=os.environ.get("GIFT_TRUSTED_PROXY_IPS", ""),
        USERS=os.environ.get("GIFT_USERS", ""),
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,
    )
    if config:
        app.config.update(config)
    root = Path(app.config["DATA_DIR"]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    (root / "photos").mkdir(exist_ok=True)
    db_path = root / "giftvault.sqlite3"

    def db():
        if "db" not in g:
            g.db = sqlite3.connect(db_path)
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys=ON")
        return g.db

    with sqlite3.connect(db_path) as conn:
        conn.executescript("""
          PRAGMA foreign_keys=ON;
          CREATE TABLE IF NOT EXISTS recipients (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE
          );
          CREATE TABLE IF NOT EXISTS gifts (
            id INTEGER PRIMARY KEY, recipient_id INTEGER NOT NULL REFERENCES recipients(id),
            year INTEGER NOT NULL, creator TEXT NOT NULL,
            title TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'idea',
            estimated_pence INTEGER NOT NULL DEFAULT 0,
            actual_pence INTEGER NOT NULL DEFAULT 0,
            visibility TEXT NOT NULL DEFAULT 'private',
            photo_name TEXT, created_at TEXT NOT NULL
          );
          CREATE INDEX IF NOT EXISTS gifts_visibility_idx ON gifts(creator,visibility,year);
        """)

    @app.teardown_appcontext
    def close_db(_exc):
        conn = g.pop("db", None)
        if conn:
            conn.close()

    @app.before_request
    def authenticate():
        try:
            peer = ipaddress.ip_address(request.remote_addr)
            trusted = {ipaddress.ip_address(v.strip()) for v in app.config["TRUSTED_PROXY_IPS"].split(",") if v.strip()}
        except ValueError:
            abort(403)
        if not trusted or peer not in trusted:
            abort(403)
        header = app.config["AUTH_HEADER"]
        username = request.headers.get(header, "").strip()
        allowed = {u.strip() for u in app.config["USERS"].split(",") if u.strip()}
        if not username or username not in allowed:
            abort(403)
        g.user = username

    def token():
        if request.form.get("_csrf") != g.csrf:
            abort(403)

    # Stateless CSRF with HTTP Origin verification: browser form submits must
    # supply a matching origin or referer; rejected when missing.
    @app.before_request
    def origin_check():
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return
        from urllib.parse import urlsplit
        origin = request.headers.get("Origin") or request.headers.get("Referer")
        if not origin:
            abort(403)
        a, b = urlsplit(origin), urlsplit(request.host_url)
        if (a.scheme, a.netloc) != (b.scheme, b.netloc):
            abort(403)

    @app.context_processor
    def context():
        return {"statuses": STATUSES}

    @app.get("/")
    def index():
        year = request.args.get("year", str(datetime.now().year), type=str)
        if not year.isdigit() or not (2020 <= int(year) <= 2100):
            abort(400)
        gifts = db().execute("""
          SELECT gifts.*, recipients.name AS recipient_name
          FROM gifts JOIN recipients ON recipients.id=gifts.recipient_id
          WHERE gifts.year=? AND (gifts.creator=? OR gifts.visibility='shared')
          ORDER BY recipients.name, gifts.id DESC
        """, (int(year), g.user)).fetchall()
        recipients = db().execute("SELECT * FROM recipients ORDER BY name").fetchall()
        return render_template("index.html", gifts=gifts, recipients=recipients,
                               year=int(year), user=g.user,
                               total=sum(item["actual_pence"] for item in gifts) / 100)

    @app.post("/recipients")
    def add_recipient():
        name = request.form.get("name", "").strip()[:100]
        if not name:
            abort(400)
        db().execute("INSERT OR IGNORE INTO recipients(name) VALUES (?)", (name,))
        db().commit()
        return redirect(url_for("index"))

    def parse_money(value):
        from decimal import Decimal, InvalidOperation
        try:
            d = Decimal(value or "0")
            p = d * 100
            if not d.is_finite() or d < 0 or p != p.to_integral_value() or p > 100_000_000:
                raise ValueError
            return int(p)
        except (InvalidOperation, ValueError):
            abort(400)

    @app.post("/gifts")
    def add_gift():
        try:
            rid = int(request.form.get("recipient_id", ""))
            year = int(request.form.get("year", ""))
        except ValueError:
            abort(400)
        if not 2020 <= year <= 2100:
            abort(400)
        if not db().execute("SELECT 1 FROM recipients WHERE id=?", (rid,)).fetchone():
            abort(400)
        title = request.form.get("title", "").strip()[:200]
        if not title:
            abort(400)
        status = request.form.get("status", "idea")
        if status not in STATUSES:
            abort(400)
        visibility = request.form.get("visibility", "private")
        if visibility not in ("private", "shared"):
            abort(400)
        cur = db().execute("""
          INSERT INTO gifts(recipient_id,year,creator,title,notes,status,estimated_pence,actual_pence,visibility,created_at)
          VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (rid,year,g.user,title,request.form.get("notes","")[:4000],status,
              parse_money(request.form.get("estimated")),parse_money(request.form.get("actual")),
              visibility,datetime.now(timezone.utc).isoformat()))
        db().commit()
        return redirect(url_for("index", year=year))

    def visible_gift(gift_id, owner_only=False):
        row = db().execute("SELECT * FROM gifts WHERE id=? AND (creator=? OR visibility='shared')",
                           (gift_id,g.user)).fetchone()
        if not row or (owner_only and row["creator"] != g.user):
            abort(404)
        return row

    @app.post("/gifts/<int:gift_id>/status")
    def change_status(gift_id):
        row = visible_gift(gift_id, owner_only=True)
        status = request.form.get("status", "")
        if status not in STATUSES:
            abort(400)
        db().execute("UPDATE gifts SET status=? WHERE id=?", (status,gift_id))
        db().commit()
        return redirect(url_for("index", year=row["year"]))

    @app.post("/gifts/<int:gift_id>/visibility")
    def change_visibility(gift_id):
        row = visible_gift(gift_id, owner_only=True)
        visibility = request.form.get("visibility")
        if visibility not in ("private", "shared"):
            abort(400)
        db().execute("UPDATE gifts SET visibility=? WHERE id=?", (visibility,gift_id))
        db().commit()
        return redirect(url_for("index", year=row["year"]))

    @app.post("/gifts/<int:gift_id>/photo")
    def upload_photo(gift_id):
        row = visible_gift(gift_id, owner_only=True)
        f = request.files.get("photo")
        if not f:
            abort(400)
        # Decode and re-encode to avoid untrusted original bytes and embedded GPS data.
        from PIL import Image, UnidentifiedImageError
        import io
        raw = f.read(MAX_PHOTO_BYTES + 1)
        if len(raw) > MAX_PHOTO_BYTES:
            abort(413)
        try:
            img = Image.open(io.BytesIO(raw))
            img.verify()
            img = Image.open(io.BytesIO(raw))
            img.thumbnail((1600,1600))
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
        except (UnidentifiedImageError, OSError, ValueError):
            abort(400)
        name = uuid.uuid4().hex + ".jpg"
        destination = root / "photos" / name
        img.save(destination, format="JPEG", quality=82)
        old = row["photo_name"]
        db().execute("UPDATE gifts SET photo_name=? WHERE id=?", (name,gift_id))
        db().commit()
        if old:
            (root / "photos" / old).unlink(missing_ok=True)
        return redirect(url_for("index", year=row["year"]))

    @app.get("/gifts/<int:gift_id>/photo")
    def get_photo(gift_id):
        row = visible_gift(gift_id)
        if not row["photo_name"]:
            abort(404)
        response = send_file(root / "photos" / row["photo_name"], mimetype="image/jpeg")
        response.headers["Cache-Control"] = "private, no-store"
        return response

    @app.after_request
    def security_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'"
        return response

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=int(os.environ.get("PORT", 5088)))
