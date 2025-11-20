# Bridge Search Performance Benchmarks

Comprehensive load testing suite using `wrk` for the Bridge hybrid search system.

## Prerequisites

```bash
# Install wrk
brew install wrk

# Ensure server is running
cargo run --release
```

## Quick Start

Run a quick 10-second performance test:

```bash
./benchmarks/quick_test.sh
```

## Full Test Suite

Run the complete 30-second performance test suite:

```bash
./benchmarks/run_tests.sh
```

## Test Scenarios

### 1. Single Document Addition (`add.lua`)
- **Endpoint**: `POST /add`
- **Configuration**: 4 threads, 100 connections
- **Payload**: Individual documents with random vectors
- **Expected**: ~1,000-2,000 req/s

```bash
wrk -t4 -c100 -d30s -s benchmarks/add.lua http://localhost:8080/add
```

### 2. Batch Document Addition (`batch_add.lua`)
- **Endpoint**: `POST /add_batch`
- **Configuration**: 2 threads, 10 connections
- **Payload**: 10 documents per request
- **Expected**: ~10,000-50,000 docs/s

```bash
wrk -t2 -c10 -d30s -s benchmarks/batch_add.lua http://localhost:8080/add_batch
```

### 3. Hybrid Search (`search.lua`)
- **Endpoint**: `POST /search`
- **Configuration**: 4 threads, 100 connections
- **Payload**: Vector query + text query with weighted RRF
- **Expected**: ~800-1,500 req/s

```bash
wrk -t4 -c100 -d30s -s benchmarks/search.lua http://localhost:8080/search
```

### 4. Health Check Baseline
- **Endpoint**: `GET /health`
- **Configuration**: 4 threads, 100 connections
- **Expected**: ~20,000+ req/s (baseline for async overhead)

```bash
wrk -t4 -c100 -d30s http://localhost:8080/health
```

## Custom Tests

### Adjust Concurrency

```bash
# Light load
wrk -t2 -c10 -d10s -s benchmarks/search.lua http://localhost:8080/search

# Heavy load
wrk -t8 -c200 -d60s -s benchmarks/search.lua http://localhost:8080/search
```

### Modify Lua Scripts

Edit the scripts to customize:
- **Vector dimensions**: Change vector generation in `add.lua`
- **Batch sizes**: Modify `batch_size` in `batch_add.lua`
- **Search patterns**: Add queries in `search.lua`
- **RRF weights**: Adjust `vector_weight` and `text_weight`

## Performance Metrics

### Key Metrics to Monitor

1. **Throughput**
   - Requests/sec
   - Documents/sec (for batch operations)

2. **Latency**
   - Average latency
   - P50, P95, P99 percentiles
   - Maximum latency

3. **Errors**
   - HTTP error rate
   - Timeout rate

### Expected Performance (Apple Silicon M1/M2)

| Operation | Throughput | P99 Latency |
|-----------|------------|-------------|
| Single Add | 1,500-2,000 req/s | <100ms |
| Batch Add (10) | 20,000-50,000 docs/s | <200ms |
| Hybrid Search | 1,000-1,500 req/s | <150ms |
| Health Check | 25,000+ req/s | <10ms |

## Architecture Optimizations

The test results validate these performance features:

- **Lock-free concurrency**: DashMap + AtomicI64
- **Async FAISS**: spawn_blocking prevents runtime blocking
- **Batch operations**: 5-10x faster than individual inserts
- **Weighted RRF**: Efficient parallel vector + text search
- **Zero-copy strings**: Arc<str> reduces memory allocations
- **WAL disabled**: For benchmarking, WAL writes are disabled for max throughput
  - **Note**: WAL is commented out in `main.rs` for benchmarks
  - Uncomment WAL code for production durability guarantees

## Troubleshooting

### Server Not Responding

```bash
# Check server health
curl http://localhost:8080/health

# Check if port is in use
lsof -i :8080
```

### High Error Rates

- Reduce concurrency: Lower `-c` (connections)
- Increase duration: Longer `-d` for warmup
- Check server logs for bottlenecks

### Low Throughput

- Ensure release build: `cargo build --release`
- Check CPU usage: `top` or `htop`
- Verify OpenMP is working: Check parallelism in FAISS
- Monitor disk I/O: Check if WAL is bottleneck

## CI/CD Integration

Add to your CI pipeline:

```yaml
# .github/workflows/performance.yml
- name: Performance Regression Test
  run: |
    cargo build --release
    ./target/release/core &
    sleep 5
    ./benchmarks/quick_test.sh
    # Parse results and fail if below threshold
```

## Contributing

When adding new endpoints:
1. Create a new Lua script in `benchmarks/`
2. Add test case to `run_tests.sh`
3. Document expected performance
4. Update this README
