import numpy as np 
from PyPDF2 import PdfReader
import sys
from dotenv import load_dotenv, find_dotenv
import os
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter
import nltk
from nltk.tokenize import RegexpTokenizer
nltk.download('stopwords')
nltk.download('wordnet')

load_dotenv(find_dotenv(r"C:\Users\Eugene\Documents\GroupLabs\bridge\.env"))

current_dir = Path(__file__).parent.parent
connect_dir = current_dir.parent / 'src' / 'backend' 
sys.path.append(str(connect_dir))

from auto_description import desc_gen

def text_desc(folder_path):

    descriptions = {}
    files_path = folder_path
    for file_name in os.listdir(files_path):

        chunks = []
            
        if '.pdf' in file_name:
            
            with open(files_path + "\\" + file_name, "rb") as f:
                
                pdf = PdfReader(f)

                for page in range(len(pdf.pages)):
                    #pdf_page = pdf.getPage(page)
                    page_to_clean = pdf.pages[page].extract_text()
                    
                    page_to_clean = page_to_clean.lower()

                    tokenizer = RegexpTokenizer(r'\w+')
                    tokens = tokenizer.tokenize(page_to_clean)

                    tokens = [x for x in tokens if x not in nltk.corpus.stopwords.words('english')]

                    cleaned_page = ' '.join(tokens)
                    
                    chunk_size = 1024
                    
                    text_splitter = RecursiveCharacterTextSplitter(
                        
                        chunk_size = chunk_size,
                        chunk_overlap = 20,
                        length_function = len
                    )
                    
                    temp_chunks = text_splitter.split_text(cleaned_page)
                    [chunks.append(chunk) for chunk in temp_chunks]
        elif '.txt' in file_name:
            
            with open(files_path + "\\" + file_name, "r") as f:
                
                text = f.read().lower()
                tokenizer = RegexpTokenizer(r'\w+')
                tokens = tokenizer.tokenize(text)

                tokens = [x for x in tokens if x not in nltk.corpus.stopwords.words('english')]

                cleaned_text = ' '.join(tokens)
    
                chunk_size = 1024
    
                text_splitter = RecursiveCharacterTextSplitter(
                    
                    chunk_size = chunk_size,
                    chunk_overlap = 20,
                    length_function = len
                )
    
                temp_chunks = text_splitter.split_text(cleaned_text)
                [chunks.append(chunk) for chunk in temp_chunks]
                 
                
        #15000 is the max context window tokens I'm willing to send    
        if len((' '.join(chunks)).strip().replace(" ", "")) > 15000:

            chunks_step = int(np.floor(int(np.floor(15000/chunk_size))/3))
            
            chunks_to_send = chunks[:chunks_step] + chunks[int(len(chunks)/2): int(len(chunks)/2) + chunks_step] + chunks[-chunks_step:]
            
            text_to_send = ' '.join(chunks_to_send)

        else:
            text_to_send = ' '.join(chunks)

        desc = desc_gen(text_to_send)
        
        descriptions[file_name] = desc 
    
    return descriptions