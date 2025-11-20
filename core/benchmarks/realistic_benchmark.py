#!/usr/bin/env python3
"""
Realistic benchmark: 100K documents with 4096D embeddings
Simulates production workload similar to text-embedding-3-large
"""

import requests
import time
import random
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "http://localhost:8080"
INDEX_NAME = "bench_d4096"
DIMENSION = 4096
TOTAL_DOCS = 100_000
BATCH_SIZE = 10  # Reduced from 100 due to 2MB payload limit (4096D × 10 docs = ~1.6MB)
NUM_WORKERS = 20  # Increased workers to compensate

def create_index():
    """Create index with 4096 dimensions"""
    print("Creating index...")
    resp = requests.post(f"{BASE_URL}/create_index", json={
        "name": "realistic",
        "dimension": DIMENSION,
        "k": 10
    })
    if resp.status_code == 200:
        print(f"✓ Index created: {INDEX_NAME}")
    else:
        print(f"✗ Failed to create index: {resp.text}")
        exit(1)

def generate_random_vector():
    """Generate normalized random vector"""
    vec = np.random.randn(DIMENSION).astype(np.float32)
    vec = vec / np.linalg.norm(vec)
    return vec.tolist()

def add_batch(batch_id, start_idx, batch_size):
    """Add a batch of documents"""
    documents = []
    for i in range(start_idx, start_idx + batch_size):
        documents.append({
            "text": f"Document {i}: This is a realistic test document with meaningful content",
            "vector": generate_random_vector()
        })

    try:
        resp = requests.post(f"{BASE_URL}/add_batch", json={
            "index": INDEX_NAME,
            "documents": documents
        }, timeout=60)

        if resp.status_code == 200:
            return True, batch_size
        else:
            print(f"Batch {batch_id} failed with status {resp.status_code}: {resp.text[:200]}")
            return False, 0
    except Exception as e:
        print(f"Batch {batch_id} exception: {e}")
        return False, 0

def populate_index():
    """Populate index with 100K documents using parallel batching"""
    print(f"\nPopulating with {TOTAL_DOCS:,} documents ({DIMENSION}D vectors)...")
    print(f"Using {NUM_WORKERS} parallel workers, batch size: {BATCH_SIZE}")

    num_batches = TOTAL_DOCS // BATCH_SIZE
    start_time = time.time()
    completed = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        futures = []
        for batch_id in range(num_batches):
            start_idx = batch_id * BATCH_SIZE
            future = executor.submit(add_batch, batch_id, start_idx, BATCH_SIZE)
            futures.append(future)

        for future in as_completed(futures):
            success, count = future.result()
            if success:
                completed += count
                if completed % 1000 == 0:
                    elapsed = time.time() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    print(f"  Progress: {completed:,}/{TOTAL_DOCS:,} docs ({rate:.0f} docs/sec)")
            else:
                failed += 1

    elapsed = time.time() - start_time
    rate = completed / elapsed if elapsed > 0 else 0
    print(f"✓ Populated {completed:,} documents in {elapsed:.1f}s ({rate:.0f} docs/sec)")
    if failed > 0:
        print(f"  Failed batches: {failed}")

def run_search_test(num_queries=100):
    """Run search queries and measure performance"""
    print(f"\nRunning {num_queries} search queries...")

    latencies = []
    for i in range(num_queries):
        query_vec = generate_random_vector()

        start = time.time()
        resp = requests.post(f"{BASE_URL}/search", json={
            "index": INDEX_NAME,
            "vector_query": query_vec,
            "text_query": "test document",
            "vector_weight": 0.7,
            "text_weight": 0.3,
            "k": 10
        })
        latency = (time.time() - start) * 1000

        if resp.status_code == 200:
            latencies.append(latency)
        else:
            print(f"Query {i} failed: {resp.status_code}")

    if latencies:
        latencies.sort()
        print(f"\nSearch Performance ({len(latencies)} queries):")
        print(f"  Avg Latency:  {np.mean(latencies):.2f} ms")
        print(f"  P50 Latency:  {latencies[len(latencies)//2]:.2f} ms")
        print(f"  P95 Latency:  {latencies[int(len(latencies)*0.95)]:.2f} ms")
        print(f"  P99 Latency:  {latencies[int(len(latencies)*0.99)]:.2f} ms")
        print(f"  Max Latency:  {max(latencies):.2f} ms")
        print(f"  Throughput:   {1000/np.mean(latencies):.2f} req/s (sequential)")

if __name__ == "__main__":
    import sys

    # Check server health
    try:
        resp = requests.get(f"{BASE_URL}/health")
        if resp.status_code != 200:
            print("✗ Server not healthy")
            exit(1)
    except:
        print("✗ Server not running")
        exit(1)

    # Check if running in populate-only mode
    if len(sys.argv) > 1 and sys.argv[1] == "populate":
        # Just populate, no search tests
        populate_index()
        exit(0)

    # Full benchmark mode
    print("=" * 60)
    print("  REALISTIC BENCHMARK: 100K docs × 4096D")
    print("=" * 60)
    print("✓ Server is healthy\n")

    # Create and populate
    create_index()
    populate_index()

    # Run search tests
    run_search_test(num_queries=100)

    print("\n" + "=" * 60)
    print("  BENCHMARK COMPLETE")
    print("=" * 60)
