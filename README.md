# Flussonic Auth Backend

A production-ready FastAPI authentication backend for Flussonic Media Server with token-based authorization, concurrent session management, and comprehensive access control.

## Features

- **Token-Based Authentication** - Secure token validation for Flussonic Media Server streams
- **Concurrent Session Limiting** - Control maximum simultaneous streams per user with race condition prevention
- **Access Control Lists** - IP whitelist and stream whitelist per token
- **Time-Based Validity** - Token validity periods with automatic expiration handling
- **Access Logging** - Comprehensive audit trail of all authorization attempts
- **Multi-Database Support** - SQLite (default), PostgreSQL, and MySQL with async drivers
- **Background Tasks** - Automatic cleanup of expired sessions and old logs
- **RESTful Management API** - Full CRUD operations for tokens and sessions
- **Docker Ready** - Production-ready containerization with health checks

## Technology Stack

| Component | Technology |
|-----------|------------|
| Framework | FastAPI 0.115.5+ |
| Runtime | Python 3.12+ |
| ORM | SQLAlchemy 2.0+ (async) |
| Validation | Pydantic v2 |
| Server | Uvicorn (ASGI) |
| Package Manager | uv |
| Database | SQLite / PostgreSQL / MySQL |

## Quick Start

### Using Docker (Recommended)

```bash
# Copy environment template
cp .env.example .env

# Start the service
docker-compose up -d

# View logs
docker-compose logs -f app
```

The service will be available at http://localhost:8090

### Local Development

1. **Create virtual environment and install dependencies:**
```bash
uv venv
uv pip install -e .
```

2. **Activate virtual environment:**
```bash
# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

3. **Setup environment:**
```bash
cp .env.example .env
mkdir -p data
```

4. **Run the application:**
```bash
python -m app.main
```

Or with hot reload:
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8090 --reload
```

## Configuration

All configuration is done via environment variables. Copy `.env.example` to `.env` and customize:

### Database Settings

| Variable | Default | Range | Description |
|----------|---------|-------|-------------|
| `DATABASE_URL` | `sqlite:///./data/tokens.db` | - | Connection string (auto-converts to async driver) |
| `DB_POOL_SIZE` | `5` | 1-50 | Connection pool size (PostgreSQL/MySQL only) |
| `DB_MAX_OVERFLOW` | `10` | 0-100 | Max overflow connections |
| `DB_POOL_TIMEOUT` | `30` | 5-300 | Pool connection timeout (seconds) |

**Supported Database URLs:**
- SQLite: `sqlite:///./data/tokens.db`
- PostgreSQL: `postgresql://user:password@localhost/dbname`
- MySQL: `mysql://user:password@localhost/dbname`

### Auth & Session Settings

| Variable | Default | Range | Description |
|----------|---------|-------|-------------|
| `AUTH_DURATION` | `180` | 30-3600 | Session duration in seconds |
| `SESSION_CLEANUP_INTERVAL` | `60` | 10-600 | Expired session cleanup interval (seconds) |

### Logging Settings

| Variable | Default | Options | Description |
|----------|---------|---------|-------------|
| `LOG_LEVEL` | `INFO` | DEBUG, INFO, WARNING, ERROR, CRITICAL | Console log level |
| `ENABLE_ACCESS_LOGS` | `true` | true/false | Log auth attempts to database |
| `LOG_RETENTION_DAYS` | `3` | 1-365 | Days to retain access logs |
| `LOG_CLEANUP_INTERVAL` | `3600` | 60-86400 | Log cleanup interval (seconds) |

### API Settings

| Variable | Default | Range | Description |
|----------|---------|-------|-------------|
| `API_HOST` | `0.0.0.0` | - | Server bind address |
| `API_PORT` | `8090` | 1024-65535 | Server port |
| `API_KEY` | (empty) | - | Optional API key for management endpoints |

## API Endpoints

### Authorization Endpoint (Public)

**`GET/POST /auth`** - Main authorization endpoint called by Flussonic

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | Stream name (1-255 chars) |
| `ip` | string | Yes | Client IP address |
| `token` | string | Yes | Authorization token |
| `proto` | string | No | Protocol (hls, rtmp, rtsp, etc.) |

**Success Response (HTTP 200):**
```
Headers:
  X-UserId: user-001
  X-Max-Sessions: 2
  X-AuthDuration: 180
```

**Failure Response (HTTP 403):**
```json
{
  "error": "access_denied",
  "reason": "token_not_found|token_suspended|token_expired|token_not_yet_valid|max_sessions_reached|ip_not_allowed|stream_not_allowed",
  "message": "Human-readable error message",
  "user_id": "user_id_if_found"
}
```

### Health & Info Endpoints (Public)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service info and endpoint list |
| `/health` | GET | Health check (returns `{"status": "healthy"}`) |

### Token Management API (Protected*)

*Requires `X-API-Key` header if `API_KEY` is configured.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/tokens` | POST | Create new token |
| `/api/tokens` | GET | List tokens (supports `status`, `skip`, `limit` params) |
| `/api/tokens/{id}` | GET | Get token by ID |
| `/api/tokens/{id}` | PATCH | Update token |
| `/api/tokens/{id}` | DELETE | Delete token (cascades to sessions) |

### Session Management API (Protected*)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/sessions` | GET | List active sessions (supports `user_id`, `skip`, `limit`) |
| `/api/sessions/user/{user_id}` | GET | Get sessions for specific user |
| `/api/sessions/{id}` | DELETE | Terminate specific session |
| `/api/sessions/cleanup` | POST | Manually trigger expired session cleanup |

### Access Logs API (Protected*)

*Requires `X-API-Key` header if `API_KEY` is configured.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/access-logs` | GET | Query access logs (supports `user_id`, `token`, `stream_name`, `client_ip`, `protocol`, `result`, `reason`, `start_time`, `end_time`, `skip`, `limit`) |

## Flussonic Configuration

Add to `/etc/flussonic/flussonic.conf`:

```
auth_backend myauth {
  backend http://your-server:8090/auth;
}

stream mystream {
  url http://source-stream;
  auth myauth;
}
```

## Usage Examples

### Create a Token

```bash
curl -X POST http://localhost:8090/api/tokens \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "token": "secure-token-123",
    "user_id": "user-001",
    "status": "active",
    "max_sessions": 2,
    "valid_from": "2024-01-01T00:00:00",
    "valid_until": "2024-12-31T23:59:59",
    "allowed_ips": ["192.168.1.100", "192.168.1.101"],
    "allowed_streams": ["stream1", "stream2"],
    "meta": {"region": "us-east", "plan": "premium"}
  }'
```

### Test Authorization

```bash
curl -v "http://localhost:8090/auth?name=stream1&ip=192.168.1.100&token=secure-token-123&proto=hls"
```

### List Active Tokens

```bash
curl -H "X-API-Key: your-api-key" \
  "http://localhost:8090/api/tokens?status=active&limit=50"
```

### Update Token

```bash
curl -X PATCH http://localhost:8090/api/tokens/1 \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "status": "suspended",
    "max_sessions": 1
  }'
```

### View Active Sessions

```bash
curl -H "X-API-Key: your-api-key" \
  "http://localhost:8090/api/sessions?user_id=user-001"
```

### Terminate Session

```bash
curl -X DELETE -H "X-API-Key: your-api-key" \
  http://localhost:8090/api/sessions/123
```

### Query Access Logs (API)

```bash
curl -H "X-API-Key: your-api-key" \
  "http://localhost:8090/api/access-logs?user_id=user-001&start_time=2024-01-01T00:00:00&end_time=2024-01-31T23:59:59"
```

### Query Access Logs (DB)

```bash
sqlite3 data/tokens.db \
  "SELECT timestamp, user_id, stream_name, client_ip, result, reason \
   FROM access_logs ORDER BY timestamp DESC LIMIT 20;"
```

## Project Structure

```
auth-backend/
├── app/
│   ├── __init__.py
│   ├── main.py               # FastAPI application with lifespan context
│   ├── config.py             # Pydantic settings (environment variables)
│   ├── routes.py             # All API routes (auth, tokens, sessions)
│   ├── enums.py              # TokenStatus, AccessResult enums
│   ├── exceptions.py         # Custom exception classes
│   ├── logging.py            # Logging configuration
│   ├── mappers.py            # ORM to schema conversion
│   │
│   ├── models/               # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── token.py          # Token model with JSON fields
│   │   ├── session.py        # ActiveSession model
│   │   └── log.py            # AccessLog model
│   │
│   ├── services/             # Business logic layer
│   │   ├── __init__.py
│   │   ├── database.py       # Database engine, sessions, initialization
│   │   ├── token_service.py  # Token CRUD operations
│   │   ├── session_service.py # Session management and cleanup
│   │   ├── validation.py     # Core authorization logic
│   │   └── access_log_service.py # Access logging service
│   │
│   ├── schemas/              # Pydantic v2 request/response schemas
│   │   ├── __init__.py
│   │   ├── auth.py           # Auth endpoint schemas
│   │   └── management.py     # Token and session management schemas
│   │
│   └── utils/                # Utility functions
│       ├── __init__.py
│       └── session_id.py     # Session ID generation (SHA256)
│
├── data/                     # SQLite database directory (gitignored)
├── .env                      # Environment variables (gitignored)
├── .env.example              # Environment template with documentation
├── .gitignore                # Git ignore patterns
├── .dockerignore             # Docker build ignore patterns
├── pyproject.toml            # Project configuration (dependencies, build)
├── uv.lock                   # Dependency lock file
├── Dockerfile                # Docker image definition
├── docker-compose.yml        # Docker Compose configuration
└── README.md                 # This file
```

## Architecture

### Layered Design

```
┌─────────────────────────────────────────────┐
│                 Routes Layer                 │
│     (FastAPI endpoints, request handling)    │
├─────────────────────────────────────────────┤
│                Services Layer                │
│  (Business logic, validation, operations)    │
├─────────────────────────────────────────────┤
│                 Models Layer                 │
│      (SQLAlchemy ORM, database schema)       │
├─────────────────────────────────────────────┤
│              Database (Async)                │
│        (SQLite / PostgreSQL / MySQL)         │
└─────────────────────────────────────────────┘
```

### Database Models

**Token** - Authentication tokens with configuration
- Unique token string with user association
- Status management (active, suspended, expired)
- Concurrent session limits (1-100)
- Time-based validity (valid_from, valid_until)
- IP whitelist (JSON array)
- Stream whitelist (JSON array)
- Custom metadata (JSON object)

**ActiveSession** - Tracks concurrent streams
- Session ID (SHA256 hash of stream+ip+token)
- Token association with cascade delete
- Stream and client information
- Timestamps (started, last_checked, expires)

**AccessLog** - Audit trail
- All authorization attempts (allowed/denied)
- User, stream, IP, protocol tracking
- Denial reasons for debugging
- Automatic cleanup based on retention policy

### Authorization Flow

1. Flussonic calls `/auth` with stream name, client IP, and token
2. Backend validates token (existence, status, validity period)
3. Checks access control (IP whitelist, stream whitelist)
4. Enforces session limits with race condition prevention (SELECT FOR UPDATE)
5. Returns HTTP 200 with headers (success) or HTTP 403 with JSON (denied)

### Session ID Algorithm

Sessions are identified using SHA256 hash:
```
session_id = SHA256(stream_name + client_ip + token)
```

This enables:
- Detection of re-checks vs. new sessions
- Consistent session tracking across Flussonic's periodic auth checks
- No need for additional database lookups

## API Security

### Enabling API Key Protection

1. Generate a secure key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

2. Add to `.env`:
```bash
API_KEY=your-generated-key
```

3. Include in requests:
```bash
curl -H "X-API-Key: your-generated-key" http://localhost:8090/api/tokens
```

**Note:** The `/auth` endpoint is always public (required by Flussonic).

## Docker

### Building

```bash
docker build -t flussonic-auth-backend:latest .
```

### Running

```bash
docker run -p 8090:8090 \
  -v "$(pwd)/data:/app/data" \
  -e DATABASE_URL=sqlite:///./data/tokens.db \
  -e AUTH_DURATION=180 \
  -e API_KEY=your-secret-key \
  flussonic-auth-backend:latest
```

### Docker Compose Features

- Automatic restart (unless-stopped)
- Volume persistence for database
- Health check with 30s interval
- Environment variable configuration
- Development hot-reload support (volume mount)

## Troubleshooting

### Database Issues

Ensure the data directory exists:
```bash
mkdir -p data
```

### Port Already in Use

Change the port in `.env`:
```bash
API_PORT=8091
```

### Connection to Flussonic

1. Check firewall rules
2. Verify URL in Flussonic config matches deployment
3. Test health endpoint: `curl http://localhost:8090/health`
4. Check logs: `docker-compose logs -f app`

### Session Limit Issues

If users report "max sessions reached" unexpectedly:
1. Check current sessions: `GET /api/sessions?user_id=USER_ID`
2. Sessions auto-expire after `AUTH_DURATION` seconds
3. Manually cleanup: `POST /api/sessions/cleanup`

## API Documentation

Interactive documentation is available at:
- **Swagger UI:** http://localhost:8090/docs
- **ReDoc:** http://localhost:8090/redoc

## Development

### Code Style

- Full type hints using Python 3.12+ syntax (`T | None`, `list[str]`)
- Async/await throughout for high concurrency
- Pydantic v2 for validation
- SQLAlchemy 2.0 with `Mapped` type hints

### Testing

The codebase is structured for pytest integration:
- Service layer with clear dependency injection
- Database operations isolated in services
- Validation logic is pure and deterministic

## License

MIT License
