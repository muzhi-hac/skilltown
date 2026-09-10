# SkillTown learning API. The Godot Web build is deployed separately to
# Cloudflare Pages, which proxies /api/* back here (see docs/DEPLOY.md).
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_PATH=/data/skilltown.sqlite3

WORKDIR /app

COPY server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt

COPY server/ server/

# SQLite needs a persistent volume; without one every redeploy wipes learner
# evidence, which would make the demo lie about memory.
RUN mkdir -p /data && useradd --create-home --uid 10001 skilltown \
    && chown -R skilltown /data /app
USER skilltown
VOLUME ["/data"]

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

CMD ["python", "-m", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
