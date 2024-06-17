FROM python:3.11.7-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    unixodbc \
    unixodbc-dev \
    gcc \
    python3-dev \
    git \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    libgl1-mesa-glx \
    libreoffice \
    && rm -rf /var/lib/apt/lists/*

# Install NLTK and download the 'punkt' tokenizer
RUN pip install nltk && python -m nltk.downloader punkt

# Install additional packages
RUN pip install --no-cache-dir \
    magika \
    FastAPI \
    python-dotenv \
    "unstructured[pdf]" \
    uvicorn \
    requests \
    celery \
    httpx \
    psycopg2-binary \
    openai \
    "tritonclient[http]" \
    elasticsearch \
    azure-storage-blob \
    scikit-learn \
    PyPDF2 \
    torch \
    mlflow \
    transformers \
    python-docx \
    openpyxl \
    xlrd \
    pillow \
    python-pptx \
    google-auth \
    google-auth-oauthlib \
    google-auth-httplib2 \
    google-api-python-client \
    azure-storage-blob==12.20.0 \
    scikit-learn==1.5.0 \
    mlflow==2.13.1 \
    python-docx==1.1.2 \
    openpyxl==3.1.2 \
    xlrd==2.0.1 \
    python-pptx==0.6.23 \
    mysql-connector==2.2.9 \
    mysql-connector-python-rf==2.2.2 \
    pyodbc==5.1.0 \
    requests-oauthlib==1.3.1 \
    psutil==5.9.8 \
    pyarrow==15.0.2 \
    pymongo \
    msal \
    simple_salesforce

COPY . ./

EXPOSE 8000

CMD ["python", "api.py"]
