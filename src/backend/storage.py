import hashlib
import unicodedata
import os
import yaml

from vespa.io import VespaQueryResponse
from vespa.application import Vespa

from celery import Celery

from unstructured.partition.pdf import partition_pdf

from log import setup_logger
from typeutils import get_pathtype

VESPA_URL = "http://localhost:8080/"
CELERY_BROKER_URL = "amqp://guest:guest@localhost"

logger = setup_logger("storage")

celery_app = Celery(
    "worker",
    broker=CELERY_BROKER_URL,  # Default RabbitMQ credentials
    backend="rpc://",  # Use RPC as the backend with RabbitMQ
)

# Optional: Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],  # Ignore other content
    result_serializer='json',
    timezone='Europe/London',
    enable_utc=True,
)

vespa_app = None

def get_vespa_app():
    global vespa_app
    if vespa_app is None:
        vespa_app = Vespa(url=VESPA_URL)
        logger.info("Initialized Vespa.")
    return vespa_app

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

def query(
    query: str,
    yql: str = "select id, url, title, page, chunkno, authors, text from chunk where userQuery() or ({targetHits:20}nearestNeighbor(embedding,q))",
    hits: int = 3,
    ranking: str = "colbert",
    groupname: str = "all"
):
    app = get_vespa_app()
    response:VespaQueryResponse = app.query(
        yql=yql,
        groupname=groupname,
        ranking=ranking,
        query=query,
        hits = hits,
        body={
            "presentation.format.tensors": "short-value",
            "input.query(q)": f"embed(e5, \"query: {query} \")",
            "input.query(qt)": f"embed(colbert, \"query: {query} \")"
        }
    )
    if not response.is_successful():
        raise ValueError(f"Query failed with status code {response.status_code}, url={response.url} response={response.json}")
    
    logger.info("Query fulfilled successfully.")

    return response

@celery_app.task(name="load_data_task")
def load_data(filepath: str):    
    # checks for illegal paths and returns type
    pathtype = get_pathtype(filepath)

    # unstructured
    if pathtype == "pdf":
        _pdf(filepath)

    elif pathtype == "txt":
        pass

    # structured
    elif pathtype == "dir":
        # os.walkdir

        # check if database yamls
        if os.path.basename(filepath) == "noelthomas":
            _db()
    else:
        logger.warning("unsupported filetype encountered.")
        raise NotImplementedError(f"File ({pathtype}) type is not supported.")
    
    logger.info(f"Loading data from {pathtype}")

    return pathtype
    
def _upload(schema: str, data_id: str, fields: dict, groupname: str = "all"):

    app = get_vespa_app()

    app.feed_data_point(
        schema=schema,
        namespace="all",
        data_id=data_id,
        fields=fields,
        groupname=groupname
    )

def _pdf(filepath):
    # assume schema exists

    # elements = partition_pdf(input, strategy="fast", chunking_strategy="by_title")
    elements = partition_pdf(filepath, strategy="hi_res", chunking_strategy="by_title")

    for i, e in enumerate(elements):
        vespa_id = f"{e.metadata.to_dict()['filename']}#{e.metadata.to_dict()['page_number']}#{i}"
        hash_value = hashlib.sha1(vespa_id.encode()).hexdigest()  # hash of id

        chunk = "".join(
            ch for ch in e.text if unicodedata.category(ch)[0] != "C"
        )  # remove control characters

        fields = {
            "title": e.metadata.filename,
            "url": "",
            "page": 0,
            "id": hash_value,
            "authors": [],
            "chunkno": i,
            "text": chunk,
        }

        _upload(schema="chunk", data_id=hash_value, fields=fields)

    return

def _db():
    node_name = "noelthomas"

    data = {}

    for i, file in enumerate(os.listdir(node_name)):
        filepath = os.path.join(node_name, file)
        if file.endswith('.yaml') and os.path.isfile(filepath):
            with open(filepath, 'r') as f:
                data = yaml.safe_load(f)

                vespa_id = f"{os.path.basename(filepath)}#{i}"
                hash_value = hashlib.sha1(vespa_id.encode()).hexdigest()

                fields = {
                    "title": node_name,
                    "url": "",
                    "page": 0,
                    "id": hash_value,
                    "authors": [],
                    "chunkno": i,
                    "text": data[os.path.basename(filepath).split(".")[0]]["semantic_context"],
                }

                _upload(schema="chunk", data_id=hash_value, fields=fields)
                
                print("stored: " + file.split(".")[0])

if __name__ == "__main__":
    load_data("noelthomas")
