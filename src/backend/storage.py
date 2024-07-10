import unicodedata
import os
import yaml
from uuid import uuid5, NAMESPACE_URL
import re
from pathlib import Path

from celery import Celery

from unstructured.partition.pdf import partition_pdf # pikapdf dependency is not fork safe, can we remove this dep?

from connect.postgres import postgres_to_yamls
from config import config
from log import setup_logger
from typeutils import get_pathtype, parse_connection_string
from elasticutils import Search
from tritonutils import TritonClient

import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="celery.platforms")

CELERY_BROKER_URL = config.CELERY_BROKER_URL

# logger
logger = setup_logger("storage")

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

@celery_app.task(name="load_data_task", bind=True)
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
            pass

        # mix
        elif pathtype == "dir":
            # recursively call load_data
            pass

        else:
            logger.warning("unsupported filetype encountered.")
            raise NotImplementedError(f"File ({pathtype}) type is not supported.")
    
    if os.path.exists(filepath): # remove tempfile, not needed if we don't create the temp file
            os.remove(filepath)

def _retrieve_all_objects(index: str):
    response = es.retrieve_all_objects(index)
    return response

def retrieve_object_ids(index: str):
    result = es.retrieve_object_ids(index)

    unique_docs = result['aggregations']['unique_docs']['buckets']
    doc_tuples = [(bucket['key']['document_id'], bucket['key']['document_name'], bucket['doc_count']) for bucket in unique_docs]

    return doc_tuples

def query(q: str, index: str, doc_id: str = None):
    return es.hybrid_search(q, index, doc_id)

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

            pdf_file.close()
    else:
        raise PermissionError('File is not readable.')
    
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
