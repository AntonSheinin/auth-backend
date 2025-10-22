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
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

## Configuration

Create a `.env` file (see `.env.example`):

```bash
DATABASE_URL=sqlite:///./data/tokens.db
AUTH_DURATION=180
SESSION_CLEANUP_INTERVAL=60
LOG_LEVEL=INFO
ENABLE_ACCESS_LOGS=true
API_HOST=0.0.0.0
API_PORT=8080
API_KEY=your-secret-api-key  # Optional
```

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

- **Console Logging**: All application logs output to console (stdout)
- **Access Logs**: Authentication attempts saved to SQLite database (`access_logs` table)
- No log files are created - use Docker logs or redirect console output as needed

View logs:
```bash
# Docker
docker-compose logs -f

# Local
python -m uvicorn app.main:app --log-level info
```

## Usage Examples

### Create a Token

```bash
curl -X POST http://localhost:8080/api/tokens \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{
    "token": "secure-token-123",
    "user_id": "user-001",
    "status": "active",
    "max_sessions": 2
  }'
```

### Test Authorization

```bash
curl -v "http://localhost:8080/auth?name=stream1&ip=192.168.1.100&token=secure-token-123&proto=hls"
```

## Project Structure

```
auth-backend/
├── app/
│   ├── main.py           # FastAPI application
│   ├── config.py         # Configuration
│   ├── routes.py         # All API routes
│   ├── core/
│   │   └── logging.py    # Logging setup
│   ├── models/           # Database models
│   ├── services/         # Business logic
│   ├── schemas/          # Pydantic schemas
│   └── utils/            # Utilities
├── data/                 # SQLite database
├── .venv/                # Virtual environment
├── pyproject.toml        # Project configuration
├── Dockerfile
└── docker-compose.yml
```

## License

MIT License
