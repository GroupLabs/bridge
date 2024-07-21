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
        logger.info("ES is available")
        logger.info(str(client_info))

        # inferior to documents
        # configure text_chunk
        try:
            self.es.indices.create( # may fail if index exists
                index='text_chunk', 
                mappings={
                    'properties': {
                        'document_id': {'type': 'keyword'}, # TODO: Should this be murmur? check the available types
                        'access_group': {'type': 'keyword'},
                        "document_name": {
                                "type": "text",  # Main type for full-text search
                                "fields": {
                                    "kw": {  # Sub-field for exact matches and aggregations
                                        "type": "keyword"
                                    }
                                }
                            },
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
        
        # inferior to databases
        # configure table_meta
        try:
            self.es.indices.create( # may fail if index exists
                index='table_meta', 
                mappings={
                    'properties': {
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
        
        # inferior to model tasks
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

        logger.info("Configured.")

        self.registered_indices = [
            "text_chunk",
            "table_meta",
            "model_meta"
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
    def insert_object(self, document: any, index: str):

        # add embeddings
        if index == "text_chunk":
            document['e5'] = embed_passage(document['chunk_text']).tolist()[0]
            document['colbert'] = {}

        if index == "table_meta":
            document['e5'] = embed_passage(document['description_text']).tolist()[0]
            document['colbert'] = {}
            # correlation embeddings are handled at storage

        if index == "model_meta":
            document['e5'] = embed_passage(document['description_text']).tolist()[0]
            document['colbert'] = {}
            
        logger.info("Inserting document.")

        return self.es.index(index=index, body=document)

    def insert_objects(self, documents: any, index: str):
        operations = []
        for document in documents:
            operations.append({'index': {'_index': index}})
            operations.append(document)
        return self.es.bulk(operations=operations)

    # query ops
    def retrieve_object_by_id(self, id, index):
        return self.es.get(index=index, id=id)
    
    def retrieve_all_objects(self, index, scroll='2m', size=1000):
        # Initialize the scroll
        data = self.es.search(
            index=index,
            scroll=scroll,
            size=size,
            body={
                "query": {
                    "match_all": {}
                }
            }
        )

        sid = data['_scroll_id']
        scroll_size = len(data['hits']['hits'])

        # Start scrolling
        objects = []
        while scroll_size > 0:
            objects.extend(data['hits']['hits'])
            
            # Perform next scroll
            data = self.es.scroll(scroll_id=sid, scroll=scroll)
            
            # Update the scroll ID
            sid = data['_scroll_id']
            
            # Get the number of results that returned in the last scroll
            scroll_size = len(data['hits']['hits'])
        
        return objects
    
    def retrieve_object_ids(self, index):
        query = {
            "size": 0,
            "aggs": {
                "unique_docs": {
                    "composite": {
                        "size": 10000,  # set an appropriate size limit
                        "sources": [
                            {"document_name": {"terms": {"field": "document_name.kw"}}},
                            {"document_id": {"terms": {"field": "document_id"}}}
                        ]
                    }
                }
            }
        }
        return self.es.search(index=index, body=query)

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

        # convert to list of dicts (readability)
        sorted_results = [{"id": _id, "score": res["score"], "text": res["text"]} for _id, res in sorted_results]

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
    
    def hybrid_search(self, query: str, index: str, doc_ids: list[str] = None):
        INSPECT = False
        print(doc_ids)
        if not doc_ids:
            print("no doc_id")
        # Determine the field to use based on the index
        if index == 'text_chunk':
            _field = "chunk_text"
        elif index == 'table_meta':
            _field = "description_text"
        elif index == 'model_meta':
            _field = "description_text"
        else:
            raise NotImplementedError

        # construct the match query
        try:
            match_query = {
                "query": {
                    "bool": {
                        "must": [
                            {"match": {_field: query}}
                        ]
                    }
                },
                "_source": [_field]
            }

            # add filter if doc_id is provided
            if doc_ids:
                match_query["query"]["bool"]["filter"] = [{"terms": {"document_id": doc_ids}}]

            match_response = self.es.search(index=index, body=match_query)
        except BadRequestError as e:
            logger.info(e)
            return None

        if INSPECT:
            print("MATCH")
            for hit in match_response['hits']['hits']:
                print(f"ID: {hit['_id']}, Score: {hit['_score']}, Snippet: {hit['_source'][_field][:100]}...")

        match_results = match_response['hits']['hits']

        # Construct the knn query
        try:
            knn_query = {
                    "size" : 0,
                    "query" : {
                        "bool" : {
                            "must" : {
                                "knn": {
                                    'field': 'e5',
                                    'query_vector': embed_query(query).tolist()[0],
                                    'num_candidates': 50
                                }
                            }
                        }
                    }
                }
            
            # add filter if doc_id is provided
            if doc_ids:
                knn_query["query"]["bool"]["filter"] = [{"terms": {"document_id": doc_ids}}]

            knn_response = self.es.search(index=index, body=knn_query)
        except BadRequestError as e:
            logger.info(e)
            return None

        if INSPECT:
            print("KNN")
            for hit in knn_response['hits']['hits']:
                print(f"ID: {hit['_id']}, Score: {hit['_score']}, Snippet: {hit['_source'][_field][:100]}...")

        knn_results = knn_response['hits']['hits']

        # Combine results with reciprocal rank fusion
        result_sets_with_rankings = {
            "match": match_results,
            "knn": knn_results
        }

        weights = {
            "match": 1.0,
            "knn": 1.0
        }

        rrf_results = self._rrf(result_sets_with_rankings, weights, _field, INSPECT=INSPECT)

        logger.info(f"Hybrid search returned {len(rrf_results)} elements.")

        return rrf_results


if __name__ == "__main__":    
    pass