import unicodedata
import os
import yaml
from uuid import uuid5, NAMESPACE_URL
import re
from pathlib import Path
import json

from celery import Celery

from unstructured.partition.text import partition_text
from unstructured.partition.rtf import partition_rtf
from unstructured.partition.doc import partition_doc
from unstructured.partition.docx import partition_docx
from unstructured.partition.pdf import partition_pdf # pikapdf dependency is not fork safe, can we remove this dep?
from unstructured.partition.epub import partition_epub
# from unstructured.partition.latex import partition_latex # there is no partition_latex
from unstructured.partition.md import partition_md
from unstructured.partition.ppt import partition_ppt
from unstructured.partition.pptx import partition_pptx


from connect.postgres import postgres_to_yamls
from config import config
from log import setup_logger
from typeutils import get_pathtype, parse_connection_string
from elasticutils import Search
from tritonutils import TritonClient

import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="celery.platforms")

CELERY_BROKER_URL = config.CELERY_BROKER_URL
CELERY_RESULT_BACKEND = config.CELERY_RESULT_BACKEND

# logger
logger = setup_logger("storage")

# celery config

celery_app = Celery(
    "worker",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    broker_connection_retry_on_startup=True,
    task_serializer='json',
    accept_content=['json'],  # Ignore other content
    result_serializer='json',
    timezone='Europe/London',
    enable_utc=True,
    result_expires=None,  # Results do not expire
    task_track_started=True,
)

# elasticsearch
es = Search()


try:
    # triton server
    tc = TritonClient()
except Exception as e:
    print(f"Triton not available: {e}")

@celery_app.task(name="load_data_task")
def load_data(filepath: str, read=True, c_type=None):

    # if connection type is not provided, try to infer it
    if not c_type:
        filepath = Path(filepath).absolute().as_posix() # standardize path
        c_type = get_pathtype(filepath) # checks for illegal paths and returns type

    print("Using connection type: " + c_type)

    # unstructured

    if c_type == "txt":
        _txt(filepath)

    elif c_type == "rtf":
        _rtf(filepath)
    
    elif c_type == "doc":
        _doc(filepath)

    elif c_type == "docx":
        _docx(filepath)
    
    elif c_type == "pdf":
        _pdf(filepath, read_pdf=read)
    
    elif c_type == "epub":
        _epub(filepath)

    elif c_type == "latex":
        _latex(filepath)

    elif c_type == "markdown":
        _markdown(filepath)

    elif c_type == "ppt":
        _ppt(filepath)
    
    elif c_type == "pptx":
        _pptx(filepath)

    # structured

    elif c_type == "csv":
        _csv(filepath)

    elif c_type == "tsv":
        _tsv(filepath)
    
    elif c_type == "parquet":
        _parquet(filepath)
    
    elif c_type == "xlsx":
        _xlsx(filepath)

    elif c_type == "db":
        # check if input is a supported connection string
        c_string = parse_connection_string(filepath)

        if c_string: # or other structured filetypes!
            _db(
                db_type=c_string["database_type"],
                host=c_string["host"],
                user=c_string["user"],
                password=c_string["password"],
                )

    # mixed

    elif c_type == "dir":
        # recursively call load_data
        pass

    elif c_type == "json":
        _json(filepath)
    
    elif c_type == "yaml":
        _yaml(filepath)

    # third party

    elif c_type == "linear":
        _linear(filepath)

    else:
        logger.warning("unsupported filetype encountered.")
        raise NotImplementedError(f"File ({c_type}) type is not supported.")
    
    if os.path.exists(filepath): # remove tempfile, not needed if we don't create the temp file
            os.remove(filepath)

    return c_type

def _retrieve_all_objects(index: str):
    response = es.retrieve_all_objects(index)
    return response

def retrieve_object_ids(index: str):
    result = es.retrieve_object_ids(index)

    unique_docs = result['aggregations']['unique_docs']['buckets']
    doc_tuples = [(bucket['key']['document_id'], bucket['key']['document_name'], bucket['doc_count']) for bucket in unique_docs]

    return doc_tuples

def query(q: str, index: str, doc_ids: str = None):
    return es.hybrid_search(q, index, doc_ids)

## unstructured formats

def _txt(filepath, chunking_strategy="basic"):
    
    doc_id = str(uuid5(NAMESPACE_URL, filepath))

    try:
        elements = partition_text(filepath, chunking_strategy=chunking_strategy)
    except Exception as e:
        logger.error(f"Failed to parse TEXT elements: {e}")
        return

    if elements is not None:

        for i, e in enumerate(elements):
            chunk = "".join(
                ch for ch in e.text if unicodedata.category(ch)[0] != "C"
            )  # remove control characters
            
            formatted_chunk = re.sub(r'(?<=[.?!])(?=[^\s])', ' ', chunk) # this will add a space character after every ". ? !"

            fields = {
                "document_id": doc_id,  # document id from path
                "access_group": "",  # not yet implemented
                "document_name": os.path.basename(filepath),
                "chunk_text": formatted_chunk,
                "chunking_strategy": chunking_strategy,
                "chunk_no": i,
            }

            # Insert the document into Elasticsearch
            es.insert_object(fields, index="text_chunk")
    
    os.remove(filepath)

def _rtf(filepath, chunking_strategy="by_title"):
    doc_id = str(uuid5(NAMESPACE_URL, filepath))

    try:
        elements = partition_rtf(filepath, chunking_strategy=chunking_strategy)
    except Exception as e:
        logger.error(f"Failed to parse RTF elements: {e}")
        return

    if elements is not None:

        for i, e in enumerate(elements):
            chunk = "".join(
                ch for ch in e.text if unicodedata.category(ch)[0] != "C"
            )  # remove control characters
            
            formatted_chunk = re.sub(r'(?<=[.?!])(?=[^\s])', ' ', chunk) # this will add a space character after every ". ? !"

            fields = {
                "document_id": doc_id,  # document id from path
                "access_group": "",  # not yet implemented
                "document_name": os.path.basename(filepath),
                "chunk_text": formatted_chunk,
                "chunking_strategy": chunking_strategy,
                "chunk_no": i,
            }

            # Insert the document into Elasticsearch
            es.insert_object(fields, index="text_chunk")
    
    os.remove(filepath)

def _doc(filepath, chunking_strategy="by_title"):
    doc_id = str(uuid5(NAMESPACE_URL, filepath))

    try:
        elements = partition_doc(filepath, chunking_strategy=chunking_strategy)
    except Exception as e:
        logger.error(f"Failed to parse DOC elements: {e}")
        return

    if elements is not None:

        for i, e in enumerate(elements):
            chunk = "".join(
                ch for ch in e.text if unicodedata.category(ch)[0] != "C"
            )  # remove control characters
            
            formatted_chunk = re.sub(r'(?<=[.?!])(?=[^\s])', ' ', chunk) # this will add a space character after every ". ? !"

            fields = {
                "document_id": doc_id,  # document id from path
                "access_group": "",  # not yet implemented
                "document_name": os.path.basename(filepath),
                "chunk_text": formatted_chunk,
                "chunking_strategy": chunking_strategy,
                "chunk_no": i,
            }

            # Insert the document into Elasticsearch
            es.insert_object(fields, index="text_chunk")
    
    os.remove(filepath)

def _docx(filepath, chunking_strategy="by_title"):
    doc_id = str(uuid5(NAMESPACE_URL, filepath))

    try:
        elements = partition_docx(filepath, chunking_strategy=chunking_strategy)
    except Exception as e:
        logger.error(f"Failed to parse DOCX elements: {e}")
        return

    if elements is not None:

        for i, e in enumerate(elements):
            chunk = "".join(
                ch for ch in e.text if unicodedata.category(ch)[0] != "C"
            )  # remove control characters
            
            formatted_chunk = re.sub(r'(?<=[.?!])(?=[^\s])', ' ', chunk) # this will add a space character after every ". ? !"

            fields = {
                "document_id": doc_id,  # document id from path
                "access_group": "",  # not yet implemented
                "document_name": os.path.basename(filepath),
                "chunk_text": formatted_chunk,
                "chunking_strategy": chunking_strategy,
                "chunk_no": i,
            }

            # Insert the document into Elasticsearch
            es.insert_object(fields, index="text_chunk")
    
    os.remove(filepath)

def _pdf(filepath, read_pdf=True, chunking_strategy="by_title"):
    
    doc_id = str(uuid5(NAMESPACE_URL, filepath))

    if read_pdf: # read pdf
        try:
            elements = partition_pdf(filepath, strategy="hi_res", chunking_strategy=chunking_strategy)
        except Exception as e:
            logger.error(f"Failed to parse PDF elements: {e}")
            return

        if elements is not None:
            for i, e in enumerate(elements):
                chunk = "".join(
                    ch for ch in e.text if unicodedata.category(ch)[0] != "C"
                )  # remove control characters
                
                formatted_chunk = re.sub(r'(?<=[.?!])(?=[^\s])', ' ', chunk) # this will add a space character after every ". ? !"

                fields = {
                    "document_id": doc_id,  # document id from path
                    "access_group": "",  # not yet implemented
                    "document_name": os.path.basename(filepath),
                    "chunk_text": formatted_chunk,
                    "chunking_strategy": chunking_strategy,
                    "chunk_no": i,
                }

                # Insert the document into Elasticsearch
                es.insert_object(fields, index="text_chunk")
    else:
        raise PermissionError('File is not readable.')
    
    os.remove(filepath)

def _epub(filepath, chunking_strategy="by_title"):
    doc_id = str(uuid5(NAMESPACE_URL, filepath))

    try:
        elements = partition_epub(filepath, chunking_strategy=chunking_strategy)
    except Exception as e:
        logger.error(f"Failed to parse EPUB elements: {e}")
        return

    if elements is not None:

        for i, e in enumerate(elements):
            chunk = "".join(
                ch for ch in e.text if unicodedata.category(ch)[0] != "C"
            )  # remove control characters
            
            formatted_chunk = re.sub(r'(?<=[.?!])(?=[^\s])', ' ', chunk) # this will add a space character after every ". ? !"

            fields = {
                "document_id": doc_id,  # document id from path
                "access_group": "",  # not yet implemented
                "document_name": os.path.basename(filepath),
                "chunk_text": formatted_chunk,
                "chunking_strategy": chunking_strategy,
                "chunk_no": i,
            }

            # Insert the document into Elasticsearch
            es.insert_object(fields, index="text_chunk")
    
    os.remove(filepath)

def _latex(filepath, chunking_strategy="by_title"):
    raise NotImplementedError(f"Ingestion for {filepath} is not implemented yet.")

def _markdown(filepath, chunking_strategy="by_title"):
    doc_id = str(uuid5(NAMESPACE_URL, filepath))

    try:
        elements = partition_md(filepath, chunking_strategy=chunking_strategy)
    except Exception as e:
        logger.error(f"Failed to parse MARKDOWN elements: {e}")
        return

    if elements is not None:

        for i, e in enumerate(elements):
            chunk = "".join(
                ch for ch in e.text if unicodedata.category(ch)[0] != "C"
            )  # remove control characters
            
            formatted_chunk = re.sub(r'(?<=[.?!])(?=[^\s])', ' ', chunk) # this will add a space character after every ". ? !"

            fields = {
                "document_id": doc_id,  # document id from path
                "access_group": "",  # not yet implemented
                "document_name": os.path.basename(filepath),
                "chunk_text": formatted_chunk,
                "chunking_strategy": chunking_strategy,
                "chunk_no": i,
            }

            # Insert the document into Elasticsearch
            es.insert_object(fields, index="text_chunk")
    
    os.remove(filepath)

def _ppt(filepath, chunking_strategy="by_title"):
    doc_id = str(uuid5(NAMESPACE_URL, filepath))

    try:
        elements = partition_ppt(filepath, chunking_strategy=chunking_strategy)
    except Exception as e:
        logger.error(f"Failed to parse PPT elements: {e}")
        return

    if elements is not None:

        for i, e in enumerate(elements):
            chunk = "".join(
                ch for ch in e.text if unicodedata.category(ch)[0] != "C"
            )  # remove control characters
            
            formatted_chunk = re.sub(r'(?<=[.?!])(?=[^\s])', ' ', chunk) # this will add a space character after every ". ? !"

            fields = {
                "document_id": doc_id,  # document id from path
                "access_group": "",  # not yet implemented
                "document_name": os.path.basename(filepath),
                "chunk_text": formatted_chunk,
                "chunking_strategy": chunking_strategy,
                "chunk_no": i,
            }

            # Insert the document into Elasticsearch
            es.insert_object(fields, index="text_chunk")
    
    os.remove(filepath)

def _pptx(filepath, chunking_strategy="by_title"):
    doc_id = str(uuid5(NAMESPACE_URL, filepath))

    try:
        elements = partition_pptx(filepath, chunking_strategy=chunking_strategy)
    except Exception as e:
        logger.error(f"Failed to parse PPTX elements: {e}")
        return

    if elements is not None:

        for i, e in enumerate(elements):
            chunk = "".join(
                ch for ch in e.text if unicodedata.category(ch)[0] != "C"
            )  # remove control characters
            
            formatted_chunk = re.sub(r'(?<=[.?!])(?=[^\s])', ' ', chunk) # this will add a space character after every ". ? !"

            fields = {
                "document_id": doc_id,  # document id from path
                "access_group": "",  # not yet implemented
                "document_name": os.path.basename(filepath),
                "chunk_text": formatted_chunk,
                "chunking_strategy": chunking_strategy,
                "chunk_no": i,
            }

            # Insert the document into Elasticsearch
            es.insert_object(fields, index="text_chunk")
    
    os.remove(filepath)

## structured formats

def _csv(filepath, read_pdf=True, chunking_strategy="by_title"):
    raise NotImplementedError(f"Ingestion for {filepath} is not implemented yet.")

def _tsv(filepath, read_pdf=True, chunking_strategy="by_title"):
    raise NotImplementedError(f"Ingestion for {filepath} is not implemented yet.")

def _parquet(filepath, chunking_strategy="by_title"):
    raise NotImplementedError(f"Ingestion for {filepath} is not implemented yet.")

def _xlsx(filepath, chunking_strategy="by_title"):
    raise NotImplementedError(f"Ingestion for {filepath} is not implemented yet.")

## Mixed formats

def _json(filepath, chunking_strategy="by_title"):
    raise NotImplementedError(f"Ingestion for {filepath} is not implemented yet.")

def _yaml(filepath, chunking_strategy="by_title"):
    raise NotImplementedError(f"Ingestion for {filepath} is not implemented yet.")

# third party formats

def _linear(filepath):

    doc_id = str(uuid5(NAMESPACE_URL, filepath))

    with open(filepath, 'r') as f:
        data = json.load(f)

    data = data['issues']
    for issue in data:
        fields = {
                    "document_id": doc_id,  # should it be the id of the linear import? Or the id of the issue?
                    "document_name": os.path.basename(filepath),
                    "access_group": "",  # not yet implemented
                    "chunk_text": f"Title: {issue['title']}\nStatus: {issue['status']}\nCreated At: {issue['createdAt']}",
                    "chunking_strategy": "by issue",
                    "chunk_no": "",
                }

        es.insert_object(fields, index="text_chunk")

def _db(db_type, host, user, password):
    # figure out which db connector to use
    if db_type == "postgres":
        postgres_to_yamls(host, user, password)
    elif db_type == "mysql":
        raise NotImplementedError
    else:
        raise NotImplementedError

    node_name = f"models/{db_type}/yamls" # should be turned to path object
    db_id = str(uuid5(NAMESPACE_URL, node_name))

    data = {}

    for i, file in enumerate(os.listdir(node_name)): # TODO: does this need to be enumerated?
        filepath = os.path.join(node_name, file)
        if file.endswith('.yaml') and os.path.isfile(filepath):
            with open(filepath, 'r') as f:
                data = yaml.safe_load(f)

                column_embeddings = {}
                if 'dimensions' in data:
                    for dimension in data['dimensions']:
                        column_name = dimension.get('name')
                        embedding = dimension.get('embedding')
                        if column_name and embedding:
                            column_embeddings[column_name] = embedding

                fields = {
                    "database_id" : db_id,
                    "access_group" : "", # not yet implemented
                    "table_name" : data["sql_name"],
                    "description_text" : data["description"],
                    "correlation_embedding" : column_embeddings,
                    "chunking_strategy" : "", # not chunked rn
                    "chunking_no" : "", # not chunked rn
                    "data_hash" : "not implemented", # for integrity check
                }

                es.insert_object(fields, index="table_meta")
                
                print("stored: " + file.split(".")[0])

if __name__ == "__main__":
    # load_data("/Users/noelthomas/Desktop/Mistral 7B Paper.pdf", True)

    from pprint import pprint

    response = es.hybrid_search("What is GQA?", "text_chunk")

    pprint(response)

    # print()
 
    print(es)
    print(es.registered_indices)




    

    # host="localhost"
    # user=os.getenv("PG_USER")
    # password=os.getenv("PG_PWD")

    # conn_str = f'postgres://{user}:{password}@{host}'

    # load_data(conn_str)

    # print(query("lepton"))
