FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

# Runs as root on purpose: it needs the Docker socket and the shared work dir.
# The sandbox containers it creates run as uid 1000 with no network and no secrets.
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
