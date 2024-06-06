import unicodedata
import os
import yaml
from uuid import uuid4, uuid5, NAMESPACE_URL
import time
import re
from pathlib import Path

from celery import Celery

from unstructured.partition.pdf import partition_pdf  # pikapdf dependency is not fork safe, can we remove this dep?
from unstructured.partition.text import partition_text
from unstructured.partition.md import partition_md
from unstructured.partition.doc import partition_doc
from unstructured.partition.docx import partition_docx
from unstructured.partition.odt import partition_odt
from unstructured.partition.rtf import partition_rtf
from unstructured.partition.ppt import partition_ppt
from unstructured.partition.pptx import partition_pptx
import pandas as pd
from PIL import Image
from datetime import datetime


from auto_description import describe_table, describe_picture

from connect.postgres import postgres_to_yamls
from config import config
from log import setup_logger
from typeutils import get_pathtype, parse_connection_string
from elasticutils import Search
from tritonutils import TritonClient
from integration_layer import parse_config_from_string, format_model_inputs, prepare_inputs_for_model
import torch

import PyPDF2

#import mlflow
#from mlflow.tracking import MlflowClient
#from mlflow.exceptions import MlflowException

import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="celery.platforms")

CELERY_BROKER_URL = config.CELERY_BROKER_URL

# logger
logger = setup_logger("storage")

#mlflow.set_tracking_uri(config.MLFLOW_TRACKING_URI)
"""
with mlflow.start_run():
    mlflow.log_param("test", "value")
    print("Logged test parameter to MLflow.")
"""
# celery config
celery_app = Celery(
    "worker",
    broker=CELERY_BROKER_URL,  # Default RabbitMQ credentials
    backend="rpc://",  # Use RPC as the backend with RabbitMQ
)

celery_app.conf.update(
    broker_connection_retry_on_startup=True,
    task_serializer='json',
    accept_content=['json'],  # Ignore other content
    result_serializer='json',
    timezone='Europe/London',
    enable_utc=True,
)

# elasticsearch
es = Search()


try:
    # triton server
    tc = TritonClient()
except Exception as e:
    print(f"Triton not available: {e}")

try:
    # triton server
    tc = TritonClient()
except Exception as e:
    print(f"Triton not available: {e}")

@celery_app.task(name="sort_documents_task")
def sort_docs(type: str, order: str):
    ordered = []
    # Define the index

    if type == "name":
        # Perform the search query with sorting
        response = es.search(
            index='parent_doc',
            body={
                "query": {
                    "match_all": {}
                },
                "sort": [
                    {
                        "document_name.keyword": {
                            "order":order
                        }
                    }
                ]
            },
            size=10000  # Specify the number of documents to retrieve
        )
    if type == "size":
        # Perform the search query with sorting by Size_numeric
        response = es.search(
            index='parent_doc',
            body={
                "query": {
                    "match_all": {}
                },
                "sort": [
                    {
                        "Size_numeric": {
                            "order": order
                        }
                    }
                ]
            },
            size=10000  # Specify the number of documents to retrieve
        )
    if type == "type":
        # Perform the search query with sorting by Type
        response = es.search(
            index='parent_doc',
            body={
                "query": {
                    "match_all": {}
                },
                "sort": [
                    {
                        "Type": {
                            "order": order
                        }
                    }
                ]
            },
            size=10000  # Specify the number of documents to retrieve
        )
    if type == "created":
        # Perform the search query with sorting by Created
        response = es.search(
            index='parent_doc',
            body={
                "query": {
                    "match_all": {}
                },
                "sort": [
                    {
                        "Created": {
                            "order": order  
                        }
                    }
                ]
            },
            size=10000  # Specify the number of documents to retrieve
        )


    # Print the results
    for hit in response['hits']['hits']:
        ordered.append(hit)
    return ordered

@celery_app.task(name="load_data_task")
def load_data(filepath: str, read=True):

    # check if input is a connection string
    c_string = parse_connection_string(filepath)

    # structured
    if c_string: # or other structured filetypes!
        _db(
            db_type=c_string["database_type"],
            host=c_string["host"],
            user=c_string["user"],
            password=c_string["password"],
            )
    else:
        filepath = Path(filepath).absolute().as_posix() # standardize path

        pathtype = get_pathtype(filepath) # checks for illegal paths and returns type

        # unstructured
        if pathtype == "pdf":

            _pdf(filepath, read_pdf=read)

        elif pathtype == "txt":

            _txt(filepath, read_txt=read)
            
        elif pathtype == "markdown":

            _md(filepath, read_md=read)

        elif pathtype == "doc":

            _doc(filepath, read_doc=read)

        elif pathtype == "docx":

            _docx(filepath, read_docx=read)

        elif pathtype == "odt":

            _odt(filepath, read_odt=read)

        elif pathtype == "rtf":

            _rtf(filepath, read_odt=read)

        elif pathtype == "csv":

            _csv(filepath)

        elif pathtype == "xlsx" or pathtype == "xls":

            _excel(filepath)

        elif pathtype == "jpeg" or pathtype == "jpg" or pathtype == "png":

            _picture(filepath)    

        elif pathtype == "ppt":

            _ppt(filepath)    

        elif pathtype == "pptx":

            _pptx(filepath)   

        # mix
        elif pathtype == "dir":
            # recursively call load_data
            pass

        else:
            logger.warning("unsupported filetype encountered.")
            raise NotImplementedError(f"File ({pathtype}) type is not supported.")
    
    if os.path.exists(filepath): # remove tempfile, not needed if we don't create the temp file
            os.remove(filepath)

@celery_app.task(name="get_inference_task")
def get_inference(model, data):
    search_body = { #finds the document id which has the model name.
    "query": {
        "match": {
            "model_name": model
            }
        }
    }

    response = es.search(index="model_meta", body=search_body)

    

    hit = response['hits']['hits']

    if not hit:
        logger.info("Model is not present in Elastic Search")
        return
    else:
        parsed_data = {
        'input': response['hits']['hits'][0]['_source']['input'],
        'output': response['hits']['hits'][0]['_source']['output']
    }   
    
    models_inputs = prepare_inputs_for_model(data, parsed_data)


        


    return models_inputs


@celery_app.task(name="load_model_task")
def load_model(model, config, description):

    # load to ES
    # need to fetch model description 
    fields = {
        "model_id" : uuid4(),
        "access_group" : "", # not yet implemented
        "model_name" : model,
        "description_text" : description,
        "input" : extract_io_metadata(config, 'input'),
        "output" : extract_io_metadata(config, 'output'), 
        "chunking_strategy" : "", # not chunked rn
        "chunking_no" : "", # not chunked rn
        "model_hash" : "not implemented", # for integrity check
    }

    es.insert_document(fields, index="model_meta")

    # load to triton
    tc.add_model(model,config) # TODO this function needs to leave the path of the original alone so that
    # we can do an os.remove at this level, or maybe we should pass file objects to each of these functions?


def extract_io_metadata(config, io_type):
    with open(config, 'r') as file:
        config_content = file.read()
    
    pattern = fr'{io_type}\s*\[\s*((?:\s*{{\s*(?:.|\n)*?\s*}}\s*,?\s*)+)\s*\]\s*'
    match = re.search(pattern, config_content, re.DOTALL)

    io_info = []

    if match:
        # Find all blocks within the input or output section
        blocks = re.findall(r'{(.*?)}', match.group(0), re.DOTALL)

        # Iterate over each block
        for block in blocks:
            current_info = {}

            # Extract name, data type, and dims from the block
            name_match = re.search(r'name:\s*"([^"]+)"', block)
            current_info['name'] = name_match.group(1) if name_match else None

            data_type_match = re.search(r'data_type:\s*TYPE_(\w+)', block)
            current_info['data_type'] = data_type_match.group(1) if data_type_match else None

            dims_match = re.search(r'dims:\s*\[\s*(.*?)\s*\]', block)
            dims = dims_match.group(1) if dims_match else None
            current_info['dims'] = [int(dim) for dim in dims.split(',')] if dims else None

            # Append the current input or output info to the list
            io_info.append(current_info)
    
    return io_info

# TODO remove temp models

def query(q: str, index: str):
    return es.hybrid_search(q, index)

def get_parent(chunk):
    response = es.search(
        index='text_chunk',
        body={
            "query": {
                "match_phrase": {
                    "chunk_text": chunk  # Replace with the text you want to search for
                }
            },
            "size": 1  # Retrieve only one document
        }
    )
    
    # Check if any hits are returned
    if response['hits']['total']['value'] > 0:
        # Extract the document_id from the first hit
        document_id = response['hits']['hits'][0]['_source']['document_id']
        return get_document_name(document_id)
    else:
        return None
    
def get_document_name(document_id):
    response = es.search(
        index='parent_doc',
        body={
            "query": {
                "term": {
                    "document_id": document_id  # Exact match on document_id
                }
            },
            "size": 1  # Retrieve only one document
        }
    )
    
    # Check if any hits are returned
    if response['hits']['total']['value'] > 0:
        # Extract the document_name from the first hit
        document_name = response['hits']['hits'][0]['_source']['document_name']
        return document_name
    else:
        return None


def insert_parent(filepath):
    doc_id = str(uuid5(NAMESPACE_URL, filepath))
    # Get the file size in bytes
    file_size_bytes = os.path.getsize(filepath)
    # Convert bytes to megabytes
    file_size_mb = file_size_bytes / (1024 * 1024)
    size = f"{file_size_mb:.2f} MB"
    basename_with_ext = os.path.basename(filepath)
    fields = {
        "document_id": doc_id,  # document id from path
        "document_name": os.path.splitext(basename_with_ext)[0],  
        "Size": size,
        'Size_numeric': file_size_mb,  
        "Type": os.path.splitext(filepath)[-1],
        "Created": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
    }
    es.insert_document(fields, index="parent_doc")


def _pdf(filepath, read_pdf=True, chunking_strategy="by_title"):
    
    doc_id = str(uuid5(NAMESPACE_URL, filepath))

    if read_pdf: # read pdf
        try:
            elements = partition_pdf(filepath, strategy="hi_res", chunking_strategy=chunking_strategy)
        except Exception as e:
            logger.error(f"Failed to parse PDF elements: {e}")
            return

        if elements is not None:
            pdf_file = open(filepath, 'rb')

            
            for i, e in enumerate(elements):

                chunk = "".join(
                    ch for ch in e.text if unicodedata.category(ch)[0] != "C"
                )  # remove control characters
                

                fields = {
                    "document_id": doc_id,  # document id from path
                    "access_group": "",  # not yet implemented
                    "chunk_text": chunk,
                    "chunking_strategy": chunking_strategy,
                    "chunk_no": i,
                    "page_number" : e.metadata.page_number
                }

                # Insert the document into Elasticsearch
                es.insert_document(fields, index="text_chunk")

            pdf_file.close()
    else:
        fields = {
            "access_group" : "", # not yet implemented
            "description_text" : "", # not yet implemented
            "file_path" : filepath,
            "embedding" : [0],
            "last_updated" : int(time.time()), # current time in long int
            "data_hash" : "not implemented"
        }

        es.insert_document(fields, index="document_meta")
    insert_parent(filepath)
    os.remove(filepath)


def _txt(filepath, read_txt=True, chunking_strategy="by_title"):
    
    doc_id = str(uuid5(NAMESPACE_URL, filepath))

    if read_txt:  # read txt
        try:
            elements = partition_text(filepath, chunking_strategy=chunking_strategy)
        except Exception as e:
            logger.error(f"Failed to partition text: {e}")
            return

        if elements:
            for i, e in enumerate(elements):
                chunk = "".join(
                    ch for ch in e.text if unicodedata.category(ch)[0] != "C"
                )  # remove control characters

                fields = {
                    "document_id": doc_id,  # document id from path
                    "access_group": "",  # not yet implemented
                    "chunk_text": chunk,
                    "chunking_strategy": chunking_strategy,
                    "chunk_no": i,
                    "page_number" : e.metadata.page_number
                }
                
                es.insert_document(fields, index="text_chunk")

    else:
        fields = {
            "access_group": "",  # not yet implemented
            "description_text": "",  # not yet implemented
            "file_path": filepath,
            "embedding": [0],
            "last_updated": int(time.time()),  # current time in long int
            "data_hash": "not implemented"
        }

        es.insert_document(fields, index="document_meta")
    insert_parent(filepath)
    os.remove(filepath)

def _md(filepath, read_md=True, chunking_strategy="by_title"):
    
    doc_id = str(uuid5(NAMESPACE_URL, filepath))

    if read_md:  # read txt
        try:
            elements = partition_md(filepath, chunking_strategy=chunking_strategy)
        except Exception as e:
            logger.error(f"Failed to partition text: {e}")
            return

        if elements:
            for i, e in enumerate(elements):
                chunk = "".join(
                    ch for ch in e.text if unicodedata.category(ch)[0] != "C"
                )  # remove control characters

                fields = {
                    "document_id": doc_id,  # document id from path
                    "access_group": "",  # not yet implemented
                    "chunk_text": chunk,
                    "chunking_strategy": chunking_strategy,
                    "chunk_no": i,
                    "page_number" : e.metadata.page_number
                }
                
                es.insert_document(fields, index="text_chunk")

    else:
        fields = {
            "access_group": "",  # not yet implemented
            "description_text": "",  # not yet implemented
            "file_path": filepath,
            "embedding": [0],
            "last_updated": int(time.time()),  # current time in long int
            "data_hash": "not implemented"
        }

        es.insert_document(fields, index="document_meta")
    insert_parent(filepath)
    os.remove(filepath)

def _doc(filepath, read_doc=True, chunking_strategy="by_title"):
    
    doc_id = str(uuid5(NAMESPACE_URL, filepath))

    if read_doc:  # read txt
        try:
            elements = partition_doc(filepath, chunking_strategy=chunking_strategy)
        except Exception as e:
            logger.error(f"Failed to partition text: {e}")
            return

        if elements:
            for i, e in enumerate(elements):
                chunk = "".join(
                    ch for ch in e.text if unicodedata.category(ch)[0] != "C"
                )  # remove control characters

                fields = {
                    "document_id": doc_id,  # document id from path
                    "access_group": "",  # not yet implemented
                    "chunk_text": chunk,
                    "chunking_strategy": chunking_strategy,
                    "chunk_no": i,
                    "page_number" : e.metadata.page_number
                }
                
                es.insert_document(fields, index="text_chunk")

    else:
        fields = {
            "access_group": "",  # not yet implemented
            "description_text": "",  # not yet implemented
            "file_path": filepath,
            "embedding": [0],
            "last_updated": int(time.time()),  # current time in long int
            "data_hash": "not implemented"
        }

        es.insert_document(fields, index="document_meta")
    insert_parent(filepath)
    os.remove(filepath)

def _docx(filepath, read_docx=True, chunking_strategy="by_title"):
    
    doc_id = str(uuid5(NAMESPACE_URL, filepath))

    if read_docx:  # read txt
        try:
            elements = partition_docx(filepath, chunking_strategy=chunking_strategy)
        except Exception as e:
            logger.error(f"Failed to partition text: {e}")
            return

        if elements:
            for i, e in enumerate(elements):
                chunk = "".join(
                    ch for ch in e.text if unicodedata.category(ch)[0] != "C"
                )  # remove control characters

                fields = {
                    "document_id": doc_id,  # document id from path
                    "access_group": "",  # not yet implemented
                    "chunk_text": chunk,
                    "chunking_strategy": chunking_strategy,
                    "chunk_no": i,
                    "page_number" : e.metadata.page_number
                }
                
                es.insert_document(fields, index="text_chunk")

    else:
        fields = {
            "access_group": "",  # not yet implemented
            "description_text": "",  # not yet implemented
            "file_path": filepath,
            "embedding": [0],
            "last_updated": int(time.time()),  # current time in long int
            "data_hash": "not implemented"
        }

        es.insert_document(fields, index="document_meta")
    insert_parent(filepath)
    os.remove(filepath)


def _odt(filepath, read_odt=True, chunking_strategy="by_title"):
    
    doc_id = str(uuid5(NAMESPACE_URL, filepath))

    if read_odt:  # read txt
        try:
            elements = partition_odt(filepath, chunking_strategy=chunking_strategy)
        except Exception as e:
            logger.error(f"Failed to partition text: {e}")
            return

        if elements:
            for i, e in enumerate(elements):
                chunk = "".join(
                    ch for ch in e.text if unicodedata.category(ch)[0] != "C"
                )  # remove control characters

                fields = {
                    "document_id": doc_id,  # document id from path
                    "access_group": "",  # not yet implemented
                    "chunk_text": chunk,
                    "chunking_strategy": chunking_strategy,
                    "chunk_no": i,
                    "page_number" : e.metadata.page_number
                }
                
                es.insert_document(fields, index="text_chunk")

    else:
        fields = {
            "access_group": "",  # not yet implemented
            "description_text": "",  # not yet implemented
            "file_path": filepath,
            "embedding": [0],
            "last_updated": int(time.time()),  # current time in long int
            "data_hash": "not implemented"
        }

        es.insert_document(fields, index="document_meta")
    insert_parent(filepath)
    os.remove(filepath)

def _rtf(filepath, read_rtf=True, chunking_strategy="by_title"):
    
    doc_id = str(uuid5(NAMESPACE_URL, filepath))

    if read_rtf:  # read txt
        try:
            elements = partition_rtf(filepath, chunking_strategy=chunking_strategy)
        except Exception as e:
            logger.error(f"Failed to partition text: {e}")
            return

        if elements:
            for i, e in enumerate(elements):
                chunk = "".join(
                    ch for ch in e.text if unicodedata.category(ch)[0] != "C"
                )  # remove control characters

                fields = {
                    "document_id": doc_id,  # document id from path
                    "access_group": "",  # not yet implemented
                    "chunk_text": chunk,
                    "chunking_strategy": chunking_strategy,
                    "chunk_no": i,
                    "page_number" : e.metadata.page_number
                }
                
                es.insert_document(fields, index="text_chunk")

    else:
        fields = {
            "access_group": "",  # not yet implemented
            "description_text": "",  # not yet implemented
            "file_path": filepath,
            "embedding": [0],
            "last_updated": int(time.time()),  # current time in long int
            "data_hash": "not implemented"
        }

        es.insert_document(fields, index="document_meta")
    insert_parent(filepath)
    os.remove(filepath)


def get_detailed_dtypes(df):
    detailed_dtypes = {}
    for column in df.columns:
        if pd.api.types.is_string_dtype(df[column]):
            detailed_dtypes[column] = 'string'
        elif pd.api.types.is_numeric_dtype(df[column]):
            if pd.api.types.is_integer_dtype(df[column]):
                detailed_dtypes[column] = 'integer'
            elif pd.api.types.is_float_dtype(df[column]):
                detailed_dtypes[column] = 'float'
        elif pd.api.types.is_bool_dtype(df[column]):
            detailed_dtypes[column] = 'boolean'
        else:
            detailed_dtypes[column] = 'object'
    return detailed_dtypes


def _csv(filepath):
    print("reached")
    doc_id = str(uuid5(NAMESPACE_URL, filepath))
    df = pd.read_csv(filepath)

    # Get the number of rows and columns
    rows, columns = df.shape

    # Get detailed data types of each column
    detailed_data_types = get_detailed_dtypes(df)
    
    # Convert columns to appropriate types if necessary
    for column, dtype in detailed_data_types.items():
        if dtype == 'string':
            df[column] = df[column].astype(str)
        elif dtype == 'integer':
            df[column] = pd.to_numeric(df[column], errors='coerce', downcast='integer')
        elif dtype == 'float':
            df[column] = pd.to_numeric(df[column], errors='coerce')

    # Generate YAML structure for the CSV file
    dimensions = {
        "rows": rows,
        "columns": columns
    }
    
    column_details = []
    for column in df.columns:
        column_info = {
            "name": column,
            "type": detailed_data_types[column]
        }
        column_details.append(column_info)
    
    table_name = os.path.basename(filepath)
    metadata = {
        "name": table_name,
        "dimensions": dimensions,
        "columns": column_details,
    }



    fields = {
        "document_id": doc_id,  # document id from path
        "description_text": f"{describe_table(metadata)}",
        "metadata": metadata,
        "file_path": filepath,
        "table_name": table_name,
        "embedding": [0],
        "last_updated": int(time.time()),  # current time in long int
        "data_hash": "not implemented"


    }

    es.insert_document(fields, index="table_meta")
    insert_parent(filepath)
    os.remove(filepath)


def _excel(filepath):
    doc_id = str(uuid5(NAMESPACE_URL, filepath))
    df = pd.read_excel(filepath)

    # Get the number of rows and columns
    rows, columns = df.shape

    # Get detailed data types of each column
    detailed_data_types = get_detailed_dtypes(df)
    
    # Convert columns to appropriate types if necessary
    for column, dtype in detailed_data_types.items():
        if dtype == 'string':
            df[column] = df[column].astype(str)
        elif dtype == 'integer':
            df[column] = pd.to_numeric(df[column], errors='coerce', downcast='integer')
        elif dtype == 'float':
            df[column] = pd.to_numeric(df[column], errors='coerce')

    # Generate YAML structure for the Excel file
    dimensions = {
        "rows": rows,
        "columns": columns
    }
    
    column_details = []
    for column in df.columns:
        column_info = {
            "name": column,
            "type": detailed_data_types[column]
        }
        column_details.append(column_info)
    
    table_name = os.path.basename(filepath)
    metadata = {
        "name": table_name,
        "dimensions": dimensions,
        "columns": column_details,
    }

    fields = {
        "document_id": doc_id,  # document id from path
        "description_text": f"{describe_table(metadata)}",
        "metadata": metadata,
        "file_path": filepath,
        "table_name": table_name,
        "embedding": [0],
        "last_updated": int(time.time()),  # current time in long int
        "data_hash": "not implemented"
    }

    es.insert_document(fields, index="table_meta")
    insert_parent(filepath)
    os.remove(filepath)

def _picture(filepath):

    doc_id = str(uuid5(NAMESPACE_URL, filepath))
    image = Image.open(filepath)

    # Get basic metadata
    metadata = {
        'Format': image.format,
        'Size': image.size,
        'Date added': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    description = describe_picture(filepath)

    fields = {
        "document_id": doc_id,  # document id from path
        "description_text": description,
        "metadata": metadata,
        "file_path": filepath,
        "embedding": [0],
        "last_updated": int(time.time()),  # current time in long int
        "data_hash": "not implemented"
    }

    es.insert_document(fields, index="picture_meta")
    insert_parent(filepath)
    os.remove(filepath)

def _ppt(filepath, read_ppt=True, chunking_strategy="by_title"):
    
    doc_id = str(uuid5(NAMESPACE_URL, filepath))

    if read_ppt:  # read txt
        try:
            elements = partition_ppt(filepath, chunking_strategy=chunking_strategy)
        except Exception as e:
            logger.error(f"Failed to partition text: {e}")
            return

        if elements:
            for i, e in enumerate(elements):
                chunk = "".join(
                    ch for ch in e.text if unicodedata.category(ch)[0] != "C"
                )  # remove control characters

                fields = {
                    "document_id": doc_id,  # document id from path
                    "access_group": "",  # not yet implemented
                    "chunk_text": chunk,
                    "chunking_strategy": chunking_strategy,
                    'Date added': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "chunk_no": i,
                    "page_number" : e.metadata.page_number
                }
                
                es.insert_document(fields, index="text_chunk")

    else:
        fields = {
            "access_group": "",  # not yet implemented
            "description_text": "",  # not yet implemented
            "file_path": filepath,
            "embedding": [0],
            "last_updated": int(time.time()),  # current time in long int
            "data_hash": "not implemented"
        }

        es.insert_document(fields, index="document_meta")
    insert_parent(filepath)
    os.remove(filepath)

def _pptx(filepath, read_pptx=True, chunking_strategy="by_title"):
    
    doc_id = str(uuid5(NAMESPACE_URL, filepath))

    if read_pptx:  # read txt
        try:
            elements = partition_pptx(filepath, chunking_strategy=chunking_strategy)
        except Exception as e:
            logger.error(f"Failed to partition text: {e}")
            return

        if elements:
            for i, e in enumerate(elements):
                chunk = "".join(
                    ch for ch in e.text if unicodedata.category(ch)[0] != "C"
                )  # remove control characters

                fields = {
                    "document_id": doc_id,  # document id from path
                    "access_group": "",  # not yet implemented
                    "chunk_text": chunk,
                    "chunking_strategy": chunking_strategy,
                    'Date added': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "chunk_no": i,
                    "page_number" : e.metadata.page_number
                }
                
                es.insert_document(fields, index="text_chunk")

    else:
        fields = {
            "access_group": "",  # not yet implemented
            "description_text": "",  # not yet implemented
            "file_path": filepath,
            "embedding": [0],
            "last_updated": int(time.time()),  # current time in long int
            "data_hash": "not implemented"
        }

        es.insert_document(fields, index="document_meta")
    insert_parent(filepath)
    os.remove(filepath)
    

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

                es.insert_document(fields, index="table_meta")
                
                print("stored: " + file.split(".")[0])

"""
def get_next_version(model_name: str) -> int:
    client = MlflowClient()
    try:
        versions = client.get_latest_versions(model_name, stages=["None", "Staging", "Production"])
        if versions:
            latest_version = max([int(v.version) for v in versions])
            return latest_version + 1
        else:
            return 1
    except MlflowException as e:
        if "RESOURCE_DOES_NOT_EXIST" in str(e):
            client.create_registered_model(model_name)
            return 1
        else:
            raise

def add_model_to_mlflow(model_path):
    model_name = os.path.splitext(os.path.basename(model_path))[0]

    try:
        version = get_next_version(model_name)
        with mlflow.start_run():
            logger.info("Logging to MLflow.")
            mlflow.log_param("model_name", model_name)
            mlflow.log_param("model_version", version)
            mlflow.log_artifact(local_path=model_path, artifact_path="triton_models")
            mlflow.register_model(model_uri=f"runs:/{mlflow.active_run().info.run_id}/model", name=model_name)
    except Exception as e:
        logger.error(f"Failed to log to MLflow: {str(e)}")
"""

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
