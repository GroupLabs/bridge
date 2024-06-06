from typing import List
from elasticsearch import Elasticsearch, BadRequestError

from config import config
from log import setup_logger
from embed.e5_small import embed_passage, embed_query
from datetime import datetime


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
        logger.info("ES is available")
        logger.info(str(client_info))


        try:
            self.es.indices.create( # may fail if index exists
                index='file_meta', 
                mappings={
                    'properties': {
                        'user_id': {'type': 'keyword'},
                        'file_type': {'type': 'keyword'},
                        'file_id': {'type': 'keyword'},
                        'file_name': {'type': 'text'},
                        'file_description': {'type': 'text'},
                        'file_size': {'type': 'long'},
                        'permissions': {
                            'type': 'nested',
                            'properties': {
                                'person': {'type': 'keyword'},
                                'permission': {'type': 'keyword'}
                            }
                        },
                        'last_modified_time': {'type': 'date'},
                        'created_time': {'type': 'date'}
                    }
                })
        except BadRequestError as e:
            if e.error != "resource_already_exists_exception" or e.status_code != 400:
                logger.warn(e.error)
                raise

        # configure text_chunk
        try:
            self.es.indices.create( # may fail if index exists
                index='text_chunk', 
                mappings={
                    'properties': {
                        'user_id': {'type': 'keyword'},
                        'main_doc_id': {'type': 'keyword'},
                        'chunk_id': {'type': 'keyword'}, # TODO: Should this be murmur? check the available types
                        'access_group': {'type': 'keyword'},
                        'document_name': {'type': 'text'},
                        'chunk_text': {'type': 'text'},
                        'chunking_strategy': {'type': 'keyword'},
                        'chunk_no': {'type': 'integer'},
                        # embeddings
                        'e5': {
                            'type': 'dense_vector',
                            # 'dim': 'not set',
                            'similarity': 'cosine'
                            },
                        'colbert': {'type': 'object', 'enabled': False}  # disable indexing for the 'colbert' field
                        
                    }
                })
        except BadRequestError as e:
            if e.error != "resource_already_exists_exception" or e.status_code != 400:
                logger.warn(e.error)
                raise

        # configure parent_doc
        try:
            self.es.indices.create( # may fail if index exists
                index='parent_doc', 
                mappings={
                    'properties': {
                        'document_id': {'type': 'keyword'}, # TODO: Should this be murmur? check the available types
                        'document_name': {
                            'type': 'text',
                            'fields': {
                                'keyword': {
                                    'type': 'keyword',
                                    'ignore_above': 256
                                }
                            }
                        },
                        'Size': {'type': 'text'},
                        'Size_numeric': {'type': 'float'},  # Add Size_numeric for sorting
                        'Type': {'type': 'keyword'},
                        'Last_modified': {'type': 'text'},
                        'Created': {'type': 'date'},
                        # embeddings
                        'e5': {
                            'type': 'dense_vector',
                            # 'dim': 'not set',
                            'similarity': 'cosine'
                            },
                        'colbert': {'type': 'object', 'enabled': False}  # disable indexing for the 'colbert' field
                        
                    }
                })
        except BadRequestError as e:
            if e.error != "resource_already_exists_exception" or e.status_code != 400:
                logger.warn(e.error)
                raise


        # configure picture_meta
        try:
            self.es.indices.create( # may fail if index exists
                index='picture_meta', 
                mappings={
                    'properties': {
                        'user_id': {'type': 'keyword'},
                        'picture_name': {'type': 'keyword'},
                        'access_group': {'type': 'keyword'},
                        'description_text': {'type': 'text'},
                        'time_added': {'type': 'text'},

                        # embeddings
                        'e5': {
                            'type': 'dense_vector',
                            # 'dim': 'not set',
                            'similarity': 'cosine'
                            },
                        'colbert': {'type': 'object', 'enabled': False} # disable indexing for the 'colbert' field
                        # meta
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
                        'user_id': {'type': 'keyword'},
                        'database_id': {'type': 'keyword'},
                        'access_group': {'type': 'keyword'},
                        'table_name': {'type': 'text'},
                        'description_text': {'type': 'text'},
                        'chunking_strategy': {'type': 'keyword'},
                        'chunk_no': {'type': 'integer'},
                        'table_hash': {'type': 'keyword'},
                        # embeddings
                        'e5': {
                            'type': 'dense_vector',
                            # 'dim': 'not set',
                            'similarity': 'cosine'
                            },
                        "correlation_embedding": {
                            "type": "nested",
                            "properties": {
                                "key": {"type": "keyword"},
                            }
                        },
                        'colbert': {'type': 'object', 'enabled': False} # disable indexing for the 'colbert' field
                        # meta
                    }
                })
        except BadRequestError as e:
            if e.error != "resource_already_exists_exception" or e.status_code != 400:
                logger.warn(e.error)
                raise

        # configure model_meta
        try:
            self.es.indices.create( # may fail if index exists
                index='model_meta', 
                mappings={
                    'properties': {
                        'model_id': {'type': 'keyword'},
                        'access_group': {'type': 'keyword'},
                        'model_name': {'type': 'text'},
                        'description_text': {'type': 'text'},
                        'chunking_strategy': {'type': 'keyword'},
                        'model_hash': {'type': 'keyword'},
                        # embeddings
                        'e5': {
                            'type': 'dense_vector',
                            # 'dim': 'not set',
                            'similarity': 'cosine'
                            },
                        "correlation_embedding": {
                            "type": "nested",
                            "properties": {
                                "key": {"type": "keyword"},
                            }
                        },
                        'colbert': {'type': 'object', 'enabled': False},  # disable indexing for the 'colbert' field
                        # meta
                        'input_features': {
                            'type': 'nested',  # Use nested to support future complexity
                            'properties': {
                                'feature_name': {'type': 'keyword'},
                                'feature_type': {'type': 'keyword'},  # e.g., categorical, numerical, etc.
                                'encoding': {
                                    'type': 'keyword',  # Store encoding types like 'one-hot', 'label', 'binary', etc.
                                    'null_value': 'none'  # Default to 'none' if no encoding is used
                                }
                            }
                        }
                    }
                })
        except BadRequestError as e:
            if e.error != "resource_already_exists_exception" or e.status_code != 400:
                logger.warn(e.error)
                raise

        try:
            self.es.indices.create( # may fail if index exists
                index='chat_history',
                mappings={
                    'properties': {
                        'user_id': {'type': 'keyword'},
                        'history_id': {'type': 'keyword'},
                        'queries': {'type': 'text'},
                        'responses': {'type': 'text'},
                        'title': {'type': 'text'}
                    }
                })
        except BadRequestError as e:
            if e.error != "resource_already_exists_exception" or e.status_code != 400:
                logger.warn(e.error)
                raise

        try:
            self.es.indices.create( # may fail if index exists
                index='db_meta', 
                mappings={
                    'properties': {
                        "db_type": {'type': 'keyword'},
                        'connection_id': {'type': 'keyword'},
                        'host': {'type': 'keyword'},
                        'password': {'type': 'keyword'},
                        'user': {'type': 'keyword'},
                        'connection_string': {'type': 'keyword'}
                    }
                })
        except BadRequestError as e:
            if e.error != "resource_already_exists_exception" or e.status_code != 400:
                logger.warn(e.error)
                raise
        
        logger.info("Configured.")

        self.registered_indices = [
            "text_chunk",
            "table_meta",
            "model_meta",
            "file_meta",
            "chat_history"
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
            #document['e5'] = [0.0,0.0,0.1]
            document['colbert'] = {}

        if index == "table_meta":
            document['e5'] = embed_passage(document['description_text']).tolist()[0]
            #document['e5'] = [0.0,0.0,0.1]
            document['colbert'] = {}
            # correlation embeddings are handled at storage

        if index == "model_meta":
            document['e5'] = embed_passage(document['description_text']).tolist()[0]
            document['colbert'] = {}


        if index == "picture_meta":
            document['e5'] = embed_passage(document['description_text']).tolist()[0]
            #document['e5'] = [0.0,0.0,0.1]
            document['colbert'] = {}
            # correlation embeddings are handled at storage
            
        if index == "file_meta":
            document['created_time'] = datetime.utcfromtimestamp(document['created_time']).isoformat()
            document['last_modified_time'] = datetime.utcfromtimestamp(document['last_modified_time']).isoformat()
        
        logger.info("Inserting document.")

        return self.es.index(index=index, body=document)

    def insert_documents(self, documents: any, index: str):
        operations = []
        for document in documents:
            operations.append({'index': {'_index': index}})
            operations.append(document)
        return self.es.bulk(operations=operations)

    # query ops
    def retrieve_document_by_id(self, id, index):
        return self.es.get(index=index, id=id)

    def search(self, index: str, **query_args):
        return self.es.search(index=index, **query_args)

    def _rrf(self, result_sets_with_rankings, weights, field, k=60, normalize=False, INSPECT=False):
        combined_results = {}

        # Process each result set and apply reciprocal rank formula
        for result_set, results in result_sets_with_rankings.items():
            weight = weights[result_set]
            for rank, result in enumerate(results, 1):
                _id = result['_id']
                if _id in combined_results:
                    combined_results[_id]["score"] += weight / (k + rank)
                else:
                    combined_results[_id] = {
                        "score": weight / (k + rank),
                        "text": result["_source"].get(field, '')
                    }

        # Sort results by score in descending order
        sorted_results = sorted(combined_results.items(), key=lambda item: item[1]['score'], reverse=True)

        # Optionally normalize scores
        if normalize:
            min_score = min(result["score"] for _, result in sorted_results)
            max_score = max(result["score"] for _, result in sorted_results)
            for _, result in sorted_results:
                result["normalized_score"] = (result["score"] - min_score) / (max_score - min_score) if max_score > min_score else 0

        # Optionally inspect final results
        if INSPECT:
            print("FINAL")
            for _id, res in sorted_results:
                print(f"ID: {_id}, Score: {res['score']:.6f}, Snippet: {res['text'][:100]}...")

        return sorted_results
    
    def hybrid_search(self, query: str, index: str):
        INSPECT = False

        # Determine the field to use based on the index
        # TODO: make this better so it can be set up once
        if index == 'text_chunk':
            _field = "chunk_text"
        elif index == 'table_meta':
            _field = "description_text"
        elif index == 'model_meta':
            _field = "description_text"
        elif index == 'picture_meta':
            _field = "description_text"
        else:
            raise NotImplementedError

        match_response = self.es.search(
            query={
                'match': {
                    _field: query
                }
            },
            _source=[_field],
            index=index
        )

        if INSPECT:
            print("MATCH")
            for hit in match_response['hits']['hits']:
                # Print the ID, score, and a snippet of the description_text for each hits
                print(f"ID: {hit['_id']}, Score: {hit['_score']}, Snippet: {hit['_source']['chunk_text'][:100]}...")


        match_results = match_response['hits']['hits']
        if len(match_results) == 0:
            return
        # TODO: knn tuning | https://www.elastic.co/guide/en/elasticsearch/reference/current/knn-search.html#tune-approximate-knn-for-speed-accuracy
        knn_response = self.es.search(
            knn={
                'field': 'e5',
                'query_vector': embed_query(query).tolist()[0],
                #'query_vector': [0.0, 0.0, 0.1],
                'k': 10,
                'num_candidates': 50
            },
            _source=[_field],
            index=index
        )
        if INSPECT:
            print("KNN")
            for hit in knn_response['hits']['hits']:
                # Print the ID, score, and a snippet of the description_text for each hits
                print(f"ID: {hit['_id']}, Score: {hit['_score']}, Snippet: {hit['_source']['chunk_text'][:100]}...")

        knn_results = knn_response['hits']['hits']

        # (result set, weight)
        result_sets_with_rankings = {
            "match" : match_results,
            "knn" : knn_results
        }

        # tuning between result_sets
        weights = {
            "match": 1.0,
            "knn": 1.0
        }

        rrf_results = self._rrf(result_sets_with_rankings, weights, _field, INSPECT=INSPECT)

        logger.info(f"Hybrid search returned {len(rrf_results)} elements.")

        return rrf_results

    def save_chat_to_history(self, history_id: int, query: str, response: str, user_id: str):
        try:
            # Search for documents matching both history_id and user_id
            res = self.es.search(index='chat_history', query={
                'bool': {
                    'must': [
                        {'match': {'history_id': history_id}},
                        {'match': {'user_id': user_id}}
                    ]
                }
            })

            # Check if there are any hits
            if res['hits']['total']['value'] > 0:
                doc_id = res['hits']['hits'][0]['_id']
                chat_history = res['hits']['hits'][0]['_source']
                chat_history['queries'].append(query)
                chat_history['responses'].append(response)
                self.es.update(index='chat_history', id=doc_id, body={"doc": chat_history})
            else:
                chat_history = {
                    'user_id': user_id,
                    'history_id': history_id,
                    'queries': [query],
                    'responses': [response],
                    'title': f"Chat History {user_id} - {history_id}"
                }
                self.es.index(index='chat_history', body=chat_history)

            logger.info(f"Chat history {history_id} for user {user_id} updated successfully.")
        except Exception as e:
            logger.error(f"Error saving chat history: {str(e)}")

    def get_user_chat_histories(self, user_id: str) -> List[int]:
        try:
            response = self.es.search(index='chat_history', query={
                'match': {'user_id': user_id}
            })

            if response['hits']['total']['value'] > 0:
                chat_history_ids = [hit['_source']['history_id'] for hit in response['hits']['hits']]
                return chat_history_ids
            else:
                return []
        except Exception as e:
            logger.error(f"Error retrieving chat histories for user {user_id}: {str(e)}")
            return []
        
    def add_connection(self, db_type: str=None, host: str=None, user: str=None, password: str=None, connection_id: str=None, connection_string: str = None):
        logger.info("received db_info")
        document = {
            'db_type': db_type,
            'host': host,
            'user': user,
            'password': password,
            "connection_id": connection_id,
            'connection_string': connection_string
        }
        try:
            res = self.es.search(index='db_meta', body={'query': {'bool': {'must': [
                {'match': {'connection_id': connection_id}}
            ]}}})
            if res['hits']['total']['value'] > 0:
                doc_id = res['hits']['hits'][0]['_id']
                # Update existing connection
                self.es.update(index='db_meta', id=doc_id, body={"doc": document})
                logger.info("Connection updated successfully.")
            else:
                logger.info("No existing connection found, creating a new one.")
                # Create new connection
                self.es.index(index='db_meta', body=document)
                logger.info("New connection added successfully.")
        except Exception as e:
            logger.error(f"Error adding/editing connection: {str(e)}")
            raise


if __name__ == "__main__":    
    es = Search()

    # response = es.hybrid_search("What is sliding GQA?", "text_chunk")

    response = es.search(
        index="text_chunk",
        query={
            "match": {"chunk_text": "What is GQA?"}
        },
        _source=["_id", "chunk_text"]  # Fetch these fields
    )


    print("F")

    # print(response)

    for hit in response['hits']['hits']:
        # Print the ID, score, and a snippet of the description_text for each hits
        print(f"ID: {hit['_id']}, Score: {hit['_score']}, Snippet: {hit['_source']['chunk_text'][:100]}...")


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