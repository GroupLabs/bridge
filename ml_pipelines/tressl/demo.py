# to run first:
# pip install easyocr marker

import streamlit as st

st.title("Data Ingestor (Human in the Loop)")

with st.sidebar:
    data = st.file_uploader("Data (PDF, JPEG)", label_visibility='visible')

    table_of_qs = st.file_uploader("Output (CSV, XLSX)", label_visibility='visible')

if table_of_qs is not None:
    st.write(table_of_qs)

import tempfile
import shutil
import PyPDF2
import os

from marker.convert import convert_single_pdf
from marker.models import load_all_models
import json

fname = PDF_path
model_lst = load_all_models()

print("models loaded")

from vector_store import VectorStore

vs = VectorStore()

def marker(pdf_path):
    full_text, out_meta = convert_single_pdf(pdf_path, model_lst, max_pages=None, parallel_factor=2)

    out_path = f'{pdf_path}_marked.md'

    with open(out_path, "w+", encoding='utf-8') as f:
        f.write(full_text)

    out_meta_filename = out_path.rsplit(".", 1)[0] + "_meta.json"
    with open(out_meta_filename, "w+") as f:
        f.write(json.dumps(out_meta, indent=4))

    return full_text

def split_pdf_into_pages(pdf_path, output_folder):
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)

        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        for page_num in range(len(reader.pages)):
            writer = PyPDF2.PdfWriter()
            writer.add_page(reader.pages[page_num])

            output_filename = os.path.join(output_folder, f'page_{page_num + 1}.pdf')
            with open(output_filename, 'wb') as output_file:
                writer.write(output_file)

            marked_text = marker(output_filename)
            vs.store_page(marked_text, page_num + 1)
            print(f"Ingested: {output_filename}")

def save_uploaded_file(uploaded_file):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            shutil.copyfileobj(uploaded_file, tmp_file)
            return tmp_file.name
    except Exception as e:
        print(e)
        return None

if data is not None:
    temp_file_path = save_uploaded_file(data)
    if temp_file_path:
        split_pdf_into_pages(temp_file_path, 'temp')
        # Remember to delete the temp file after processing
        os.remove(temp_file_path)