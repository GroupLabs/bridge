from elasticsearch import Elasticsearch, BadRequestError

from config import config
from embed.e5_small import embed_passage, embed_query

# TODO: add logging

# TODO: add to config
ELASTIC_PASSWORD=config.ELASTIC_PASSWORD
ELASTIC_CA_CERT_PATH=config.ELASTIC_CA_CERT_PATH
ELASTIC_USER=config.ELASTIC_USER
ELASTIC_URL=config.ELASTIC_URL

class Search:
    def __init__(self):
        self.es = Elasticsearch(
            ELASTIC_URL,
            ca_certs=ELASTIC_CA_CERT_PATH,
            basic_auth=(ELASTIC_USER, ELASTIC_PASSWORD)
        )
        client_info = self.es.info()
        print('Connected to Elasticsearch!')
        # pprint(client_info.body)

        # configure text_chunk
        try:
            self.es.indices.create( # may fail if index exists
                index='text_chunk', 
                mappings={
                    'properties': {
                        # 'id': {'type': 'keyword'}, # auto created by es
                        'document_id': {'type': 'keyword'},
                        'access_group': {'type': 'keyword'},
                        'document_name': {'type': 'text'},
                        'chunk_text': {'type': 'text'},
                        'chunking_strategy': {'type': 'keyword'},
                        'chunk_no': {'type': 'integer'},
                        # 'last_updated': {'type': 'date'}, # auto created by es
                        'e5': {'type': 'dense_vector'},
                        'colbert': {'type': 'object', 'enabled': False}  # disable indexing for the 'colbert' field
                    }
                })
        except BadRequestError as e:
            # TODO: should be logged
            if e.error != "resource_already_exists_exception" or e.status_code != 400:
                raise
        
        # configure table_meta
        try:
            self.es.indices.create( # may fail if index exists
                index='table_meta', 
                mappings={
                    'properties': {
                        # 'id': {'type': 'keyword'}, # auto created by es
                        'database_id': {'type': 'keyword'},
                        'access_group': {'type': 'keyword'},
                        'table_name': {'type': 'text'},
                        'description_text': {'type': 'text'},
                        'chunking_strategy': {'type': 'keyword'},
                        'chunk_no': {'type': 'integer'},
                        'data_hash': {'type': 'keyword'},
                        # 'last_updated': {'type': 'date'}, # auto created by es
                        'e5': {'type': 'dense_vector'},
                        'correlation_embedding': {'type': 'dense_vector'},
                        'colbert': {'type': 'object', 'enabled': False}  # disable indexing for the 'colbert' field
                    }
                })
        except BadRequestError as e:
            # TODO: should be logged
            if e.error != "resource_already_exists_exception" or e.status_code != 400:
                raise

        self.registered_indices = [
            "text_chunk"
        ]

    def __repr__(self):
        r = ""
        r = r + "Search: \n"
        r = r + f".... status: {'HEALTHY' if self.es.ping() else 'DISCONNECTED'}\n"
        for idx in self.registered_indices:
            r = r + f".... [{idx}] storing {self.es.count(index=idx)['count']} value(s)"
        return r
    
    # load ops
    def insert_document(self, document: any, index: str):

        # add embeddings
        if index == "text_chunk":
            document['e5'] = embed_passage(document['chunk_text']).tolist()[0]
            document['colbert'] = {}

        if index == "table_meta":
            document['e5'] = embed_passage(document['description_text']).tolist()[0]
            document['colbert'] = {}
            # correlation embeddings are handled at storage

        return self.es.index(index=index, body=document)

    def insert_documents(self, documents: any, index: str):
        operations = []
        for document in documents:
            operations.append({'index': {'_index': index}})
            operations.append(document)
        return self.es.bulk(operations=operations)

    # query ops
    def search(self, index: str, **query_args):
        return self.es.search(index=index, **query_args)

    def retrieve_document_by_id(self, id, index):
        return self.es.get(index=index, id=id)
    
    def hybrid_search(self, query: str, index: str):
        match_response = self.es.search(
            query={
                'match': {
                    'title': {
                        'query': query
                    }
                }
            },
            index=index
        )

        match_results = match_response['hits']['hits']

        knn_response = self.es.search(
            knn={
                'field': 'e5',
                'query_vector': embed_query(query).tolist()[0],
                'k': 10,
                'num_candidates': 50
            },
            index=index
        )

        knn_results = knn_response['hits']['hits']

        # rrf
        combined_results = {}
        k = 60

        for rank, result in enumerate(match_results, 1):
            combined_results[result['_id']] = 1 / (k + rank)

        for rank, result in enumerate(knn_results, 1):
            combined_results[result['_id']] = combined_results.get(result['_id'], 0) + 1 / (k + rank)

        sorted_results = sorted(combined_results.items(), key=lambda item: item[1], reverse=True)

        return sorted_results

if __name__ == "__main__":
    from pprint import pprint
    
    es = Search()

    # # es.es.indices.delete(index="test")

    # document = {
    #     # "id" : "a",
    #     "document_id" : "ab", # document id from path
    #     "access_group" : "", # not yet implemented
    #     "title" : "", # not yet implemented
    #     "chunk_text" : "Bridge is awesome",
    #     "chunking_strategy" : "none",
    #     "chunk_no" : 1,
    #     # "last_updated" : 1, # current time in long int
    #     # "e5" : embed_passage("Bridge is awesome").tolist()[0],
    #     # "colbert" : {}
    # }

    # resp = es.insert_document(document, "test")

    # print()
    # pprint(resp)

    # resp = es.retrieve_document_by_id(
    #     resp['_id'],
    #     index='test'
    # )

    # print()
    # pprint(resp)

    # resp = es.search(
    #     query={
    #         'match': {
    #             'chunk_text': {
    #                 'query': 'Bridge'
    #             }
    #         }
    #     },
    #     index='test'
    # )

    # print()
    # pprint(resp['hits'])

    # print()
    # pprint(es.es.indices.get_mapping(index='test')["test"])

    # resp = es.search(
    #     # query={
    #     #     'match': {
    #     #         'title': {
    #     #             'query': 'describe bridge'
    #     #         }
    #     #     }
    #     # },
    #     knn={
    #         'field': 'e5',
    #         'query_vector': embed_query("describe bridge").tolist()[0],
    #         'k': 10,
    #         'num_candidates': 50
    #     },
    #     # rank={
    #     #     'rrf': {}
    #     # },
    #     index='test'
    # )

    # print()
    # pprint(resp['hits'])

    print(es)

    # print(es.retrieve_document_by_id("iI78g44BIew1j5poztvp", "text_chunk"))

