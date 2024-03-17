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
from unstructured.partition.pdf import partition_pdf
nltk.download('stopwords')
nltk.download('wordnet')

load_dotenv(find_dotenv(r"C:\Users\Eugene\Documents\GroupLabs\bridge\.env"))

current_dir = Path(__file__).parent.parent
connect_dir = current_dir.parent / 'src' / 'backend' / 'connect'
sys.path.append(str(connect_dir))

from desc_gen import desc_gen

def text_desc(folder_path):

    pdf_names = []
    pdf_files_path = folder_path
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
                    
                    split_id = 5
                elif num_pages > 4 and num_pages <=12:
                    
                    split_id = 7
                elif num_pages >12 and num_pages <= 25:
                    
                    split_id = 10
                else:
                    
                    split_id = 15
                
                chunk_size = 700
                
                text_splitter = RecursiveCharacterTextSplitter(
                    
                    chunk_size = chunk_size,
                    chunk_overlap = 20,
                    length_function = len
                )
                
                temp_chunks = text_splitter.split_text(cleaned_page)
                [chunks.append(chunk) for chunk in temp_chunks]
                
                
    #15000 is the max context window tokens I'm willing to send

    print(len((' '.join(chunks)).strip().replace(" ", "")))
    
    if len((' '.join(chunks)).strip().replace(" ", "")) > 15000:

        chunks_step = int(np.floor(int(np.floor(15000/chunk_size))/3))
        
        chunks_to_send = chunks[:chunks_step] + chunks[int(len(chunks)/2): int(len(chunks)/2) + chunks_step] + chunks[-chunks_step:]
        
        text_to_send = ' '.join(chunks_to_send)

    else:
        text_to_send = ' '.join(chunks)

    desc = desc_gen(text_to_send)
    
    return desc


