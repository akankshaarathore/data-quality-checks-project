FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
  postgresql-client \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY split_csv.py .
COPY data_ingestion_2.py .

COPY data/ ./data/

CMD ["python", "--version"]