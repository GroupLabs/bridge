# purpose: handle vector storage, and retrieval

# unstructured: store as new faiss index
# structured: each column is its own entity


# purpose: convert and tag inbound data.

import faiss
import numpy as np
import pickle
import torch
from sentence_transformers import SentenceTransformer

# modalities
from pdf import pdf_to_strings

VEC_DIM = 768
EMBEDDING_MODEL_NAME = 'msmarco-distilbert-base-tas-b'
EMBEDDING_MODEL = SentenceTransformer(EMBEDDING_MODEL_NAME)

def embed(text): # create embedding from strings (and other modes later)
    return torch.as_tensor(EMBEDDING_MODEL.encode(text))

def store(input): # store input in lakehouse
    
    index = faiss.IndexFlatL2(VEC_DIM) # instantiate index
    
    if type(input) is str:
        vector = embed(input)
        index.add(vector)
        
    elif isinstance(input, list) and all(isinstance(i, str) for i in input):
        vector_list = [embed(s) for s in input]
        vectors = np.array(vector_list)
        index.add(vectors)

    with open("new.pkl", "wb") as f:
        pickle.dump(index, f)

if __name__ == "__main__":
    pass
