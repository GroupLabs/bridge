It seems like the embeddings will largely depend on what we want to use as the LLM (mainly for the efficiency of not having to compute it again). However, we can decouple them, and make our embeddings entirely separate from what is inputted to the LLM. This won't be too performance intensive, as we only ever pass in the relevant subset to the LLM (this always happens after reduction by search via attn mechanism or semantic search)

- How do we create a multimodal storage mechanism?
- How can we make it fast? scalable?

## Using FAISS

- How do we make embeddings?
	- Llama2 embeddings?
	- SentenceTransformers !!


purpose: store and retrieve data.

INGESTION

STORAGE

FAISS, shards

RETRIEVAL

Knowledge Graph -> (Basic) Attention mechanism + Statistical [Variance/Deviation] / (Adv) Fine tuned LLM or Graph Attention Networks? -> Relevant Subset
How do we resolve dependencies?