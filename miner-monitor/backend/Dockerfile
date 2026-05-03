FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONPATH=/app/..
ENV DB_PATH=/app/data/miner_monitor.db
EXPOSE 5002
CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "5002"]
