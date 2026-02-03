#!/usr/bin/env python3
"""USearch SIFT1M Benchmark - Direct comparison with Bridge."""
import numpy as np
import time
from usearch.index import Index, MetricKind

def read_fvecs(filename):
    with open(filename, 'rb') as f:
        data = np.fromfile(f, dtype='int32')
    d = data[0]
    return data.reshape(-1, d + 1)[:, 1:].copy().view('float32')

def main():
    print("="*60)
    print("USearch SIFT1M Benchmark")
    print("="*60)

    # Load data
    print("\nLoading SIFT1M data...")
    base = read_fvecs("sift/sift_base.fvecs")
    queries = read_fvecs("sift/sift_query.fvecs")
    print(f"Base: {base.shape}, Queries: {queries.shape}")

    # Create index
    print("\nCreating USearch index...")
    index = Index(
        ndim=128,
        metric=MetricKind.L2sq,
        dtype='f32',
        connectivity=32,  # Similar to HNSW M parameter
        expansion_add=128,
        expansion_search=64,
    )

    # Add vectors
    print("Adding vectors...")
    start = time.time()
    ids = np.arange(len(base))
    index.add(ids, base)
    add_time = time.time() - start
    print(f"Added {len(base)} vectors in {add_time:.2f}s ({len(base)/add_time:.0f} vec/s)")

    # Warmup
    print("\nWarmup...")
    for q in queries[:100]:
        index.search(q, 10)

    # Benchmark - sequential
    print("\nSequential benchmark (10k queries)...")
    start = time.time()
    for q in queries:
        index.search(q, 10)
    seq_time = time.time() - start
    seq_qps = len(queries) / seq_time
    print(f"Sequential QPS: {seq_qps:.0f}")
    print(f"Avg latency: {(seq_time/len(queries))*1000000:.0f}μs")

    # Benchmark - batch
    print("\nBatch benchmark (10k queries at once)...")
    start = time.time()
    results = index.search(queries, 10)
    batch_time = time.time() - start
    batch_qps = len(queries) / batch_time
    print(f"Batch QPS: {batch_qps:.0f}")

    # Summary
    print("\n" + "="*60)
    print("USEARCH RESULTS")
    print("="*60)
    print(f"Dataset: SIFT1M (1M vectors, 128D)")
    print(f"Ingestion: {len(base)/add_time:.0f} vec/s")
    print(f"Sequential QPS: {seq_qps:.0f}")
    print(f"Batch QPS: {batch_qps:.0f}")
    print(f"Sequential latency: {(seq_time/len(queries))*1000000:.0f}μs")
    print("="*60)

if __name__ == "__main__":
    main()
