FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY pubmed_etl ./pubmed_etl
ENV PUBMED_DB=/app/data/pubmed.db
VOLUME /app/data
# Run the ETL:  docker run -v pubmed:/app/data IMAGE python -m pubmed_etl "query"
# Serve the API (default): docker run -p 8000:8000 -v pubmed:/app/data IMAGE
CMD ["uvicorn", "pubmed_etl.api:app", "--host", "0.0.0.0", "--port", "8000"]
