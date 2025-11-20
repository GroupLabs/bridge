#!/bin/bash
# High concurrency / High QPS benchmark test
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

BASE_URL="http://localhost:8080"
TEST_DURATION=30s

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Hybrid Search Benchmark Suite${NC}"
echo -e "${BLUE}  (SeekStorm-safe concurrency)${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Check if server is running
echo -e "${YELLOW}Checking server health...${NC}"
if ! curl -sf "$BASE_URL/health" > /dev/null; then
    echo -e "${RED}Error: Server not running at $BASE_URL${NC}"
    echo "Please start the server first:"
    echo "  export DYLD_LIBRARY_PATH=/opt/homebrew/opt/libomp/lib:\$DYLD_LIBRARY_PATH && ./target/release/core"
    exit 1
fi
echo -e "${GREEN}✓ Server is healthy${NC}\n"

# Clean up any corrupted index files from previous runs
echo -e "${YELLOW}Cleaning up previous test data...${NC}"
rm -rf indices/bench_d3 2>/dev/null || true
echo -e "${GREEN}✓ Cleanup complete${NC}\n"

# Setup test index
echo -e "${YELLOW}Setting up test index...${NC}"
curl -sf -X POST "$BASE_URL/create_index" \
    -H "Content-Type: application/json" \
    -d '{"name":"bench","dimension":3,"k":10}' > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Test index created${NC}\n"
else
    echo -e "${RED}✗ Failed to create index${NC}\n"
    exit 1
fi

# Pre-populate with test data
echo -e "${YELLOW}Pre-populating with 100 documents...${NC}"
for i in {1..100}; do
    curl -sf -X POST "$BASE_URL/add" \
        -H "Content-Type: application/json" \
        -d "{\"index\":\"bench_d3\",\"text\":\"test document $i\",\"vector\":[1.0,2.0,3.0]}" > /dev/null &
done
wait
echo -e "${GREEN}✓ Pre-populated with 100 documents${NC}\n"

sleep 2

# Test 1: Hybrid Search - SeekStorm-safe concurrency
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Test 1: Hybrid Search (Moderate Load)${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${YELLOW}Threads: 2, Connections: 10, Duration: $TEST_DURATION${NC}\n"
wrk -t2 -c10 -d$TEST_DURATION -s benchmarks/search.lua "$BASE_URL/search"
echo ""

sleep 2

# Test 2: Single Document Add - SeekStorm-safe concurrency
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Test 2: Single Add (Moderate Load)${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${YELLOW}Threads: 2, Connections: 10, Duration: $TEST_DURATION${NC}\n"
wrk -t2 -c10 -d$TEST_DURATION -s benchmarks/add.lua "$BASE_URL/add"
echo ""

sleep 2

# Test 3: Batch Add - SeekStorm-safe concurrency
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Test 3: Batch Add (10 docs/batch)${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${YELLOW}Threads: 2, Connections: 5, Duration: $TEST_DURATION${NC}"
echo -e "${YELLOW}(10 documents per batch)${NC}\n"
wrk -t2 -c5 -d$TEST_DURATION -s benchmarks/batch_add.lua "$BASE_URL/add_batch"
echo ""

sleep 2

# Test 4: Health Check Baseline
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Test 4: Health Check Baseline${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${YELLOW}Threads: 4, Connections: 100, Duration: 10s${NC}\n"
wrk -t4 -c100 -d10s "$BASE_URL/health"
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  High Concurrency Tests Complete${NC}"
echo -e "${BLUE}========================================${NC}\n"

echo -e "${GREEN}All tests completed!${NC}"
echo -e "${YELLOW}Expected performance (Hybrid FAISS + SeekStorm):${NC}"
echo -e "  - Hybrid Search:  ~500-800 req/s (at 10 concurrent connections)"
echo -e "  - Single Add:     ~800-1,200 req/s (at 10 concurrent connections)"
echo -e "  - Batch Add:      ~5,000-10,000 docs/s (at 5 concurrent connections)"
echo -e "  - Health Check:   ~50,000+ req/s"
echo ""
echo -e "${YELLOW}⚠️  SeekStorm 1.0 Concurrency Limitation:${NC}"
echo -e "  - Race condition at index.rs:3875 (.unwrap() on empty shard_queue)"
echo -e "  - Safe concurrency: ≤10 connections for writes, ≤20 for reads"
echo -e "  - High concurrency (100+ connections) causes panics and crashes"
echo -e "  - Issue reported to SeekStorm maintainers"
echo ""
echo -e "${YELLOW}For maximum throughput, increase concurrency after SeekStorm fix${NC}"
