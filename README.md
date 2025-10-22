# Flussonic Auth Backend

A modern, standalone FastAPI-based authentication backend for Flussonic Media Server with SQLite database, built with Python 3.12, uv package manager, and following latest best practices.

## Features

- **Modern Python 3.12**: Uses latest type hints (`|` union types, `Mapped` types)
- **UV Package Manager**: Fast, modern dependency management
- **Token-based Authentication**: Validate client access using tokens
- **Session Management**: Track and limit concurrent streaming sessions per user
- **Status Control**: Active, suspended, and expired token states
- **Access Control**:
  - IP whitelist per token
  - Stream whitelist per token
  - Time-based validity periods
- **Concurrent Session Limiting**: Configure max simultaneous streams per token
- **Access Logging**: Comprehensive audit trail for all authorization requests
- **Management API**: RESTful API for token and session administration
- **Docker Support**: Ready-to-deploy Docker container with multi-stage builds
- **Background Cleanup**: Automatic cleanup of expired sessions
- **Code Quality**: Pre-commit hooks, ruff linting, mypy type checking

## Quick Start

### Using Docker (Recommended)

```bash
# Clone and start
git clone <repository-url>
cd auth-backend
docker-compose up -d

# View logs
docker-compose logs -f

# The service will be available on http://localhost:8080
```

### Using UV (Development)

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv pip install -e ".[dev]"

# Setup pre-commit hooks
pre-commit install

# Run the application
make run
# Or directly:
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

## Development Commands

```bash
# Install dependencies
make install      # Production dependencies
make dev          # Development dependencies + pre-commit

# Code quality
make lint         # Run ruff and mypy
make format       # Format code with ruff

# Testing
make test         # Run pytest with coverage

# Run locally
make run          # Start with auto-reload

# Docker
make docker-build
make docker-up
make docker-down
make docker-logs

# Clean
make clean        # Remove cache and artifacts
```

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc

For complete API documentation and usage examples, see the full documentation in the `/docs` endpoint.

## License

MIT License
