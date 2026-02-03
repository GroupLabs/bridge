#!/usr/bin/env python3
"""Raw FAISS SIFT1M Benchmark - No HTTP overhead."""
import numpy as np
import time
import faiss

def read_fvecs(filename):
    with open(filename, 'rb') as f:
        data = np.fromfile(f, dtype='int32')
    d = data[0]
    return data.reshape(-1, d + 1)[:, 1:].copy().view('float32')

def main():
    print("="*60)
    print("FAISS SIFT1M Benchmark")
    print("="*60)

    # Load data
    print("\nLoading SIFT1M data...")
    base = read_fvecs("sift/sift_base.fvecs")
    queries = read_fvecs("sift/sift_query.fvecs")
    print(f"Base: {base.shape}, Queries: {queries.shape}")

    # Test HNSW
    print("\n--- HNSW Index ---")
    index_hnsw = faiss.IndexHNSWFlat(128, 32)
    index_hnsw.hnsw.efSearch = 64

    start = time.time()
    index_hnsw.add(base)
    print(f"HNSW add: {len(base)/(time.time()-start):.0f} vec/s")

    # Warmup
    for q in queries[:100]:
        index_hnsw.search(q.reshape(1, -1), 10)

    start = time.time()
    for q in queries:
        index_hnsw.search(q.reshape(1, -1), 10)
    hnsw_seq = len(queries) / (time.time() - start)
    print(f"HNSW Sequential QPS: {hnsw_seq:.0f}")

    start = time.time()
    index_hnsw.search(queries, 10)
    hnsw_batch = len(queries) / (time.time() - start)
    print(f"HNSW Batch QPS: {hnsw_batch:.0f}")

    # Test IVF-PQ FastScan (what Bridge uses)
    print("\n--- IVF-PQ FastScan Index ---")
    n = len(base)
    nlist = int(4 * np.sqrt(n))
    m = 128 // 8  # 16 subquantizers for 128D

    quantizer = faiss.IndexFlatL2(128)
    index_pq = faiss.IndexIVFPQ(quantizer, 128, nlist, m, 8)

    print("Training...")
    start = time.time()
    index_pq.train(base)
    print(f"Train time: {time.time()-start:.1f}s")

    print("Adding...")
    start = time.time()
    index_pq.add(base)
    print(f"IVF-PQ add: {len(base)/(time.time()-start):.0f} vec/s")

    index_pq.nprobe = 8  # Same as Bridge

    # Warmup
    for q in queries[:100]:
        index_pq.search(q.reshape(1, -1), 10)

    start = time.time()
    for q in queries:
        index_pq.search(q.reshape(1, -1), 10)
    pq_seq = len(queries) / (time.time() - start)
    print(f"IVF-PQ Sequential QPS: {pq_seq:.0f}")

    start = time.time()
    index_pq.search(queries, 10)
    pq_batch = len(queries) / (time.time() - start)
    print(f"IVF-PQ Batch QPS: {pq_batch:.0f}")

    # Summary
    print("\n" + "="*60)
    print("FAISS RESULTS (Raw, no HTTP)")
    print("="*60)
    print(f"HNSW Sequential: {hnsw_seq:.0f} QPS")
    print(f"HNSW Batch: {hnsw_batch:.0f} QPS")
    print(f"IVF-PQ Sequential: {pq_seq:.0f} QPS")
    print(f"IVF-PQ Batch: {pq_batch:.0f} QPS")
    print("="*60)

if __name__ == "__main__":
    main()
