import unicodedata
import os
import yaml
from uuid import uuid4, uuid5, NAMESPACE_URL
import time
from pathlib import Path
import sys

from celery import Celery

from unstructured.partition.pdf import partition_pdf

from connect.postgres import postgres_to_yamls
from log import setup_logger
from typeutils import get_pathtype, parse_connection_string
from elasticutils import Search

CELERY_BROKER_URL = "amqp://guest:guest@localhost"

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


def _db(db_type, host, user, password):
    # figure out which db connector to use
    if db_type == "postgres":
        postgres_to_yamls(host, user, password)
    else:
        raise NotImplementedError

    node_name = f"models/{db_type}/yamls" # should be turned to path object
    db_id = str(uuid5(NAMESPACE_URL, node_name))

    data = {}

    for i, file in enumerate(os.listdir(node_name)):
        filepath = os.path.join(node_name, file)
        if file.endswith('.yaml') and os.path.isfile(filepath):
            with open(filepath, 'r') as f:
                data = yaml.safe_load(f)

                table_id = str(uuid4())

                fields = {
                    "database_id" : db_id,
                    "access_group" : "", # not yet implemented
                    "description_text" : data["description"], # not yet implemented
                    "data_hash" : "not implemented" # for integrity check
                }

                es.insert_document(fields, index="table_meta")
                
                print("stored: " + file.split(".")[0])

if __name__ == "__main__":
    # load_data("/Users/noelthomas/Desktop/Mistral 7B Paper.pdf", True)

    response = es.search(
        # query={
        #     'match': {
        #         'title': {
        #             'query': 'describe bridge'
        #         }
        #     }
        # },
        knn={
            'field': 'e5',
            'query_vector': embed_query("what is GQA?").tolist()[0],
            'k': 10,
            'num_candidates': 50
        },
        # rank={
        #     'rrf': {}
        # },
        index='text_chunk'
    )

    print(response)
    print()
    print()


    response = es.hybrid_search("What is GQA?", "text_chunk")

    print()
    print()
    print()
    print()
    print()
    print(response)

    

    # host="localhost"
    # user=os.getenv("PG_USER")
    # password=os.getenv("PG_PWD")

    # conn_str = f'postgres://{user}:{password}@{host}'

    # load_data(conn_str)

    # print(query("lepton"))
