# GiftVault

Private Christmas gift planning for two accounts, with an ordinary responsive browser interface on desktop, iPhone Safari and Android Chrome.

## Security model

- Reverse proxy authenticates users; GiftVault requires a verified identity header **only** from a configured trusted proxy IP. It will reject requests otherwise. The proxy **must overwrite** any incoming identity header (never forward a browser-supplied value).
- UDA forwards the authenticated **email address** as `X-UDA-User`; the `GIFT_USERS` allowlist must contain those exact email addresses, not display names. Set `GIFT_AUTH_HEADER` (default `X-UDA-User`, matching UDA `forward_auth`), `GIFT_TRUSTED_PROXY_IPS` (comma-separated IP addresses), and `GIFT_USERS` (comma-separated accepted proxy usernames).
- A gift belongs to its creator and is either private or explicitly shared. Hidden gifts never appear in other users' lists, totals, searches or attachment responses. Recipient names can be shared, but the existence of private gifts must not leak.
- Production only through a correctly configured TLS proxy; bind the upstream service to a private interface / loopback and block bypass connections. Configure proxies carefully when using containers (REMOTE_ADDR must match the actual trusted connection peer).
- Sessionless per-request proxy authentication, no local password database.

## Quick start

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export GIFT_USERS='gez,tanya'
export GIFT_TRUSTED_PROXY_IPS='127.0.0.1'
export GIFT_DATA_DIR="$PWD/.local-data"
python app.py
```

Open only via your configured authenticated reverse proxy. A direct browser request should be denied. The deployment instructions are intentionally incomplete until the Caddy/auth-provider identity header and network topology are verified.

## Core functionality

- Add recipients, Christmas years and gifts (planned, ordered, purchased, received, wrapped, given)
- Gifts default to **private**. Only their creator may mark them shared or change/delete them.
- An optional image can be captured using phone camera or selected from library. Images are access-controlled via the server.
- Per-viewer budgets/totals are derived only from visible gifts.
- SQLite stores gifts; photo files are outside the repository in `GIFT_DATA_DIR`.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

## Deployment

See [DEVELOPMENT.md](DEVELOPMENT.md). Never commit actual purchases, gift images, secrets or production database files to this public repository.

## Mobile login/access denied troubleshooting

An UDA portal sign-in or **Access denied** page occurs **before** GiftVault receives the request.

1. Use the same public **HTTPS host** and `/apps/<slug>/` URL as desktop (not the LAN HTTP address). In Safari/Chrome mobile, open the portal home first and log in there, then open GiftVault from its portal tile, in the **same browser**.
2. Ensure the mobile login is verified in UDA. If login succeeds but the portal says Access denied, an UDA admin must assign GiftVault directly to the authenticated email account or put the account in the proxy entitlement group. UDA `/auth/check` returns **401** if no portal session, **403** if the user has no entitlement.
3. Avoid switching between the public HTTPS portal and an HTTP/IP-based LAN portal: secure cookie behaviour and browser cookie jars differ, especially on phones and private browsing.
4. The UDA proxy forwards the **X-UDA-User** identity header. Confirm `GIFT_AUTH_HEADER=X-UDA-User` (now the default) and set `GIFT_USERS` to exact UDA login email addresses. UDA must replace, never trust, client-supplied identity headers.
5. Only if the **GiftVault application's own** 403 appears: inspect trusted peer IPs and allowlist, keeping the proxy bypass protections intact.

Do not disable UDA authorization, remove cookie security, change Caddy to permit anonymous access, or broadly trust forwarded user headers. The running Caddy/UDA instance and its logs must be checked on the Ubuntu server to conclusively identify the mobile 401/403; GitHub code alone cannot inspect mobile sessions.
