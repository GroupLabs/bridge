> March 25, 2024

We noticed that there are a couple different retrieval mechanisms (bm25, embeddings, etc.), each with their own strengths and weaknesses. We chose to develop 3 ranking profiles.

`colbertande5` - uses two dense embedding models, and uses both to rank the documents.

`nativerank` - is a more traditional approach and is wildly useful especially for exact text.

`hybrid search` - uses the best of both words by ranking based on both methods. There is an alpha parameter that allows you to change the weight between the methods.


