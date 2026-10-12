# GiftVault development plan

## Phase 1 — Runnable privacy-first MVP
- [x] Flask and SQLite scaffold
- [x] Per-request trusted-proxy authenticated identity
- [x] Private-by-default gift visibility enforced in SQL
- [x] Recipient, gift, status and visibility forms
- [x] Browser camera/library upload with server-side photo re-encoding
- [x] Protected image download, no-store response headers
- [x] Verify real reverse-proxy auth integration and request topology in Ubuntu
- [ ] Run test suite in CI and smoke-test on Android Chrome and iPhone Safari

## Phase 2 — Usability and tracking
- [ ] Gift detail editor, deletions/restore and status history
- [ ] Separate purchase, delivery and wrapping states
- [ ] Budget per recipient/year and shopping dashboard
- [ ] Multiple photos, receipt capture and HEIC conversion
- [ ] Advanced filter/search, exports with permission scoping
- [ ] Permission model for selected individual users beyond two accounts

## Phase 3 — Operations
- [ ] Automated backup/restore of SQLite and photo files
- [x] UDA registry entry based on the live Ubuntu deployment conventions
- [ ] Harden image formats, file quotas, upload errors and concurrency
- [ ] Review proxy header behaviour (overwrite/remove spoofed identity headers)
- [ ] Confirm permission leakage tests for search, summary and future endpoints
- [ ] Accessible mobile UI, optional PWA and annual archive

## Important limitations
MVP supports one image per gift and JPEG/PNG/WebP when Pillow decodes them. Some iPhone HEIC photos need a server-side decoder in Phase 2. The browser form captures photos without a native app. The app is not safe for public deployment until the actual reverse-proxy trust configuration is verified. No live UDA deployment is included.
