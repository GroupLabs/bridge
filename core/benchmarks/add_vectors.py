#!/usr/bin/env python3
"""Add vectors to an index for benchmarking."""
import numpy as np
import json
import urllib.request
import sys
import time

BASE_URL = "http://localhost:8080"

def add_batch(index_name: str, start_id: int, vectors: np.ndarray):
    documents = [
        {"text": f"d{start_id + i}", "vector": vectors[i].tolist()}
        for i in range(len(vectors))
    ]
    data = json.dumps({"index": index_name, "documents": documents}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/add_batch",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req, timeout=120)

def main():
    if len(sys.argv) < 4:
        print("Usage: add_vectors.py <index_name> <num_vectors> <dimensions>")
        print("Example: add_vectors.py myindex_d128 100000 128")
        sys.exit(1)

    index_name = sys.argv[1]
    num_vectors = int(sys.argv[2])
    dims = int(sys.argv[3])
    batch_size = 2000 if dims <= 128 else 500

    print(f"Adding {num_vectors} vectors ({dims}D) to {index_name}...", flush=True)
    start = time.time()

    all_vectors = np.random.randn(num_vectors, dims).astype(np.float32)
    print(f"Generated in {time.time() - start:.1f}s", flush=True)

    for i in range(0, num_vectors, batch_size):
        add_batch(index_name, i, all_vectors[i:i+batch_size])
        if (i + batch_size) % 10000 == 0:
            elapsed = time.time() - start
            print(f"Added {i+batch_size}/{num_vectors} ({(i+batch_size)/elapsed:.0f} vec/s)", flush=True)

    print(f"Done in {time.time() - start:.1f}s", flush=True)

if __name__ == "__main__":
    main()
