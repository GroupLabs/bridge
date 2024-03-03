
import faiss
import numpy as np
import pickle
import json
import torch
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans

TOKENIZERS_PARALLELISM=True

class Search:
    VEC_DIM = 768
    EMBEDDING_MODEL_NAME = "msmarco-distilbert-base-tas-b"
    EMBEDDING_MODEL = SentenceTransformer(EMBEDDING_MODEL_NAME)

    def __init__(self, load_file=None):
        if not load_file:
            self.index = faiss.IndexFlatL2(self.VEC_DIM)  # instantiate index
            self.values = []
        else:
            with open(f"/shards/{load_file}.pkl", "rb") as f:
                self.index = pickle.load(f)
            with open(f"/shards/{load_file}.json", "r") as f:
                self.values = json.load(f)

    def __repr__(self) -> str:
        # r = ""
        # r = r + "Search: \n"
        # r = r + f".... status: {self.app.get_application_status()}\n"
        # r = r + f".... storing {len(self)} value(s)"
        # return r
        return ""

    def embed(self, text):  # create embedding from strings (and other modes later)
        return torch.as_tensor(self.EMBEDDING_MODEL.encode(text))

    def store(self, input):
        self.index.add(np.array([self.embed(input)]))
        self.values.append(input)

    def store_object(self, input, semantic_context_key="semantic_context"):
        if semantic_context_key not in input:
            raise ValueError("Semantic context for object could not be found")

        self.index.add(np.array([self.embed(input[semantic_context_key])]))
        self.values.append(input)

    def query(self, input, k=-1, return_distances=False):
        if k == -1:
            k = len(self.values)  # use max number of values as k

        query_vec = self.embed(input).reshape(1, -1)
        distances, indices = self.index.search(query_vec, k)

        # apply k means to find relevancy
        distances_reshaped = distances.reshape(-1, 1)
        kmeans = KMeans(n_clusters=2, random_state=0, n_init="auto").fit(
            distances_reshaped
        )
        cluster_centers = sorted(kmeans.cluster_centers_.flatten())
        cutoff = (cluster_centers[0] + cluster_centers[1]) / 2

        # apply cutoff
        relevant_indices = indices[0][distances[0] < cutoff]

        results = [self.values[i] for i in relevant_indices]

        if return_distances:
            relevant_distances = distances[0][distances[0] < cutoff]
            return relevant_distances, results
        return results

    def save(self, name):
        with open(f"shards/{name}.pkl", "wb") as f:
            pickle.dump(self.index, f)
        with open(f"shards/{name}.json", "w") as f:
            json.dump(self.values, f)

if __name__ == "__main__":
    pass