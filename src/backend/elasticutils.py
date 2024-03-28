import json
from pprint import pprint
import os
import time

from dotenv import load_dotenv
from elasticsearch import Elasticsearch, BadRequestError

from e5_small import embed_passage, embed_query

# TODO: add logging

load_dotenv()

ELASTIC_PASSWORD="v4Ci+biLJxCFS=s5arr1"
ELASTIC_CA_CERT_PATH="/Users/noelthomas/Documents/GitHub/Bridge/http_ca.crt"
ELASTIC_USER="elastic"
ELASTIC_URL="https://localhost:9200"

class Search:
    def __init__(self):
        self.es = Elasticsearch(
            ELASTIC_URL,
            ca_certs=ELASTIC_CA_CERT_PATH,
            basic_auth=(ELASTIC_USER, ELASTIC_PASSWORD)
        )
        client_info = self.es.info()
        print('Connected to Elasticsearch!')
        pprint(client_info.body)

        # configure
        try:
            self.es.indices.create( # may fail if index exists
                index='text_chunk', 
                mappings={
                    'properties': {
                        # 'id': {'type': 'keyword'}, # auto created by es
                        'document_id': {'type': 'keyword'},
                        'access_group': {'type': 'keyword'},
                        'title': {'type': 'text'},
                        'chunk_text': {'type': 'text'},
                        'chunking_strategy': {'type': 'keyword'},
                        'chunk_no': {'type': 'integer'},
                        # 'last_updated': {'type': 'date'}, # auto created by es
                        'e5': {'type': 'dense_vector'},
                        'colbert': {'type': 'object', 'enabled': False}  # Disable indexing for the 'colbert' field
                    }
                })
        except BadRequestError as e:
            # TODO: should be logged
            if e.error != "resource_already_exists_exception" or e.status_code != 400:
                raise

    # load
    def insert_document(self, document: any, index: str):

        # adding embeddings
        if index == "text_chunk":
            document['e5'] = embed_passage(document['chunk_text']).tolist()[0]
            document['colbert'] = {}

        return self.es.index(index=index, body=document)

    def insert_documents(self, documents: any, index: str):
        operations = []
        for document in documents:
            operations.append({'index': {'_index': index}})
            operations.append(document)
        return self.es.bulk(operations=operations)

    # query
    def search(self, index: str, **query_args):
        return self.es.search(index=index, **query_args)

    def retrieve_document_by_id(self, id, index):
        return self.es.get(index=index, id=id)


if __name__ == "__main__":
    
    es = Search()

    # es.es.indices.delete(index="test")

    document = {
        # "id" : "a",
        "document_id" : "ab", # document id from path
        "access_group" : "", # not yet implemented
        "title" : "", # not yet implemented
        "chunk_text" : "Bridge is awesome",
        "chunking_strategy" : "none",
        "chunk_no" : 1,
        # "last_updated" : 1, # current time in long int
        # "e5" : embed_passage("Bridge is awesome").tolist()[0],
        # "colbert" : {}
    }

    resp = es.insert_document(document, "test")

    print()
    pprint(resp)

    resp = es.retrieve_document_by_id(
        resp['_id'],
        index='test'
    )

    print()
    pprint(resp)

    resp = es.search(
        query={
            'match': {
                'chunk_text': {
                    'query': 'Bridge'
                }
            }
        },
        index='test'
    )

    print()
    pprint(resp['hits'])

    print()
    pprint(es.es.indices.get_mapping(index='test')["test"])

    resp = es.search(
        # query={
        #     'match': {
        #         'title': {
        #             'query': 'describe bridge'
        #         }
        #     }
        # },
        knn={
            'field': 'e5',
            'query_vector': embed_query("describe bridge").tolist()[0],
            'k': 10,
            'num_candidates': 50
        },
        # rank={
        #     'rrf': {}
        # },
        index='test'
    )

    print()
    pprint(resp['hits'])

