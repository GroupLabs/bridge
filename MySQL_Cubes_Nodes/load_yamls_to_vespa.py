import json
import yaml
import pandas as pd 
import numpy as np 
import os
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
import openai
from vespa.application import Vespa
from vespa.io import VespaQueryResponse
from dotenv import load_dotenv, find_dotenv
import unicodedata

load_dotenv(find_dotenv(r"C:\Users\Eugene\Documents\GroupLabs\bridge\MySQL_Cubes_Nodes\.env"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

CUBES_DIR = r"C:\Users\Eugene\Documents\GroupLabs\bridge\MySQL_Cubes_Nodes\MySql\models\cubes\\"

vespa_endpoint = 'http://localhost:8080/'

app = Vespa(url = vespa_endpoint)

yamls = []

for yaml_file in os.listdir(CUBES_DIR):
    with open(CUBES_DIR + yaml_file, 'r') as file:
        yamls.append(yaml.safe_load(file))

my_docs_to_feed = []

def remove_control_characters(s):
    return "".join(ch for ch in s if unicodedata.category(ch)[0]!="C")

#text_splitter = SemanticChunker(OpenAIEmbeddings(api_key=OPENAI_API_KEY))

#docs = text_splitter.create_documents([yamls[0]["description"]])
#print(docs[1].page_content)

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size = 1024, #chars, not llm tokens
    chunk_overlap  = 0,
    length_function = len,
    is_separator_regex = False,
)

chunk_id = 0

for yaml_content in yamls:
    
    docs = text_splitter.split_text(yaml_content["description"])
    docs = [remove_control_characters(doc) for doc in docs]
    
    for doc_id, doc in enumerate(docs):
        
        chunk_id += 1
        
        fields = {
              "id" : chunk_id,
              "name" : yaml_content['name'],
              "sql_name" : yaml_content['sql_name'],
              "dimensions": yaml_content['dimensions'],
              "joins": yaml_content['joins'] if 'joins' in yamls[0].keys() else [""],
              "chunkno": doc_id,
              "chunk": doc
          }
        
        my_docs_to_feed.append(fields)
        
from typing import Iterable
def vespa_feed(user:str) -> Iterable[dict]:
    for doc in my_docs_to_feed:
        yield {
            "fields": doc,
            "id": doc["id"],
            "groupname": "all"
        }

from vespa.io import VespaResponse

def callback(response:VespaResponse, id:str):
    if not response.is_successful():
        print(f"Document {id} failed to feed with status code {response.status_code}, url={response.url} response={response.json}")

app.feed_iterable(schema="yamls", iter=vespa_feed("all"), namespace="personal", callback=callback)
        
        




response:VespaQueryResponse = app.query(
    yql="select name,chunkno,chunk, dimensions from yamls where userQuery() or ({targetHits:10}nearestNeighbor(embedding,q))",
    groupname="all",
    ranking="colbert",
    query="what apples to choose?",
    body={
        "presentation.format.tensors": "short-value",
        "input.query(q)": "embed(e5, \"what apples to choose?\")",
        "input.query(qt)": "embed(colbert, \"what apples to choose?\")",
    }
)

print(json.dumps(response.hits[0], indent=2))