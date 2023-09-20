The vector storage stores both embeddings (in a FAISS index that's L2 optimized), and raw values (either primitive types, or objects as dictionaries). *The storage can mix types right now so be careful.*

We are using an L2 optimized index because our embedding model, provided by sentence transformers is designed to operate with euclidean distance. It is also best performing (better than cosine) at the time of writing.

### saving & loading
When saving/loading there are two operations. At save, FAISS indices are dumped into .pkl files and values (primitive types, or objects) are dumped into json files in the shards directory. At load the opposite happens. Load is only possible when instantiating a storage object.
### query
Query can operate like a simple euclidean distance with k nearest neighbours. This is implemented largely by FAISS. When querying we go a step further and decided which set of returned values are actually relevant. This is done by doing a K-means clustering approach. This approach returns a dynamic set.

It might also make sense to switch to a z-score approach. More debate is required. Example is provided:

```
from scipy.stats import zscore

# Example distances
distances = np.array([0.1, 0.2, 0.3, 0.9, 1.0, 1.1])
# Compute Z-scores
z_scores = zscore(distances)

# Define Z-score threshold (e.g., within 1 standard deviation from the mean)
threshold = 1.0

# Find relevant distances
relevant_distances = distances[np.abs(z_scores) < threshold]

print("Z-score threshold:", threshold)
print("Relevant distances:", relevant_distances)
```
``
