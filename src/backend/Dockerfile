FROM python:3.11.7-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    libgl1-mesa-glx \
    libreoffice \
    && rm -rf /var/lib/apt/lists/*

# Install NLTK and download the 'punkt' tokenizer
RUN pip install nltk && python -m nltk.downloader punkt

#COPY requirements.txt ./

RUN pip install --no-cache-dir magika FastAPI python-dotenv "unstructured[pdf]" uvicorn requests celery httpx psycopg2-binary openai "tritonclient[http]" elasticsearch azure-storage-blob scikit-learn PyPDF2 torch mlflow transformers python-docx openpyxl xlrd pillow python-pptx


COPY . ./

EXPOSE 8000

CMD ["python", "api.py"]