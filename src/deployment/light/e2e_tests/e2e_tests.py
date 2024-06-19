# import os
import requests

# ['sampleunsecuredpdf.pdf', 'Dockerfile', 'e2e_tests.py']
# print(os.listdir())

with open('sampleunsecuredpdf.pdf', 'rb') as f:
    files = {"file": ('sampleunsecuredpdf.pdf', f, "application/pdf")}
    r = requests.post("http://deployment-api-1:8000/load", files=files)

if r.status_code == 202:
    print("Successfully acquired the task id")
    task_id = r.json()["task_id"]
    print(task_id)
else:
    exit(1)
