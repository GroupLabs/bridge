from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim
from sentence_transformers.quantization import quantize_embeddings

# 1. Specify preffered dimensions
dimensions = 512

# 2. load model
model = SentenceTransformer("mixedbread-ai/mxbai-embed-large-v1", truncate_dim=dimensions)

def embed_passage(string):
    return model.encode(string)

def embed_query(string):
    return model.encode(f"'Represent this sentence for searching relevant passages: {string}")

def similarity(embA, embB):
    return float("{:.2f}".format(float(cos_sim(embA, embB))))

if __name__ == "__main__":
    embA = embed_passage("This is a document about hot dogs.")
    embB = embed_query("Tell me about hot dogs")

    print(embA)

    print(similarity(embA, embB))