FROM python:3.11.7-slim

RUN pip install --no-cache-dir requests

WORKDIR /app

COPY . ./

ADD https://uwaterloo.ca/onbase/sites/ca.onbase/files/uploads/files/sampleunsecuredpdf.pdf /app/sampleunsecuredpdf.pdf

CMD ["python", "e2e_tests.py"]
