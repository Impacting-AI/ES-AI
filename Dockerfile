FROM node:22-alpine AS frontend
WORKDIR /app
COPY package.json tsconfig.json index.html build.mjs ./
COPY web web
RUN npm install --no-audit --no-fund && npm run build
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home app
COPY server server
COPY tests tests
COPY --from=frontend /app/dist dist
USER app
CMD ["uvicorn","server.app:app","--host","0.0.0.0","--port","8080","--no-proxy-headers"]
