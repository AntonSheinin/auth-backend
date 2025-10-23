# Flussonic Auth Backend

A standalone FastAPI authentication backend for Flussonic Media Server with SQLite database, built with Python 3.12 and uv package manager.

## Features

- Token-based authentication for Flussonic Media Server
- Session management with concurrent stream limiting
- Status control (active, suspended, expired)
- IP and stream whitelisting per token
- Time-based token validity
- Access logging to database
- RESTful management API
- Docker support
- Automatic session cleanup

## Quick Start

### Using Docker (Recommended)

```bash
docker-compose up -d
```

The service will be available on http://localhost:8080

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

3. **Run the application:**
```bash
python -m app.main
```

Or with uvicorn directly:
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

## Configuration

Copy `.env.example` to `.env` and customize as needed:

```bash
cp .env.example .env
```

### Environment Variables

All variables have sensible defaults (see `.env.example` for detailed documentation):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./data/tokens.db` | Database connection string (SQLite, PostgreSQL, MySQL) |
| `AUTH_DURATION` | `180` | Session duration in seconds (30-3600) |
| `SESSION_CLEANUP_INTERVAL` | `60` | Expired session cleanup interval (10-600 seconds) |
| `MAX_RESPONSE_TIME` | `2.5` | Max response time to stay under Flussonic's 3s timeout |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `ENABLE_ACCESS_LOGS` | `true` | Log authentication attempts to database |
| `API_HOST` | `0.0.0.0` | IP address to bind the API server |
| `API_PORT` | `8080` | Port for the API server |
| `API_KEY` | `` (empty) | Optional API key for management endpoints |

## Flussonic Configuration

Add to `/etc/flussonic/flussonic.conf`:

```
auth_backend myauth {
  backend http://your-server:8080/auth;
}

stream mystream {
  url http://source-stream;
  auth myauth;
}
```

## API Documentation

Visit http://localhost:8080/docs for interactive API documentation.

### Main Endpoints

- **GET/POST** `/auth` - Authorization endpoint (called by Flussonic)
- **POST** `/api/tokens` - Create token
- **GET** `/api/tokens` - List tokens
- **PATCH** `/api/tokens/{id}` - Update token
- **DELETE** `/api/tokens/{id}` - Delete token
- **GET** `/api/sessions` - List active sessions
- **DELETE** `/api/sessions/{id}` - Terminate session

## Logging

The application uses Python's default logging system with comprehensive access tracking:

- **Console Logging**: Application logs output to stdout (configured via `LOG_LEVEL` env var)
- **Access Logs**: All authentication attempts saved to SQLite database (`access_logs` table)
  - Includes: token, user_id, stream_name, client_ip, protocol, result (allowed/denied), reason
  - Controlled by `ENABLE_ACCESS_LOGS` environment variable
- **No File Logging**: Logs are only output to console, use Docker logs or standard output redirection as needed

View logs:
```bash
# Docker
docker-compose logs -f app

# Local development
python -m app.main
```

Query access logs from database:
```bash
sqlite3 data/tokens.db "SELECT * FROM access_logs ORDER BY timestamp DESC LIMIT 10;"
```

## Usage Examples

### Create a Token

```bash
curl -X POST http://localhost:8080/api/tokens \
  -H "Content-Type: application/json" \
  -d '{
    "token": "secure-token-123",
    "user_id": "user-001",
    "status": "active",
    "max_sessions": 2,
    "allowed_ips": ["192.168.1.100", "192.168.1.101"],
    "allowed_streams": ["stream1", "stream2"],
    "meta": {"region": "us-east"}
  }'
```

### Test Authorization (Called by Flussonic)

```bash
curl -v "http://localhost:8080/auth?name=stream1&ip=192.168.1.100&token=secure-token-123&proto=hls"
```

Success response (HTTP 200):
```
X-UserId: user-001
X-Max-Sessions: 2
X-AuthDuration: 180
```

Failure response (HTTP 403):
```json
{
  "error": "access_denied",
  "reason": "ip_not_allowed",
  "message": "IP address 192.168.1.50 is not authorized for this token",
  "user_id": "user-001"
}
```

### List Tokens

```bash
curl http://localhost:8080/api/tokens?status=active
```

### Update Token

```bash
curl -X PATCH http://localhost:8080/api/tokens/1 \
  -H "Content-Type: application/json" \
  -d '{
    "status": "suspended",
    "max_sessions": 1
  }'
```

### Query Access Logs

```bash
# View recent authentication attempts
sqlite3 data/tokens.db \
  "SELECT timestamp, user_id, stream_name, client_ip, result, reason \
   FROM access_logs \
   ORDER BY timestamp DESC \
   LIMIT 20;"
```

## Project Structure

```
auth-backend/
├── app/
│   ├── main.py               # FastAPI application with lifespan context
│   ├── config.py             # Pydantic settings (environment variables)
│   ├── routes.py             # All API routes (auth, tokens, sessions)
│   ├── logging.py            # Logging configuration
│   ├── models/               # SQLAlchemy ORM models
│   │   ├── token.py          # Token model with allowed_ips, allowed_streams, meta
│   │   ├── session.py        # ActiveSession model for concurrent stream tracking
│   │   └── log.py            # AccessLog model for audit trail
│   ├── services/             # Business logic layer
│   │   ├── database.py       # Database engine, SessionLocal, get_db dependency
│   │   ├── token_service.py  # Token CRUD operations
│   │   ├── session_service.py # Session management and cleanup
│   │   └── validation.py     # Core authorization logic
│   ├── schemas/              # Pydantic v2 request/response schemas
│   │   ├── auth.py           # Auth endpoint schemas
│   │   └── management.py     # Token and session management schemas
│   └── utils/                # Utility functions
│       └── session_id.py     # Session ID generation
├── data/                     # SQLite database (gitignored)
├── .venv/                    # Virtual environment (gitignored)
├── .env                      # Environment variables (gitignored)
├── .env.example              # Environment template with documentation
├── pyproject.toml            # Project configuration (uv, build, dependencies)
├── Dockerfile                # Docker image definition
├── docker-compose.yml        # Docker Compose configuration
└── README.md                 # This file
```

## Architecture

The application follows a clean, layered architecture:

- **Models** (`app/models/`): SQLAlchemy ORM models representing database tables
  - `Token`: Authentication tokens with configuration (IP/stream whitelist, metadata)
  - `ActiveSession`: Tracks concurrent sessions per user
  - `AccessLog`: Audit trail of all authorization attempts

- **Services** (`app/services/`): Business logic layer
  - `DatabaseService`: Database engine, connection pooling, initialization
  - `TokenService`: CRUD operations for tokens
  - `SessionService`: Session lifecycle management and cleanup
  - `ValidationService`: Core authorization logic with comprehensive checks

- **Schemas** (`app/schemas/`): Pydantic v2 models for request/response validation
  - Input validation for API endpoints
  - Automatic OpenAPI documentation generation

- **Routes** (`app/routes.py`): FastAPI route handlers
  - Auth endpoint (called by Flussonic)
  - Token management endpoints
  - Session management endpoints

- **Utils** (`app/utils/`): Helper functions
  - Session ID generation for tracking concurrent streams

## Development

The project uses modern Python 3.12+ features and best practices:

- **Type Hints**: Full Python 3.12 union syntax (`T | None` instead of `Optional[T]`)
- **Package Management**: `uv` for fast dependency resolution and management
- **ORM**: SQLAlchemy 2.0 with `Mapped` type hints
- **Validation**: Pydantic v2 with modern configuration
- **Async**: FastAPI async/await for high concurrency
- **Testing**: Ready for pytest integration
- **Logging**: Python's default logging with database persistence for access logs

### Python 3.12+ Features Used

- Union type syntax: `str | None`, `list[str]`, `dict[str, Any]`
- Built-in generic types (no `List[]`, `Dict[]` from typing)
- Modern imports from `collections.abc` for generator types
- f-strings for string interpolation

## API Security

The management endpoints (`/api/tokens`, `/api/sessions`) can be protected with an optional API key:

1. Generate a secure API key:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. Set it in your `.env`:
   ```bash
   API_KEY=your-generated-key
   ```

3. Include it in management API requests:
   ```bash
   curl -H "X-API-Key: your-generated-key" http://localhost:8080/api/tokens
   ```

The authorization endpoint (`/auth`) is always publicly accessible (required by Flussonic).

## Troubleshooting

### Database Issues

If you get database errors, ensure the `data/` directory exists:
```bash
mkdir -p data
```

### Port Already in Use

If port 8080 is already in use, change it in `.env`:
```bash
API_PORT=8081
```

Then run the application with the new port:
```bash
docker-compose up  # Uses .env automatically
```

### Connection to Flussonic

Ensure Flussonic can reach the auth backend:
- Check firewall rules
- Verify the URL in Flussonic config matches your deployment
- Use the health check endpoint: `curl http://localhost:8080/health`

## License

MIT License
