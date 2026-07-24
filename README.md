# Simple FastAPI

A simple yet complete FastAPI application with User and Product Management, featuring JWT authentication, database support (SQLite, PostgreSQL, MySQL), and Docker deployment.

## Features

- **User Management**: Register, update, delete, and retrieve users
- **Product Management**: CRUD operations for products
- **Authentication**: JWT-based authentication with token management
- **Database Support**: Multiple database backends (SQLite, PostgreSQL, MySQL)
- **Docker Ready**: Containerized deployment with docker-compose
- **Testing**: Pytest-based test suite
- **Security**: Password hashing with bcrypt, CORS middleware

## Tech Stack

- **Framework**: FastAPI 0.115.6
- **Database ORM**: SQLAlchemy 2.9.2
- **Database Migrations**: Alembic 1.15.2
- **Validation**: Pydantic 2.10.3
- **Authentication**: python-jose (JWT), passlib (password hashing)
- **Testing**: pytest, httpx
- **Server**: Uvicorn

## Project Structure

```
.
├── app/
│   ├── __init__.py
│   ├── main.py              # Application entry point
│   ├── core/                # Core configurations and utilities
│   │   ├── config.py        # Application settings
│   │   ├── database.py      # Database configuration
│   │   ├── dependencies.py  # Request dependencies
│   │   ├── responses.py     # Standard response formats
│   │   └── security.py      # Security utilities
│   └── modules/             # Feature modules
│       ├── auth/            # Authentication module
│       ├── user/            # User management module
│       └── product/         # Product management module
├── tests/                   # Test suite
├── alembic/                 # Database migrations
├── docker-compose.yml       # Docker Compose configuration
├── dockerfile               # Docker image configuration
├── requirements.txt         # Python dependencies
└── .env.example             # Environment variables template
```

## Getting Started

### Prerequisites

- Python 3.11+
- pip or poetry
- Docker and Docker Compose (optional)

### Local Development

1. **Clone the repository**

```bash
git clone <repository-url>
cd <project-directory>
```

2. **Create a virtual environment**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Configure environment variables**

```bash
cp .env.example .env
```

Edit `.env` and configure your settings:

```env
APP_NAME="FastAPI App"
APP_VERSION="1.0.0"
DEBUG=False
DATABASE_URL="sqlite:///./app.db"
SECRET_KEY="your-super-secret-key-change-this-in-production"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

5. **Run the application**

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`.

### Interactive API Documentation

Once running, access the interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Docker Deployment

### Using SQLite (default)

```bash
docker-compose --profile sqlite up -d
```

### Using PostgreSQL

```bash
docker-compose --profile postgres up -d
```

Update `DATABASE_URL` in your environment:

```env
DATABASE_URL="postgresql://user:password@postgres:5432/fastapi_db"
```

### Using MySQL

```bash
docker-compose --profile mysql up -d
```

Update `DATABASE_URL` in your environment:

```env
DATABASE_URL="mysql+pymysql://user:password@mysql:3306/fastapi_db"
```

### View logs

```bash
docker-compose logs -f app
```

### Stop containers

```bash
docker-compose down
```

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register a new user |
| POST | `/auth/login` | Login and get access token |
| GET | `/auth/me` | Get current user info |

### User Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/users/register` | Create a new user |
| GET | `/users/` | List all users |
| GET | `/users/{user_id}` | Get user by ID |
| PUT | `/users/{user_id}` | Update user |
| DELETE | `/users/{user_id}` | Delete user (soft delete) |

### Product Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/products/` | Create a new product |
| GET | `/products/` | List all products |
| GET | `/products/{product_id}` | Get product by ID |
| PUT | `/products/{product_id}` | Update product |
| DELETE | `/products/{product_id}` | Delete product (soft delete) |

### Health Check

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check endpoint |
| GET | `/` | Welcome message |

## Running Tests

```bash
pytest
```

Or with verbose output:

```bash
pytest -v
```

## Database Migrations

This project uses Alembic for database migrations.

### Initialize migrations (if needed)

```bash
alembic init alembic
```

### Create a new migration

```bash
alembic revision --autogenerate -m "Description of changes"
```

### Apply migrations

```bash
alembic upgrade head
```

### Rollback migrations

```bash
alembic downgrade -1
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_NAME` | Application name | "FastAPI App" |
| `APP_VERSION` | Application version | "1.0.0" |
| `DEBUG` | Debug mode | False |
| `DATABASE_URL` | Database connection URL | sqlite:///./app.db |
| `SECRET_KEY` | Secret key for JWT | (required) |
| `ALGORITHM` | JWT algorithm | HS256 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiration time | 30 |

## Security Notes

- **Change the SECRET_KEY** in production! Generate a secure key with:
  ```bash
  openssl rand -hex 32
  ```
- **Use HTTPS** in production environments
- **Restrict CORS origins** instead of allowing all origins
- **Change default API keys** and credentials

## License

See [LICENSE](LICENSE) for details.