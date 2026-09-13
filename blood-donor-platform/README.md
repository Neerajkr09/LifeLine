# LifeLine — Blood Donor-Recipient Connection Platform

A production-structured full-stack platform connecting blood donors with recipients: **FastAPI**
(Python) backend, **React 18 + Vite** frontend, **MongoDB Atlas** database.

```
Recipient raises a verified request  →  Compatible donors nearby see it  →  Donor volunteers
                                     →  Recipient sees who's willing to help
```

---

## 1. Tech stack

| Layer      | Choice                                                                 |
|------------|-------------------------------------------------------------------------|
| Frontend   | React 18, Vite, React Router v6, Tailwind CSS, React Hook Form + Yup, Axios, lucide-react |
| Backend    | FastAPI, Motor (async MongoDB driver), Pydantic v2, PyJWT, bcrypt, slowapi (rate limiting) |
| Database   | MongoDB Atlas                                                          |
| Auth       | JWT bearer tokens, bcrypt password hashing, OTP email verification     |

---

## 2. Project structure

```
blood-donor-platform/
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI app factory: middleware, routers, lifespan
│   │   ├── core/                  # config, database connection, security (JWT/bcrypt)
│   │   ├── models/                # Mongo document shapes + builder functions (not an ORM --
│   │   │                          # Mongo is schema-less; these are typed references)
│   │   ├── schemas/                # Pydantic request/response validation
│   │   ├── routes/                # FastAPI routers (thin -- delegate to controllers)
│   │   ├── controllers/            # Business logic / DB access
│   │   ├── middleware/             # error handling, rate limiting, security headers
│   │   ├── dependencies/           # auth dependency (current user, role guard)
│   │   └── utils/                  # validators, file handling, blood compatibility, serializers
│   ├── tests/                      # pytest suite (see "Testing" below)
│   ├── uploads/                    # local storage for hospital approval documents (dev only)
│   ├── requirements.txt
│   ├── requirements-dev.txt        # test-only deps
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── api/                    # axios instance + one file per resource
    │   ├── components/
    │   │   ├── common/             # Button, Input, Select, Card, Modal, Alert, etc.
    │   │   ├── layout/              # Navbar, Footer, Layout
    │   │   └── auth/                # ProtectedRoute, OtpVerification, RegistrationForm
    │   ├── context/                 # AuthContext (JWT + current user)
    │   ├── hooks/                   # useAuth, useGeolocation
    │   ├── pages/                   # one file per route
    │   ├── routes/                  # AppRoutes.jsx (central route table)
    │   └── utils/                   # yup validation schemas, blood group list
    ├── package.json
    └── .env.example
```

**Why this split:** routes stay thin (HTTP concerns only — parsing, status codes), controllers hold
all business logic and DB calls, schemas own validation, and models document the Mongo document
shape without pretending Mongo is a relational ORM. Adding a new feature (e.g. donor ratings) means
adding a new controller + route + schema without touching existing files.

---

## 3. Setup guide

### Prerequisites
- Python 3.11+
- Node.js 18+
- A MongoDB Atlas cluster (or any MongoDB 6+ instance) and its connection string

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: at minimum set MONGO_URI, MONGO_DB_NAME, and JWT_SECRET_KEY
# generate a strong JWT secret with:
#   python -c "import secrets; print(secrets.token_urlsafe(64))"

uvicorn app.main:app --reload --port 8000
```

The API is now at `http://localhost:8000`. Interactive docs (Swagger UI) are at
`http://localhost:8000/api/docs`, ReDoc at `/api/redoc`.

On startup the app connects to MongoDB and creates all required indexes automatically (see
`app/core/database.py::ensure_indexes`) — no separate migration step needed.

**Email/OTP in local development:** if `SMTP_HOST` is left blank in `.env`, OTPs are printed to the
server console instead of emailed, so the whole registration/verification flow works out of the box
without real SMTP credentials. Set `SMTP_HOST` / `SMTP_USERNAME` / `SMTP_PASSWORD` to send real email.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env   # defaults to http://localhost:8000/api/v1, edit if your API runs elsewhere
npm run dev
```

The app is now at `http://localhost:5173`.

### Testing

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/ -v
```

The test suite (`tests/test_smoke.py`) exercises the entire flow — registration, OTP verification,
login, role-based access, blood request creation (both "for self" and "for someone else"), file
upload validation, document-access security, donor matching, and dashboard stats — against an
in-memory MongoDB mock (`mongomock-motor`), so it runs without a live database.

---

## 4. Environment variables

### Backend (`backend/.env`)

| Variable | Purpose | Default |
|---|---|---|
| `JWT_SECRET_KEY` | Signs access tokens — **change in production** | placeholder |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime | `1440` (24h) |
| `MONGO_URI` | MongoDB Atlas connection string | local placeholder |
| `MONGO_DB_NAME` | Database name | `blood_donor_platform` |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins | `localhost:5173` |
| `OTP_EXPIRE_MINUTES` / `OTP_LENGTH` / `OTP_MAX_ATTEMPTS` | OTP behavior | `10` / `6` / `5` |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USERNAME` / `SMTP_PASSWORD` | Real email delivery (blank = console log) | blank |
| `UPLOAD_DIR` / `MAX_UPLOAD_SIZE_MB` / `ALLOWED_UPLOAD_CONTENT_TYPES` | Hospital document upload rules | `uploads` / `5` / pdf,jpeg,png |
| `RATE_LIMIT_DEFAULT` / `RATE_LIMIT_AUTH` / `RATE_LIMIT_OTP` | Rate limits (per-IP) | `100/min`, `10/min`, `5/min` |

### Frontend (`frontend/.env`)

| Variable | Purpose | Default |
|---|---|---|
| `VITE_API_URL` | Base URL of the backend's `/api/v1` | `http://localhost:8000/api/v1` |

---

## 5. API reference

Full interactive documentation is auto-generated at `/api/docs` once the backend is running. Summary:

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/auth/send-otp` | — | Email a 6-digit verification code |
| POST | `/api/v1/auth/verify-otp` | — | Verify the code |
| POST | `/api/v1/auth/register` | — | Register (donor or recipient); requires prior OTP verification; returns a token (auto-login) |
| POST | `/api/v1/auth/login` | — | Log in; returns a token |
| GET | `/api/v1/users/me` | JWT | Current user's profile |
| POST | `/api/v1/blood-requests` | JWT (recipient) | Create a request — multipart form + file upload |
| GET | `/api/v1/blood-requests/mine` | JWT (recipient) | List my requests |
| GET | `/api/v1/blood-requests/matching` | JWT (donor) | Compatible requests within 5km, nearest first |
| GET | `/api/v1/blood-requests/{id}/detail` | JWT (eligible donor) | Full recipient detail incl. contact number, before deciding |
| POST | `/api/v1/blood-requests/{id}/volunteer` | JWT (donor) | Volunteer to donate for a request |
| POST | `/api/v1/blood-requests/{id}/reject` | JWT (donor) | Reject a request with a mandatory reason |
| GET | `/api/v1/blood-requests/{id}/willing-donors` | JWT (owner recipient) | List donors currently willing, for accept/deny review |
| POST | `/api/v1/blood-requests/{id}/accept-donor` | JWT (owner recipient) | Accept one donor; closes the request |
| POST | `/api/v1/blood-requests/{id}/deny-donor` | JWT (owner recipient) | Dismiss one donor; request stays open |
| GET | `/api/v1/blood-requests/{id}/document` | JWT (owner or eligible donor) | View/download the hospital approval document |
| GET | `/api/v1/dashboard/recipient` | JWT (recipient) | Dashboard stat counts |
| GET | `/api/v1/dashboard/donor` | JWT (donor) | Dashboard stat counts |
| GET | `/api/health` | — | Health check |

All error responses share one shape: `{"success": false, "message": str, "errors": [...]}`.

---

## 6. MongoDB schema

| Collection | Key fields | Indexes |
|---|---|---|
| `users` | `role` (donor\|recipient), name/age/blood_group/contact/email, `address`, `location` (GeoJSON Point), `hashed_password` | unique `email`; `role`; `blood_group`; `2dsphere` on `location` |
| `blood_requests` | `recipient_id`, `for_self`, `patient` (embedded patient details), `location`, `hospital_approval_document`, `status`, `willing_donor_count` | `recipient_id`; `status`; `patient.blood_group`; `2dsphere` on `location`; `created_at` |
| `donor_responses` | `request_id`, `donor_id`, `status` | unique compound `(request_id, donor_id)` |
| `otps` | `email`, `otp_hash`, `purpose`, `verified`, `expires_at` | TTL index on `expires_at` (auto-cleanup) |

**Why one `users` collection instead of separate `donors`/`recipients` collections:** donors and
recipients share nearly identical fields (name, age, blood group, contact, address, credentials).
A single collection discriminated by `role` avoids duplicating that schema, lets one login/auth flow
serve both roles, and still leaves room to add role-specific fields later without a migration —
Mongo documents don't require every document in a collection to share the same shape.

---

## 7. Security measures implemented

- JWT bearer authentication + role-based authorization on every protected route
- bcrypt password hashing (cost factor 12)
- Mandatory email verification (OTP, hashed at rest, TTL-expired, rate-limited, single-use)
- Pydantic validation on every input (strong password rule, phone format, name format, blood group enum)
- File upload validation: content-type allowlist, size cap, server-generated filenames (no path traversal), sensitive documents served only via an authenticated, ownership-checked endpoint — never a public static path
- Rate limiting on auth/OTP endpoints (slowapi)
- Security headers middleware (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, `Strict-Transport-Security`)
- CORS allowlist (not `*`)
- Centralized error handling that never leaks internals (stack traces, DB errors) to the client
- For "blood requirement for self", the server always sources patient identity from the authenticated user's own profile — it never trusts client-supplied identity fields for that case
- Soft delete (`is_deleted`) instead of hard delete throughout

---

## 7a. Donor-recipient matching, consent, and fraud detection

This is the core workflow added after the initial artefact, connecting a donor's willingness to a
recipient's decision rather than leaving "willing donor count" as a number with no next step:

1. A donor's `/blood-requests/matching` feed is filtered by **ABO/Rh compatibility** and bounded to
   a **5km radius** (`$geoNear` with `maxDistance`), not just sorted by distance.
2. Opening a specific request (`GET /{id}/detail`) reveals the recipient's name, age, blood group,
   email, address, and the hospital approval document — but only if the donor is actually eligible
   (compatible blood group, request still active, within radius). The same eligibility check gates
   `/document`, `/volunteer`, and `/reject`, so there's one source of truth for "can this donor see
   or act on this request," not three.
3. From there a donor either **volunteers** (`POST /volunteer`) or **rejects with a mandatory reason**
   (`POST /reject`). A donor can only respond once per request (DB-enforced via a unique index).
4. The recipient reviews everyone who volunteered (`GET /willing-donors`, including each donor's
   contact number) and either **accepts** one (`POST /accept-donor` — confirms that donor, closes
   the request, and it disappears from every other donor's feed automatically since the feed only
   ever queries `status: active`) or **denies** a specific donor (`POST /deny-donor` — removes just
   that donor from the review list; the request stays open to others).
5. **Fraud detection:** if a single request accumulates 5 donor rejections
   (`settings.DONOR_REJECTION_BAN_THRESHOLD`), the recipient's account is automatically banned
   (`is_banned=True`) and the request is cancelled. A banned account is blocked at the
   `get_current_user` dependency level, so it's locked out of every authenticated endpoint, not just
   login — attempting to log in shows `ACCOUNT IS BANNED DUE TO SUSPECTED ACTIVITY!`.

**Deliberate design call worth flagging:** the recipient's contact number is shown to a donor as
soon as they open a request's detail view (before deciding), not gated behind accepting. This was
genuinely ambiguous in how the feature was described — if you intended contact details to stay
hidden until *after* a donor commits, that's a one-line change (move `contact` out of
`BloodRequestDonorDetail` and only include it in the post-volunteer response).

---

## 8. Design decisions & notes on the original spec

A few places where the spec was ambiguous or where I made an explicit judgment call — flagging
these so they're easy to revisit:

- **Password/Confirm Password fields on the Blood Request form:** the original spec listed these
  as mandatory fields on the blood request page, mirroring the registration field list. Since the
  user is already authenticated (JWT) when raising a request, and no functional purpose for a new
  password was described, I did **not** implement these on the request form — they'd either be
  redundant or confusing. If the intent was instead "re-enter your current password to confirm this
  irreversible action" (a common pattern for high-stakes submissions), that's a small, well-scoped
  addition I can make — let me know.
- **Email verification for "for self" requests:** since the account's email was already verified at
  registration, self-requests skip a second OTP round. "For someone else" requests verify the
  third-party email via its own OTP (purpose=`blood_request`) before submission is allowed.
  Registration auto-verified accounts are still re-checked against the identity encoded in the
  requester's JWT, not the client-supplied form data.
  It's the only place `otps` are reused for a purpose other than registration.
- **Registration auto-login:** the spec says "after successful registration redirect user to
  respective dashboard," so `/auth/register` returns an access token immediately, matching `/auth/login`'s response shape.
- **Donor-recipient matching:** not explicitly specified beyond "Willing Donor Count" in the original
  spec; see Section 7a above for how this was built out into a full consent + accept/deny + fraud-
  detection workflow.
- **Request status lifecycle:** requests are immutable once submitted (per spec) — no endpoint edits
  request content — but the system-managed `status` field now transitions automatically
  (`active` → `fulfilled` when a recipient accepts a donor, or → `cancelled` when a request is
  auto-flagged for suspected fraud) rather than being a dead field with no way to change.

---

## 9. Known limitations / natural next steps

- **File storage** is local disk (`backend/uploads/`) for simplicity. For real deployment, swap
  `app/utils/file_utils.py` to write to S3/Azure Blob/GCS and serve via short-lived signed URLs.
- **Rate limiting** uses slowapi's in-memory store, which only tracks limits within a single
  process. Behind a load balancer with multiple instances, point it at Redis instead.
- **No refresh tokens** — access tokens are long-lived (24h default) rather than short-lived +
  refreshable. Fine for an MVP; worth adding for production.
- **No automated frontend tests** — the backend has a full integration test suite; the frontend
  would benefit from component tests (e.g. Vitest + React Testing Library) as a follow-up.
- **No moderation/admin role or appeal path.** The 5-rejection auto-ban (Section 7a) is a blunt,
  automatic heuristic with no human review step and no way for a wrongly-banned recipient to
  contest it — a real deployment would want an admin role that can review flagged requests and
  reinstate accounts, rather than banning being final and unappealable.
- **No notification when a donor is denied or not selected** — a donor who volunteers currently
  only finds out they weren't chosen by noticing the request disappeared from their feed (because
  it's no longer `active`), rather than getting an explicit "not this time" notice.
