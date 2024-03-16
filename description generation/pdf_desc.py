import openai
import pandas as pd
import numpy as np 
from PyPDF2 import PdfReader
import sys
from dotenv import load_dotenv, find_dotenv
import os
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter
import nltk
from nltk.tokenize import RegexpTokenizer
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
import re
nltk.download('stopwords')
nltk.download('wordnet')

load_dotenv(find_dotenv(r"C:\Users\Eugene\Documents\GroupLabs\bridge\.env"))

current_dir = Path(__file__).parent
connect_dir = current_dir.parent / 'connect'
sys.path.append(str(connect_dir))

from desc_gen import desc_gen

pdf_names = []
pdf_files_path = r'C:\Users\Eugene\Documents\GroupLabs\bridge\data\datasets\pdf_nonigest'
for pdf_name in os.listdir(pdf_files_path):
    pdf_names.append(pdf_name)

chunks = []

for pdf in pdf_names:
    
    with open(pdf_files_path + "\\" + pdf, "rb") as f:
        pdf = PdfReader(f)
        num_pages = len(pdf.pages)
        for page in range(len(pdf.pages)):
            #pdf_page = pdf.getPage(page)
            page_to_clean = pdf.pages[page].extract_text()
            
            page_to_clean = page_to_clean.lower()

            tokenizer = RegexpTokenizer(r'\w+')
            tokens = tokenizer.tokenize(page_to_clean)

            tokens = [x for x in tokens if x not in nltk.corpus.stopwords.words('english')]

            cleaned_page = ' '.join(tokens)
            
            if num_pages <=4: 
                chunk_size = 75
                chunk_overlap = 3 
            elif num_pages > 4 and num_pages <=12:
                chunks_size = 250
                chunk_overlap = 10
            elif num_pages >12 and num_pages <= 25:
                chunk_size = 500
                chunk_overlap = 20
            else:
                chunk_size = 1000
                chunk_overlap = 35
            
            text_splitter = RecursiveCharacterTextSplitter(
                
                chunk_size = chunk_size,
                chunk_overlap = chunk_overlap,
                length_function = len
            )
            
            temp_chunks = text_splitter.split_text(cleaned_page)
            [chunks.append(chunk) for chunk in temp_chunks]
            
            
#first k chunks, k chunks from the middle and bottom k chunks - TO BE DETERMINED
chunks_to_send = chunks[:10] + chunks[int(len(chunks)/2): int(len(chunks)/2) + 10] + chunks[-10:]

text_to_send = ' '.join(chunks_to_send)

desc = desc_gen(text_to_send)
            
                        
        


