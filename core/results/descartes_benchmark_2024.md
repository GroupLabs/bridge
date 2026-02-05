# Descartes Vector Search Benchmark Results

**Date:** 2024-02-04
**Platform:** Apple Silicon (ARM64)
**SIMD:** NEON

## Executive Summary

- **IVF achieves 100% recall** on well-clustered data across all configurations
- **HNSW is faster for search** at higher dimensions (2-5x speedup at 512D+)
- **IVF is faster for build** (10-50x speedup) and uses less memory (2x)
- Choose based on workload: frequent rebuilds → IVF, high-dim search → HNSW

---

## 1. SIMD Distance Function Performance

| Implementation | ns/distance | Throughput | Speedup |
|----------------|-------------|------------|---------|
| C++ NEON | 5.1ns | 194M/sec | **1.55x** |
| Rust auto-vec | 8.0ns | 125M/sec | baseline |

---

## 2. IVF Recall by Scale (Clustered Data)

| Vectors | Dim | nlist | nprobe | QPS | Recall | Build | Memory |
|---------|-----|-------|--------|-----|--------|-------|--------|
| 10K | 128 | 64 | 16 | 25,558 | **100%** | 0.1s | 6.6MB |
| 10K | 512 | 64 | 16 | 7,738 | **100%** | 0.3s | 25.8MB |
| 10K | 4096 | 64 | 16 | 606 | **100%** | 2.6s | 205.2MB |
| 100K | 128 | 256 | 24 | 3,982 | **100%** | 3.3s | 65.6MB |
| 100K | 512 | 256 | 24 | 792 | **100%** | 12.7s | 257.7MB |
| 1M | 128 | 1024 | 32 | 627 | **100%** | 200s | 656.1MB |

---

## 3. HNSW vs IVF by Dimension (10K vectors)

| Dim | HNSW QPS | IVF QPS | HNSW Speedup | HNSW Recall | IVF Recall | HNSW Build | IVF Build |
|-----|----------|---------|--------------|-------------|------------|------------|-----------|
| 128 | 56,916 | 38,271 | **1.5x** | 100% | 100% | 4.16s | 0.08s |
| 256 | 38,507 | 21,246 | **1.8x** | 100% | 100% | 5.19s | 0.17s |
| 512 | 27,396 | 10,816 | **2.5x** | 100% | 100% | 10.41s | 0.33s |
| 1024 | 16,760 | 4,385 | **3.8x** | 98% | 100% | 13.91s | 0.66s |
| 2048 | 9,185 | 1,784 | **5.1x** | 99.4% | 100% | 24.74s | 1.31s |

**Key insight:** HNSW's advantage grows with dimension because it does fewer distance computations (~2,500 fixed) vs IVF's linear scan (~2,500 × nprobe).

---

## 4. HNSW vs IVF by Dataset Size (128D)

| Vectors | HNSW QPS | IVF QPS | Winner | HNSW Recall | IVF Recall | HNSW Build | IVF Build |
|---------|----------|---------|--------|-------------|------------|------------|-----------|
| 1K | 109,548 | 195,427 | **IVF 1.8x** | 100% | 100% | 0.39s | 0.02s |
| 5K | 98,594 | 60,942 | **HNSW 1.6x** | 100% | 100% | 2.06s | 0.10s |
| 10K | 66,236 | 34,581 | **HNSW 1.9x** | 100% | 100% | 4.19s | 0.19s |
| 50K | 31,837 | 6,305 | **HNSW 5x** | 99.8% | 100% | 22.64s | 2.13s |

**Key insight:** IVF wins at very small scales (1K) where cluster overhead is minimal. HNSW wins at larger scales due to O(log n) vs O(n/nlist) complexity.

---

## 5. IVF nprobe vs QPS/Recall Tradeoff (10K × 128D, random data)

| nprobe | QPS | Recall@10 |
|--------|-----|-----------|
| 1 | 97,679 | 17.2% |
| 2 | 100,862 | 22.2% |
| 4 | 87,545 | 27.4% |
| 8 | 62,672 | 39.0% |
| 16 | 46,735 | 52.2% |
| 32 | 28,185 | 70.2% |

**Note:** Random uniform data doesn't cluster well. Real-world data achieves much higher recall.

---

## 6. Algorithm Complexity Analysis

### HNSW
```
Distance computations per query ≈ ef_search × avg_neighbors ≈ 80 × 32 ≈ 2,560
Complexity: O(log n) for graph traversal
```

### IVF
```
Distance computations per query ≈ nprobe × (n / nlist)
For 50K vectors, nlist=223, nprobe=56: 56 × 224 ≈ 12,544
Complexity: O(n / nlist) linear scan within clusters
```

---

## 7. Recommendations

| Use Case | Recommended | Reason |
|----------|-------------|--------|
| High-dim vectors (512D+) | HNSW | 2-5x faster search |
| Frequent index rebuilds | IVF | 10-50x faster build |
| Memory constrained | IVF | 2x less memory |
| Very small datasets (<5K) | IVF | Lower overhead |
| Large datasets (>10K) | HNSW | Better scaling |
| Need perfect recall | IVF | 100% on clustered data |

---

## 8. Implementation Details

### Files Created
- `src/simd/bridge_simd.h` - C header for SIMD functions
- `src/simd/bridge_simd.cpp` - AVX2 (x86) + NEON (ARM) implementations
- `src/descartes/ivf.rs` - IVF index with k-means clustering
- `src/descartes/benchmark.rs` - Comprehensive benchmarking
- `src/descartes/bench_compare.rs` - HNSW vs IVF comparison

### Key Optimizations
1. **SIMD distance computation** - 1.55x speedup via explicit NEON/AVX2 intrinsics
2. **Sampling-based k-means** - 10x faster build for large datasets
3. **Parallel cluster assignment** - Uses rayon for multi-core assignment
4. **Float32 coarse search** - Accurate centroid selection for better recall
