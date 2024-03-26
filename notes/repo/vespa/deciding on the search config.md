> March 25, 2024

We noticed that there are a couple different retrieval mechanisms (bm25, embeddings, etc.), each with their own strengths and weaknesses. We chose to develop 3 ranking profiles.

`colbertande5` - uses two dense embedding models, and uses both to rank the documents.

`nativerank` - is a more traditional approach and is wildly useful especially for exact text.

`hybrid search` - uses the best of both words by ranking based on both methods. There is an alpha parameter that allows you to change the weight between the methods.





The following are some potential queries (not implemented):

```
response = vespa_query.query(
    body={
        "yql": 'select * from text_chunk where userQuery();',
        # "yql": 'select * from sources * where userQuery();', can be this if all .sd has same rank-profiles
        "hits": 10,
        "query": query_str
        "type": "any",
        "ranking": "default"
    }
)

print(response.json)


response = vespa_query.query(
    yql="select id,chunk_text from text_chunk where userQuery() or ({targetHits:10}nearestNeighbor(embedding,q))",
    groupname="all",
    ranking="hybrid_search",  # Use the correct rank profile
    query=query_str,
    body={
        "presentation.format.tensors": "short-value",
        "ranking.features.query(q)": f'embed(e5, "{query_str}")',
        "ranking.features.query(alpha)": 0.5,
    },
)

response = vespa_query.query(
    yql= f'select * from sources * where chunk_text contains "{query_str}"',
    groupname="all",
)
```