FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

EXPOSE 8000 8080

CMD ["bash", "-lc", "uvicorn src.main:app --host 0.0.0.0 --port 8000 & streamlit run ui/app.py --server.address 0.0.0.0 --server.port 8080"]
