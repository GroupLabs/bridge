FROM python:3.11.7-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    libgl1-mesa-glx \
    jq \
    curl \
    unixodbc-dev \
    apt-transport-https \
    gnupg \
    && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/10/prod.list | tee /etc/apt/sources.list.d/msprod.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql17 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

RUN pip install --no-cache-dir magika FastAPI python-dotenv "unstructured[pdf]" uvicorn requests celery httpx psycopg2-binary openai "tritonclient[http]" elasticsearch azure-storage-blob scikit-learn PyPDF2 torch mlflow transformers msal pymongo pyodbc

COPY . ./

EXPOSE 8000

CMD ["python", "api.py"]
