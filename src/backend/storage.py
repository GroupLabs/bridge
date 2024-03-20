import unicodedata
import os
import yaml
from uuid import uuid4, uuid5, NAMESPACE_URL
import time
from pathlib import Path
import sys

from celery import Celery

from unstructured.partition.pdf import partition_pdf
from postgres import postgres_to_yamls

from log import setup_logger
from typeutils import get_pathtype, parse_connection_string
from vespautils import upload_config, upload, query

VESPA_CONFIG_PATH = "./search-config"
CELERY_BROKER_URL = "amqp://guest:guest@localhost"

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

# vespa config
try:
    upload_config(VESPA_CONFIG_PATH)
except Exception as e:
    logger.critical(f"Failed to configure Vespa: {e}")
    sys.exit(1)

# def __len__(self) -> int:
#     return self.app.query(
#         yql="select * from sources * where true",
#         groupname="all"
#     ).number_documents_indexed

# def __repr__(self) -> str:
#     r = ""
#     r = r + "Search: \n"
#     r = r + f".... status: {self.app.get_application_status()}\n"
#     r = r + f".... storing {len(self)} value(s)"
#     return r

# def __del__(self):
#     pass

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
        # checks for illegal paths and returns type
        pathtype = get_pathtype(filepath)

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
        # elements = partition_pdf(input, strategy="fast", chunking_strategy="by_title")
        try:
            elements = partition_pdf(filepath, strategy="hi_res", chunking_strategy=chunking_strategy)
        except Exception as e:
            logger.error(f"Failed to parse PDF elements: {e}")

        for i, e in enumerate(elements):

            chunk = "".join(
                ch for ch in e.text if unicodedata.category(ch)[0] != "C"
            )  # remove control characters

            chunk_id = str(uuid4()) # random id

            fields = {
                "id" : chunk_id, 
                "document_id" : doc_id, # document id from path
                "access_group" : "", # not yet implemented
                "chunk_text" : chunk,
                "chunking_strategy" : chunking_strategy,
                "chunk_no" : i,
                # "embedding" : [0],
                "last_updated" : int(time.time()) # current time in long int
            }

            upload(schema="text_chunk", data_id=chunk_id, fields=fields)
    else:
        fields = {
            "id" : doc_id, 
            "access_group" : "", # not yet implemented
            "description_text" : "", # not yet implemented
            "file_path" : filepath,
            "embedding" : [0],
            "last_updated" : int(time.time()), # current time in long int
            "data_hash" : "not implemented"
        }

        upload(schema="document_meta", data_id=doc_id, fields=fields)


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
                    "id": table_id,
                    "database_id" : db_id,
                    "access_group" : "", # not yet implemented
                    "description_text" : data["description"], # not yet implemented
                    "embedding" : [0],
                    "correlation_embedding" : [0],
                    "last_updated" : int(time.time()), # current time in long int
                    "data_hash" : "not implemented"
                }

                upload(schema="table_meta", data_id=table_id, fields=fields)
                
                print("stored: " + file.split(".")[0])

if __name__ == "__main__":
    load_data("/Users/noelthomas/Desktop/Mistral 7B Paper.pdf", True)

    response = query("What is GQA?")
    print(response)

    # host="localhost"
    # user=os.getenv("PG_USER")
    # password=os.getenv("PG_PWD")

    # conn_str = f'postgres://{user}:{password}@{host}'

    # load_data(conn_str)

    # print(query("lepton"))
