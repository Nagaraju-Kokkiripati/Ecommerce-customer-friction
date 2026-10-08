FROM python:3.14-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home appuser && mkdir -p /app/persist && chown -R appuser:appuser /app
USER appuser
ENV DATA_DIR=/app/persist
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "frictioniq.main:app", "--host", "0.0.0.0", "--port", "8000"]
