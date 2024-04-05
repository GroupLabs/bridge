> March 29, 2024

There are many types of search mechanisms.

For example, there is embedding-based, exact, phrase, n-gram, fuzzy, and so forth.

For our use case, we decided to combine an embedding-based retriever with a text-based one. The exact type of the text-based one was less important. This approach allows to achieve a semantically accurate answer, and identify keywords. This can be useful if the user queries for specific names or categories. To combine the results, we opted to use our own implementation of reciprocal rank fusion (RRF).

To implement this, we considered Vespa, Elasticsearch, Solr, and LanceDB among others. We chose to move away from vector-only search engines, as they lack support for text based search such as BM25. Vespa lacked the maturity and support we required to keep the momentum of the project. Ultimately, we selected ES for its proficiency in autoscaling, full text search (FTS), vector support, and for the documentation and thriving community.

> April 5, 2024

For now, we are choosing not to pursue search methods that do not directly improve our hybrid search. In this decision, we are opting to iterate and improve on one search method instead of tackling many at once. We believe that thanks to ES, it will be fairly straightforward to implement other types of search (fuzzy, exact, phrase, etc.). 

Our hybrid search implementation currently uses RRF to combine results from a standard (no option set) BM25 query and a cosine similarity of e5-small embeddings. There is reason to consider https://huggingface.co/mixedbread-ai/mxbai-embed-large-v1 for its size and performance on MTEB.