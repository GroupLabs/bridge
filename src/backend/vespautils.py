import requests
import os
from io import BytesIO
import zipfile

from vespa.io import VespaQueryResponse
from vespa.application import Vespa

from log import setup_logger

logger = setup_logger("vespa")

VESPA_CONFIG_URL = "http://localhost:19071/"
VESPA_PREPAREANDACTIVATE_ENDP = VESPA_CONFIG_URL + "application/v2/tenant/default/prepareandactivate"
VESPA_FEED_URL = "http://localhost:8080/"
VESPA_QUERY_URL = "http://localhost:8082/"

vespa_feed = None
vespa_query = None

def get_vespa_feed():
    global vespa_feed
    if vespa_feed is None:
        vespa_feed = Vespa(url=VESPA_FEED_URL)
        logger.info("Initialized Vespa Feed.")
    return vespa_feed

def get_vespa_query():
    global vespa_query
    if vespa_query is None:
        vespa_query = Vespa(url=VESPA_QUERY_URL)
        logger.info("Initialized Vespa Query")
    return vespa_query

def upload_config(search_config_path):
    if not os.path.isdir(search_config_path):
        raise ValueError(f"The path {search_config_path} does not exist or is not a directory")

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
        for root, dirs, files in os.walk(search_config_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, search_config_path)
                zip_file.write(file_path, arcname)

    zip_buffer.seek(0)

    headers = {"Content-Type": "application/zip"}

    response = requests.post(VESPA_PREPAREANDACTIVATE_ENDP, headers=headers, data=zip_buffer)

    if response.status_code == 200:
        logger.info(f"Vespa Config Upload Successful: {response.text}")
    else:
        # should retry, or graceful exit api.
        logger.warn(f"Vespa Config Upload Failed ({response.status_code}): {response.text}")

def upload(schema: str, data_id: str, fields: dict, groupname: str = "all"):

    app = get_vespa_feed()

    app.feed_data_point(
        schema=schema,
        namespace="all",
        data_id=data_id,
        fields=fields,
        groupname=groupname
    )

    # logger.info("Upload fulfilled successfully.")

def query(
    query: str = None,
    yql: str = "select id,chunk_text from text_chunk where userQuery() or ({targetHits:10}nearestNeighbor(embedding,q))",
    ranking: str = "colbert"
    ):

    # eg yql
    # yql = f'select * from sources * where chunk_text contains "{query}"'
    # yql = 'select * from sources * where sddocname contains "text_chunk" limit 10;'

    response = vespa_query.query(
        yql=yql,
        groupname="all",
        ranking=ranking,
        query=query,
        body={
            "presentation.format.tensors": "short-value",
            "input.query(q)": f'embed(e5, "{query}")',
            "input.query(qt)": f'embed(colbert, "{query}")',
        },
    )
        
    if not response.is_successful():
        raise ValueError(f"Query failed with status code {response.status_code}, url={response.url} response={response.json}")
    
    # logger.info("Query fulfilled successfully.")

    return response.json

get_vespa_feed()
get_vespa_query()

if __name__ == "__main__":
    upload_config("./search-config")

    fields = {
        "id" : "a", 
        "document_id" : "ab", # document id from path
        "access_group" : "", # not yet implemented
        "chunk_text" : "Bridge is awesome",
        "chunking_strategy" : "none",
        "chunk_no" : 1,
        "last_updated" : 1, # current time in long int
        "e5" : [i for i in range(384)],
        "colbert" : {}
    }

    upload(schema="text_chunk", data_id="a", fields=fields)

    fields = {
        "id" : "b", 
        "document_id" : "abc", # document id from path
        "access_group" : "", # not yet implemented
        "chunk_text" : "Bridge is great",
        "chunking_strategy" : "none",
        "chunk_no" : 1,
        "last_updated" : 1, # current time in long int
        "e5" : [i+0.3 for i in range(384)],
        "colbert" : {}
    }

    upload(schema="text_chunk", data_id="b", fields=fields)

    fields = {
        "id" : "c", 
        "document_id" : "abcd", # document id from path
        "access_group" : "", # not yet implemented
        "chunk_text" : "Bridge is amazing",
        "chunking_strategy" : "none",
        "chunk_no" : 1,
        "last_updated" : 1, # current time in long int
        "e5" : [-i for i in range(384)],
        "colbert" : {}
    }

    upload(schema="text_chunk", data_id="c", fields=fields)

    query_str = "Bridge is awesome"

    # response = vespa_query.query(
    #     yql="select id,chunk_text from text_chunk where userQuery() or ({targetHits:10}nearestNeighbor(e5,q))",
    #     groupname="all",
    #     ranking="hybrid_search",
    #     query=query,
    #     body={
    #         "presentation.format.tensors": "short-value",
    #         "input.query(q)": [i for i in range(384)],
    #         "input.query(alpha)": 0.5,
    #     },
    # )

    # print(response.json)

    print()

    # response = vespa_query.query(
    #     body={
    #         "yql": 'select * from text_chunk where userQuery();',
    #         # "yql": 'select * from sources * where userQuery();', can be this if all .sd has same rank-profiles
    #         "hits": 10,
    #         "query": query_str
    #         "type": "any",
    #         "ranking": "default"
    #     }
    # )

    # print(response.json)


    # response = vespa_query.query(
    #     yql="select id,chunk_text from text_chunk where userQuery() or ({targetHits:10}nearestNeighbor(embedding,q))",
    #     groupname="all",
    #     ranking="hybrid_search",  # Use the correct rank profile
    #     query=query_str,
    #     body={
    #         "presentation.format.tensors": "short-value",
    #         "ranking.features.query(q)": f'embed(e5, "{query_str}")',
    #         "ranking.features.query(alpha)": 0.5,
    #     },
    # )

    response = vespa_query.query(
        yql= f'select * from sources * where chunk_text contains "{query_str}"',
        groupname="all",
    )
    
    print()

    print(response.json)
    # pass
