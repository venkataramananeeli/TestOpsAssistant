# TestOps Application

A Streamlit-based test operations dashboard.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure `.streamlit/secrets.toml` with your database credentials

3. Run the app:
   ```bash
   streamlit run app.py
   ```

## Docker Deployment

1. Create env file:
   ```bash
   cp .env.example .env
   ```

2. Update `.env` with database credentials.

3. Start with Docker:
   ```bash
   docker compose up -d --build
   ```

4. Verify:
   ```bash
   curl http://localhost:8080/_stcore/health
   ```

Detailed steps: see `DEPLOY_DOCKER.md`.

## Structure

- `app.py` - Main entry point
- `modules/` - Reusable Python modules
- `pages/` - Multi-page app files
- `.streamlit/` - Streamlit configuration
