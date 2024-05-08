import unicodedata
import os
import yaml
from uuid import uuid4, uuid5, NAMESPACE_URL
import time
from pathlib import Path

from celery import Celery

from unstructured.partition.pdf import partition_pdf

from connect.postgres import postgres_to_yamls
from config import config
from log import setup_logger
from typeutils import get_pathtype, parse_connection_string
from elasticutils import Search
from tritonutils import TritonClient

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
    task_serializer='json',
    accept_content=['json'],  # Ignore other content
    result_serializer='json',
    timezone='Europe/London',
    enable_utc=True,
)

# elasticsearch
es = Search()

# triton server
tc = TritonClient()

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

@celery_app.task(name="load_model_task")
def load_model(model, config):
    # load to triton
    tc.addToModels(model,config)

    # load to ES
    fields = {
        "model_id" : uuid4(),
        "access_group" : "", # not yet implemented
        "model_name" : model,
        "description_text" : "This is the model description.",
        "chunking_strategy" : "", # not chunked rn
        "chunking_no" : "", # not chunked rn
        "model_hash" : "not implemented", # for integrity check
    }

    es.insert_document(fields, index="model_meta")

    # TODO remove temp models

def query(q: str, index: str):
    return es.hybrid_search(q, index)

def _pdf(filepath, read_pdf=True, chunking_strategy="by_title"):
    
    doc_id = str(uuid5(NAMESPACE_URL, filepath))

    if read_pdf: # read pdf
        # elements = partition(input, strategy="fast", chunking_strategy="by_title")

        elements = None
        try:
            elements = partition_pdf(filepath, strategy="hi_res", chunking_strategy=chunking_strategy)
        except Exception as e:
            logger.error(f"Failed to parse PDF elements: {e}")

        if elements is not None:
            for i, e in enumerate(elements):

                chunk = "".join(
                    ch for ch in e.text if unicodedata.category(ch)[0] != "C"
                )  # remove control characters

                fields = {
                    "document_id" : doc_id, # document id from path
                    "access_group" : "", # not yet implemented
                    "chunk_text" : chunk,
                    "chunking_strategy" : chunking_strategy,
                    "chunk_no" : i,
                }

                es.insert_document(fields, index="text_chunk")
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
