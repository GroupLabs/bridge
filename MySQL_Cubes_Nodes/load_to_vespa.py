import pandas as pd 
import numpy as np 
import os 
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import openai
from dotenv import load_dotenv, find_dotenv
from vespa.package import Schema, Document, Field, FieldSet, ApplicationPackage, Component, Parameter, RankProfile, Function, FirstPhaseRanking, SecondPhaseRanking
import hashlib
import unicodedata
from vespa.application import Vespa
from vespa.deployment import VespaDocker
from vespa.io import VespaQueryResponse

load_dotenv()

vespa_endpoint = 'http://localhost:8080/'

app = Vespa(url = vespa_endpoint)

def sample_pdfs():
    return [
        {
            "title": "ColBERTv2: Effective and Efficient Retrieval via Lightweight Late Interaction",
            "url": "https://arxiv.org/pdf/2112.01488.pdf",
            "authors": "Keshav Santhanam, Omar Khattab, Jon Saad-Falcon, Christopher Potts, Matei Zaharia"
        },
        {
            "title": "ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT",
            "url": "https://arxiv.org/pdf/2004.12832.pdf",
            "authors": "Omar Khattab, Matei Zaharia"
        },
        {
            "title": "On Approximate Nearest Neighbour Selection for Multi-Stage Dense Retrieval",
            "url": "https://arxiv.org/pdf/2108.11480.pdf",
            "authors": "Craig Macdonald, Nicola Tonellotto"
        },
        {
            "title": "A Study on Token Pruning for ColBERT",
            "url": "https://arxiv.org/pdf/2112.06540.pdf",
            "authors": "Carlos Lassance, Maroua Maachou, Joohee Park, Stéphane Clinchant"
        },
        {
            "title": "Pseudo-Relevance Feedback for Multiple Representation Dense Retrieval",
            "url": "https://arxiv.org/pdf/2106.11251.pdf",
            "authors": "Xiao Wang, Craig Macdonald, Nicola Tonellotto, Iadh Ounis"
        }

    ]

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size = 1024, #chars, not llm tokens
    chunk_overlap  = 0,
    length_function = len,
    is_separator_regex = False,
)

def remove_control_characters(s):
    return "".join(ch for ch in s if unicodedata.category(ch)[0]!="C")

my_docs_to_feed = []
for pdf in sample_pdfs():
    url = pdf['url']
    loader = PyPDFLoader(url)
    pages = loader.load_and_split()
    for index, page in enumerate(pages):
        source = page.metadata['source']
        chunks = text_splitter.transform_documents([page])
        text_chunks = [chunk.page_content for chunk in chunks]
        text_chunks = [remove_control_characters(chunk) for chunk in text_chunks]
        page_number = index + 1
        for chunkno, chunk in enumerate(text_chunks):
          vespa_id = f"{url}#{page_number}#{chunkno}"
          hash_value = hashlib.sha1(vespa_id.encode()).hexdigest()
          fields = {
              "title" : pdf['title'],
              "url" : url,
              "page": page_number,
              "id": hash_value,
              "authors": [a.strip() for a in pdf['authors'].split(",")],
              "chunkno": chunkno,
              "chunk": chunk,
              "metadata": page.metadata
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

app.feed_iterable(schema="pdf", iter=vespa_feed("all"), namespace="personal", callback=callback)

import requests
import json

# Your Vespa endpoint

# Feed each document
# headers = {"Content-Type": "application/json"}
# for doc in my_docs_to_feed:
#     document_id = f"id:pdf:pdf::{doc['id']}"
#     url = f"{vespa_endpoint}pdf/pdf/docid/{doc['id']}"
#     data = json.dumps({"fields": doc})
#     response = requests.post(url, data=data, headers=headers)
#     print(response.json())

response:VespaQueryResponse = app.query(
    yql="select id,title,page,chunkno,chunk from pdf where userQuery() or ({targetHits:10}nearestNeighbor(embedding,q))",
    groupname="all",
    ranking="colbert",
    query="why is colbert effective?",
    body={
        "presentation.format.tensors": "short-value",
        "input.query(q)": "embed(e5, \"why is colbert effective?\")",
        "input.query(qt)": "embed(colbert, \"why is colbert effective?\")",
    }
)

print(json.dumps(response.hits[0], indent=2))

