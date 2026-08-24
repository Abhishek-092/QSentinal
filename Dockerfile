# QSENTINEL — Single-machine demo deployment
# Blueprint §22: FastAPI + static React frontend, SQLite volume-mounted
FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock

# Copy application code
COPY qds/ qds/
COPY qsentinel_monitor/ qsentinel_monitor/
COPY attacks/ attacks/
COPY experiments/ experiments/
COPY api/ api/
COPY db/ db/
COPY forensic_store/ forensic_store/
COPY tests/ tests/
COPY pyproject.toml importlinter.ini ./

# Install package in editable mode
RUN pip install -e .

# Initialize database on first run
RUN python -c "from db.models import init_db; init_db()"

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
