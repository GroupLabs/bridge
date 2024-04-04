from elasticsearch import Elasticsearch, BadRequestError

from config import config
from log import setup_logger
from embed.e5_small import embed_passage, embed_query

# logger
logger = setup_logger("elastic")

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
        logger.info("Connected.")
        logger.info(str(client_info))

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
            if e.error != "resource_already_exists_exception" or e.status_code != 400:
                logger.warn(e.error)
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
                        "correlation_embedding": {
                            "type": "nested",
                            "properties": {
                                "key": {"type": "keyword"},
                            }
                        },
                        'colbert': {'type': 'object', 'enabled': False}  # disable indexing for the 'colbert' field
                    }
                })
        except BadRequestError as e:
            if e.error != "resource_already_exists_exception" or e.status_code != 400:
                logger.warn(e.error)
                raise

        logger.info("Configured.")

        self.registered_indices = [
            "text_chunk",
            "table_meta"
        ]

        logger.info("Indices Registered.")

    def __repr__(self):
        r = ""
        r = r + "Search: \n"
        r = r + f".... status: {'HEALTHY' if self.es.ping() else 'DISCONNECTED'}"
        for idx in self.registered_indices:
            r = r + f"\n.... [{idx}] storing {self.es.count(index=idx)['count']} value(s)"
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

        logger.info("Inserting document.")

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
        # Determine the field to use based on the index
        # TODO: make this better so it can be set up once
        _field = 'description_text' if index == 'table_meta' else 'chunk_text' if index == 'text_chunk' else None

        if _field is None:
            raise NotImplementedError

        # Use _field in the match query and to specify the _source fields to fetch
        match_response = self.es.search(
            query={
                'match': {
                    _field: query
                }
            },
            _source=[_field],  # Correctly fetch the specific field
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
            _source=[_field],  # Correctly fetch the specific field
            index=index
        )

        knn_results = knn_response['hits']['hits']

        # rrf
        combined_results = {}
        k = 60

        for rank, result in enumerate(match_results, 1):
            combined_results[result['_id']] = {
                "score": 1 / (k + rank),
                "text": result["_source"].get(_field, '')
            }

        for rank, result in enumerate(knn_results, 1):
            if result['_id'] in combined_results:
                combined_results[result['_id']]["score"] += 1 / (k + rank)
            else:
                combined_results[result['_id']] = {
                    "score": 1 / (k + rank),
                    "text": result["_source"].get(_field, '')
                }

        sorted_results = sorted(combined_results.items(), key=lambda item: item[1]['score'], reverse=True)

        logger.info(f"Hybrid search returned {len(sorted_results)} elements.")

        return sorted_results


if __name__ == "__main__":
    from pprint import pprint
    
    es = Search()

    response = es.hybrid_search("What is sliding GQA?", "text_chunk")

    # response = es.search(
    #     index="text_chunk",
    #     query={
    #         "match": {"title": "What is GQA?"}
    #     },
    #     _source=["_id", "chunk_text"]  # Fetch only these fields
    # )


    # # es.es.indices.delete(index="test")
    

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

