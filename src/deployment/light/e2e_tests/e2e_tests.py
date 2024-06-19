import os
import requests

# URL of the PDF file to download
pdf_url = 'https://uwaterloo.ca/onbase/sites/ca.onbase/files/uploads/files/sampleunsecuredpdf.pdf'

# Download the PDF file
response = requests.get(pdf_url)
if response.status_code == 200:
    with open('sampleunsecuredpdf.pdf', 'wb') as f:
        f.write(response.content)
    print("PDF downloaded successfully")
else:
    print("Failed to download PDF")
    exit(1)

# Verify that the file has been downloaded
print(os.listdir())

# Upload the PDF file
with open('sampleunsecuredpdf.pdf', 'rb') as f:
    files = {"file": ('sampleunsecuredpdf.pdf', f, "application/pdf")}
    r = requests.post("http://0.0.0.0:8000/load", files=files)

if r.status_code == 202:
    print("Successfully acquired the task id")
    task_id = r.json()["task_id"]
    print(task_id)
else:
    print("Failed to upload PDF")
    exit(1)