# Bridge Search Benchmark Results

**Date:** February 3, 2026
**Hardware:** Apple Silicon Mac
**Dataset:** 100,000 vectors
**Test Duration:** 30 seconds per test
**Concurrency:** 8 threads, 64 connections

## Summary

| Search Mode | 128D QPS | 128D Latency | 4096D QPS | 4096D Latency |
|-------------|----------|--------------|-----------|---------------|
| **HNSW** | 61,129 | 1.70ms | 6,007 | 10.93ms |
| **FastScan** | 77,621 | 2.78ms | 15,064 | 4.77ms |
| **Text-only** | - | - | 92,847 | 14.10ms* |
| **Hybrid** | - | - | 15,416 | 4.87ms |

*\*High latency at 64 connections due to queuing; true latency is 53μs (see below)*

## Key Findings

### HNSW vs FastScan
- **128D:** FastScan is **27% faster** than HNSW
- **4096D:** FastScan is **2.5x faster** than HNSW
- FastScan's advantage increases with higher dimensions

### True Latencies (Single Connection)
| Search Mode | Latency | Single-thread QPS |
|-------------|---------|-------------------|
| Text-only | **53μs** | 17,936 |
| Vector (FastScan 4096D) | **405μs** | 2,419 |

### Parallelism Scaling (FastScan 4096D)
| Concurrency | QPS | Scaling |
|-------------|-----|---------|
| 1 connection | 2,419 | 1x |
| 64 connections | 15,637 | **6.5x** |

FastScan benefits significantly from multiple cores because:
- `OMP_NUM_THREADS=1` keeps each search single-threaded (no contention)
- Rayon thread pool runs multiple searches in parallel
- Architecture: "many single-threaded searches in parallel"

## Configuration

### FastScan Upgrade Threshold
```rust
const IVF_PQ_UPGRADE_THRESHOLD: usize = 10_000;
```
Index automatically upgrades from HNSW to FastScan after 10k vectors.

### FastScan Parameters
- **nlist:** `4 * sqrt(n)` (clamped 16-4096)
- **m (PQ segments):** `dimension / 64` (clamped 8-64)
- **nprobe:** 8 (search-time parameter)

## Running Benchmarks

```bash
# Start server
./target/release/core

# Create index
curl -X POST http://localhost:8080/create_index \
  -H "Content-Type: application/json" \
  -d '{"name":"bench","dimension":128}'

# Add vectors
python3 benchmarks/add_vectors.py bench_d128 100000 128

# Run benchmark
./benchmarks/run_benchmark.sh bench_d128 128 30s
```

## Environment Variables

The Lua scripts accept environment variables:
- `INDEX_NAME`: Index to benchmark (default: "test_d128")
- `DIMS`: Vector dimensions (default: 128)

```bash
INDEX_NAME=myindex_d4096 DIMS=4096 wrk -t8 -c64 -d30s -s benchmarks/vector_search.lua http://localhost:8080/search
```
