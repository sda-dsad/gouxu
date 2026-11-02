FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 GOUXU_PROJECT_ROOT=/app GOUXU_STATE_ROOT=/state GOUXU_DATA_ROOT=/datasets
WORKDIR /app
COPY services/api/requirements.lock.txt /app/requirements.lock.txt
RUN pip install --no-cache-dir -r requirements.lock.txt && useradd --uid 1000 --create-home app
COPY contracts/ /app/contracts/
COPY fixtures/layout.synthetic.json /app/fixtures/layout.synthetic.json
COPY services/api/app/ /app/services/api/app/
RUN mkdir -p /state /datasets && chown 1000:1000 /state /datasets
USER 1000:1000
HEALTHCHECK --interval=15s --timeout=5s --start-period=120s --retries=4 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4)"
EXPOSE 8000
CMD ["python","-m","uvicorn","app.main:app","--app-dir","services/api","--host","0.0.0.0","--port","8000","--no-access-log"]
