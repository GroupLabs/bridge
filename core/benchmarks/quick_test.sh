#!/bin/bash
# Quick performance test (10 seconds each)
set -e

BASE_URL="http://localhost:8080"
DURATION=10s

echo "Quick Performance Test (10s each)"
echo "===================================="
echo ""

# Create index
curl -sf -X POST "$BASE_URL/create_index" \
    -H "Content-Type: application/json" \
    -d '{"name":"bench","dimension":3,"k":10}' > /dev/null 2>&1 || true

# Pre-populate
echo "Pre-populating with 50 docs..."
for i in {1..50}; do
    curl -sf -X POST "$BASE_URL/add" \
        -H "Content-Type: application/json" \
        -d "{\"index\":\"bench_d3\",\"text\":\"test $i\",\"vector\":[1.0,2.0,3.0]}" > /dev/null &
done
wait
echo ""

echo "1. Testing Single Add (4 threads, 50 connections, 10s)..."
wrk -t4 -c50 -d$DURATION -s benchmarks/add.lua "$BASE_URL/add" 2>&1 | grep -E "Requests/sec|Latency"
echo ""

sleep 1

echo "2. Testing Hybrid Search (4 threads, 50 connections, 10s)..."
wrk -t4 -c50 -d$DURATION -s benchmarks/search.lua "$BASE_URL/search" 2>&1 | grep -E "Requests/sec|Latency"
echo ""

sleep 1

echo "3. Testing Batch Add (2 threads, 10 connections, 10s)..."
wrk -t2 -c10 -d$DURATION -s benchmarks/batch_add.lua "$BASE_URL/add_batch" 2>&1 | grep -E "Requests/sec|Latency"
echo ""

echo "Quick test complete!"
