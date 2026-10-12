FROM mcr.microsoft.com/playwright:v1.58.0-noble
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv python3-pip git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python3 -m venv /opt/testagent-venv \
    && /opt/testagent-venv/bin/pip install --no-cache-dir -r requirements.txt

ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
COPY browser_runner/package.json browser_runner/package-lock.json ./browser_runner/
RUN cd browser_runner && npm ci --ignore-scripts
COPY browser_runner/tsconfig.json ./browser_runner/
COPY browser_runner/src ./browser_runner/src
RUN cd browser_runner && npm run build

COPY testagent ./testagent
ENV PATH="/opt/testagent-venv/bin:$PATH" DATA_DIR=/data IMPORT_ROOT=/workspace PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "testagent.api:app", "--host", "0.0.0.0", "--port", "8000"]

