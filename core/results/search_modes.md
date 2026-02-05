# Bridge Search Modes

## Available Implementations

| Mode | Implementation | Code Location | Best For |
|------|----------------|---------------|----------|
| **HNSW** | `DescartesIndex` (pure Rust) | `src/descartes/mod.rs` | High-dim (512D+), large datasets (5K+) |
| **IVF** | `IvfIndex` (pure Rust) | `src/descartes/ivf.rs` | Fast builds, small datasets, perfect recall |
| **FastScan** | FAISS C++ FFI | `src/main.rs` (FAISS bindings) | Production speed, already in Bridge |

---

## Performance Comparison

### Search Speed (QPS)

| Scale | HNSW | IVF | FastScan |
|-------|------|-----|----------|
| 10K × 128D | 57,000 | 38,000 | 62,000 |
| 100K × 128D | 32,000 | 4,000 | ~60,000 |
| 100K × 512D | 6,500 | 900 | ~50,000 |
| 1M × 128D | ~3,000 | 600 | ~60,000 |

### Build Speed

| Mode | 10K × 128D | 100K × 512D |
|------|------------|-------------|
| IVF | 0.08s | 12.8s |
| HNSW | 4.2s | 130.4s |
| FastScan | ~1s | ~10s |

### Memory Usage

| Mode | 10K × 128D | 100K × 512D |
|------|------------|-------------|
| IVF | 6.6MB | 257.7MB |
| HNSW | 12.1MB | 312.8MB |
| FastScan | ~2MB (PQ compressed) | ~25MB |

### Recall

| Mode | Clustered Data | Random Data |
|------|----------------|-------------|
| IVF | 100% | 70-90% (nprobe dependent) |
| HNSW | 98-100% | 95-99% |
| FastScan | 95-97% | 95-97% |

---

## Decision Matrix

```
IF vectors < 10K:
    Use IVF (fast build, good search, perfect recall)

ELSE IF vectors >= 10K:
    Use FastScan (already integrated, best QPS)

ELSE IF need pure Rust + high dimensions:
    Use HNSW (7x faster than IVF at 512D+)
```

---

## When to Use Each

### IVF (`IvfIndex`)
- Prototyping and development
- Datasets under 10K vectors
- When build time matters (10-50x faster)
- When perfect recall on clustered data is needed
- Pure Rust requirement

### HNSW (`DescartesIndex`)
- High-dimensional vectors (512D+)
- Medium-large datasets (5K-100K)
- When search speed matters more than build time
- Pure Rust requirement

### FastScan (FAISS)
- Production deployments
- Large scale (10K+ vectors)
- Best search throughput needed
- Memory efficiency (PQ compression)

---

## Current Bridge Behavior

Bridge already auto-switches at 10K vectors:
- **< 10K**: Uses Descartes (currently HNSW)
- **≥ 10K**: Uses FAISS FastScan

### Recommended Enhancement

```
< 5K vectors:     IVF (fast build, simple)
5K - 10K vectors: HNSW (better search QPS)
≥ 10K vectors:    FastScan (production speed)
```
