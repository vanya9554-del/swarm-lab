# syntax=docker/dockerfile:1
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY swarmlab ./swarmlab
COPY README.md SPEC.md ./
RUN addgroup --system app && adduser --system --ingroup app app && mkdir -p /data && chown -R app:app /app /data
USER app
EXPOSE 8788
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8788/health',timeout=2)"
CMD ["python","-m","swarmlab","serve","--db","/data/swarm.db","--host","0.0.0.0","--port","8788"]
