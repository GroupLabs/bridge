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

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

EXPOSE 8000

CMD ["python", "api.py"]