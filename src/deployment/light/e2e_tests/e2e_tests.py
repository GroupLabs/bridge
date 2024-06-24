import os
import requests
import time

# Constants
PDF_URL = 'https://uwaterloo.ca/onbase/sites/ca.onbase/files/uploads/files/sampleunsecuredpdf.pdf'
API_URL = "http://0.0.0.0:8000/load"
MAX_RETRIES = 5
RETRY_DELAY = 10  # in seconds

# Function to download the PDF file
def download_pdf(url):
    response = requests.get(url)
    if response.status_code == 200:
        with open('sampleunsecuredpdf.pdf', 'wb') as f:
            f.write(response.content)
        print("PDF downloaded successfully")
    else:
        print("Failed to download PDF")
        exit(1)

# Function to upload the PDF file
def upload_pdf():
    with open('sampleunsecuredpdf.pdf', 'rb') as f:
        files = {"file": ('sampleunsecuredpdf.pdf', f, "application/pdf")}
        
        for attempt in range(MAX_RETRIES):
            try:
                r = requests.post(API_URL, files=files)
                if r.status_code == 202:
                    print("Successfully acquired the task id")
                    task_id = r.json()["task_id"]
                    print(task_id)
                    return task_id
                else:
                    print(f"Failed to upload PDF, status code: {r.status_code}")
                    exit(1)
            except requests.exceptions.ConnectionError as e:
                print(f"Connection error: {e}, retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
        else:
            print("Failed to connect to the server after several attempts.")
            exit(1)

# Download the PDF file
download_pdf(PDF_URL)

# Verify that the file has been downloaded
print(os.listdir())

# Upload the PDF file
upload_pdf()