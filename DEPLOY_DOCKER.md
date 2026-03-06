# Docker Deployment Guide

## 1. Prepare Environment Variables

Copy the template and fill real values:

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
MYSQL_HOST=...
MYSQL_PORT=3306
MYSQL_USER=...
MYSQL_PASS=...
MYSQL_DB=...
MYSQL_POOL_SIZE=10
OPENAI_API_KEY=...  # optional
```

## 2. Build and Run

```bash
docker compose up -d --build
```

## 3. Verify

```bash
docker compose ps
docker compose logs -f testops-app
curl http://localhost:8080/_stcore/health
```

Expected health response:

```text
ok
```

## 4. Upgrade Deployment

```bash
git pull
docker compose up -d --build
```

## 5. Stop / Remove

```bash
docker compose down
```

## Notes

- App is exposed on port `8080`.
- Ensure MySQL is reachable from the server running Docker.
- If firewall is enabled, allow inbound traffic to `8080` (or put Nginx in front and expose only `80/443`).
