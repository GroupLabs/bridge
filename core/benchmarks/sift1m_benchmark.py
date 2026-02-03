#!/usr/bin/env python3
"""SIFT1M Benchmark for Bridge Search.

Downloads SIFT1M dataset and benchmarks vector search performance.
Dataset: 1M vectors, 128 dimensions, L2 distance.
"""
import numpy as np
import json
import urllib.request
import time
import sys
import os
import tarfile
import shutil
from concurrent.futures import ThreadPoolExecutor

BASE_URL = "http://localhost:8080"
INDEX_NAME = "sift1m_d128"
BATCH_SIZE = 2000

def download_sift1m():
    """Download and extract SIFT1M dataset."""
    if os.path.exists("sift/sift_base.fvecs"):
        print("SIFT1M already downloaded")
        return True

    print("Downloading SIFT1M dataset...")
    url = "ftp://ftp.irisa.fr/local/texmex/corpus/sift.tar.gz"

    try:
        urllib.request.urlretrieve(url, "sift.tar.gz")
        print("Extracting...")
        with tarfile.open("sift.tar.gz", "r:gz") as tar:
            tar.extractall()
        os.remove("sift.tar.gz")
        print("Download complete!")
        return True
    except Exception as e:
        print(f"Download failed: {e}")
        print("Trying Hugging Face mirror...")
        # Fallback to HuggingFace
        try:
            os.makedirs("sift", exist_ok=True)
            for f in ["sift_base.fvecs", "sift_query.fvecs", "sift_groundtruth.ivecs"]:
                url = f"https://huggingface.co/datasets/qbo-odp/sift1m/resolve/main/{f}"
                print(f"Downloading {f}...")
                urllib.request.urlretrieve(url, f"sift/{f}")
            print("Download complete!")
            return True
        except Exception as e2:
            print(f"HuggingFace download also failed: {e2}")
            return False

def read_fvecs(filename):
    """Read .fvecs file format."""
    with open(filename, 'rb') as f:
        data = np.fromfile(f, dtype='int32')
    d = data[0]
    return data.reshape(-1, d + 1)[:, 1:].copy().view('float32')

def read_ivecs(filename):
    """Read .ivecs file format (for groundtruth)."""
    with open(filename, 'rb') as f:
        data = np.fromfile(f, dtype='int32')
    d = data[0]
    return data.reshape(-1, d + 1)[:, 1:].copy()

def create_index():
    """Create Bridge index for SIFT1M."""
    print(f"Creating index {INDEX_NAME}...")
    data = json.dumps({"name": "sift1m", "dimension": 128}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/create_index",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        print(resp.read().decode())
        return True
    except Exception as e:
        print(f"Create index failed: {e}")
        return False

def add_vectors(vectors):
    """Add vectors to index."""
    n = len(vectors)
    print(f"Adding {n} vectors to index...")
    start = time.time()

    for i in range(0, n, BATCH_SIZE):
        batch = vectors[i:i+BATCH_SIZE]
        documents = [
            {"text": f"v{i+j}", "vector": batch[j].tolist()}
            for j in range(len(batch))
        ]
        data = json.dumps({"index": INDEX_NAME, "documents": documents}).encode()
        req = urllib.request.Request(
            f"{BASE_URL}/add_batch",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=120)

        if (i + BATCH_SIZE) % 100000 == 0:
            elapsed = time.time() - start
            rate = (i + BATCH_SIZE) / elapsed
            print(f"Added {i+BATCH_SIZE}/{n} ({rate:.0f} vec/s)", flush=True)

    elapsed = time.time() - start
    print(f"Added {n} vectors in {elapsed:.1f}s ({n/elapsed:.0f} vec/s)")

def search(query_vector, k=10):
    """Search for nearest neighbors."""
    data = json.dumps({
        "index": INDEX_NAME,
        "vector_query": query_vector.tolist(),
        "k": k
    }).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/search",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read().decode())

def benchmark_search(queries, k=10, num_queries=None):
    """Benchmark search performance."""
    if num_queries:
        queries = queries[:num_queries]

    n = len(queries)
    print(f"Benchmarking with {n} queries (k={k})...")

    # Warmup
    print("Warmup (100 queries)...")
    for q in queries[:100]:
        search(q, k)

    # Benchmark
    print("Running benchmark...")
    start = time.time()

    for i, q in enumerate(queries):
        search(q, k)
        if (i + 1) % 1000 == 0:
            elapsed = time.time() - start
            qps = (i + 1) / elapsed
            print(f"Progress: {i+1}/{n} ({qps:.0f} QPS)", flush=True)

    elapsed = time.time() - start
    qps = n / elapsed
    avg_latency_ms = (elapsed / n) * 1000

    print(f"\n{'='*50}")
    print(f"SIFT1M Benchmark Results (Sequential)")
    print(f"{'='*50}")
    print(f"Queries: {n}")
    print(f"Total time: {elapsed:.2f}s")
    print(f"QPS: {qps:.2f}")
    print(f"Avg latency: {avg_latency_ms:.2f}ms")
    print(f"{'='*50}")

    return qps, avg_latency_ms

def benchmark_search_parallel(queries, k=10, num_queries=None, threads=8):
    """Benchmark search with parallel requests."""
    if num_queries:
        queries = queries[:num_queries]

    n = len(queries)
    print(f"Benchmarking with {n} queries, {threads} threads (k={k})...")

    # Warmup
    print("Warmup...")
    with ThreadPoolExecutor(max_workers=threads) as executor:
        list(executor.map(lambda q: search(q, k), queries[:100]))

    # Benchmark
    print("Running parallel benchmark...")
    start = time.time()

    with ThreadPoolExecutor(max_workers=threads) as executor:
        list(executor.map(lambda q: search(q, k), queries))

    elapsed = time.time() - start
    qps = n / elapsed
    avg_latency_ms = (elapsed / n) * 1000 * threads  # Approximate

    print(f"\n{'='*50}")
    print(f"SIFT1M Benchmark Results (Parallel, {threads} threads)")
    print(f"{'='*50}")
    print(f"Queries: {n}")
    print(f"Total time: {elapsed:.2f}s")
    print(f"QPS: {qps:.2f}")
    print(f"{'='*50}")

    return qps

def calculate_recall(queries, groundtruth, k=10, num_queries=100):
    """Calculate recall@k."""
    print(f"Calculating recall@{k} with {num_queries} queries...")

    recalls = []
    for i in range(num_queries):
        result = search(queries[i], k)
        returned_ids = set(r["id"] for r in result["results"])
        true_ids = set(groundtruth[i][:k].tolist())
        recall = len(returned_ids & true_ids) / k
        recalls.append(recall)

    avg_recall = np.mean(recalls)
    print(f"Recall@{k}: {avg_recall:.4f} ({avg_recall*100:.2f}%)")
    return avg_recall

def main():
    print("="*60)
    print("SIFT1M Benchmark for Bridge Search")
    print("="*60)

    # Download dataset
    if not download_sift1m():
        sys.exit(1)

    # Load data
    print("\nLoading SIFT1M data...")
    base_vectors = read_fvecs("sift/sift_base.fvecs")
    query_vectors = read_fvecs("sift/sift_query.fvecs")
    groundtruth = read_ivecs("sift/sift_groundtruth.ivecs")

    print(f"Base vectors: {base_vectors.shape}")
    print(f"Query vectors: {query_vectors.shape}")
    print(f"Groundtruth: {groundtruth.shape}")

    # Create index and add vectors
    if not create_index():
        print("Index may already exist, continuing...")

    add_vectors(base_vectors)

    # Run benchmarks
    print("\n" + "="*60)
    print("Running Benchmarks")
    print("="*60)

    # Sequential benchmark
    seq_qps, seq_latency = benchmark_search(query_vectors, k=10, num_queries=1000)

    # Parallel benchmark
    par_qps = benchmark_search_parallel(query_vectors, k=10, num_queries=10000, threads=32)

    # Recall calculation
    recall = calculate_recall(query_vectors, groundtruth, k=10, num_queries=100)

    # Summary
    print("\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)
    print(f"Dataset: SIFT1M (1M vectors, 128D)")
    print(f"Sequential QPS: {seq_qps:.0f}")
    print(f"Sequential Latency: {seq_latency:.2f}ms")
    print(f"Parallel QPS (32 threads): {par_qps:.0f}")
    print(f"Recall@10: {recall*100:.2f}%")
    print("="*60)

if __name__ == "__main__":
    main()
