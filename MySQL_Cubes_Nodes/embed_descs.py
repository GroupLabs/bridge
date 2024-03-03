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

load_dotenv()

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
    
pdf_schema = Schema(
            name="pdf",
            mode="streaming",
            document=Document(
                fields=[
                    Field(name="id", type="string", indexing=["summary"]),
                    Field(name="title", type="string", indexing=["summary", "index"]),
                    Field(name="url", type="string", indexing=["summary", "index"]),
                    Field(name="authors", type="array<string>", indexing=["summary", "index"]),
                    Field(name="metadata", type="map<string,string>", indexing=["summary", "index"]),
                    Field(name="page", type="int", indexing=["summary", "attribute"]),
                    Field(name="chunkno", type="int", indexing=["summary", "attribute"]),
                    Field(name="chunk", type="string", indexing=["summary", "index"]),

                    Field(name="embedding", type="tensor<bfloat16>(x[384])",
                        indexing=['"passage: " . (input title || "") . " " . (input chunk || "")', "embed e5", "attribute"],
                        attribute=["distance-metric: angular"],
                        is_document_field=False
                    ),

                    Field(name="colbert", type="tensor<int8>(dt{}, x[16])",
                        indexing=['(input title || "") . " " . (input chunk || "")', "embed colbert", "attribute"],
                        is_document_field=False
                    )
                ],
            ),
            fieldsets=[
                FieldSet(name = "default", fields = ["title", "chunk"])
            ]
)

vespa_app_name = "pdfs"
vespa_application_package = ApplicationPackage(
        name=vespa_app_name,
        schema=[pdf_schema],
        components=[
            Component(id="e5", type="hugging-face-embedder",
              parameters=[
                  Parameter("transformer-model", {"url": "https://huggingface.co/intfloat/e5-small-v2/resolve/main/model.onnx"}),
                  Parameter("tokenizer-model", {"url": "https://huggingface.co/intfloat/e5-small-v2/raw/main/tokenizer.json"})
              ]
            ),
            Component(id="colbert", type="colbert-embedder",
              parameters=[
                  Parameter("transformer-model", {"url": "https://huggingface.co/colbert-ir/colbertv2.0/resolve/main/model.onnx"}),
                  Parameter("tokenizer-model", {"url": "https://huggingface.co/colbert-ir/colbertv2.0/raw/main/tokenizer.json"})
              ]
            )
        ]
)

colbert = RankProfile(
    name="colbert",
    inputs=[
        ("query(q)", "tensor<float>(x[384])"),
        ("query(qt)", "tensor<float>(qt{}, x[128])")
        ],
    functions=[
        Function(
            name="unpack",
            expression="unpack_bits(attribute(colbert))"
        ),
        Function(
            name="cos_sim",
            expression="closeness(field, embedding)"
        ),
        Function(
            name="max_sim",
            expression="""
                sum(
                    reduce(
                        sum(
                            query(qt) * unpack() , x
                        ),
                        max, dt
                    ),
                    qt
                )
            """
        )
    ],
    first_phase=FirstPhaseRanking(
        expression="cos_sim"
    ),
    second_phase=SecondPhaseRanking(
        expression="max_sim"
    ),
    match_features=["max_sim", "cos_sim"]
)

pdf_schema.add_rank_profile(colbert)

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