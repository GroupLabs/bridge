#!/bin/bash
# Maximum performance stress test
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

BASE_URL="http://localhost:8080"
TEST_DURATION=30s

echo -e "${MAGENTA}========================================${NC}"
echo -e "${MAGENTA}  MAX PERFORMANCE STRESS TEST${NC}"
echo -e "${MAGENTA}  Finding Absolute Limits${NC}"
echo -e "${MAGENTA}========================================${NC}\n"

# Check if server is running
echo -e "${YELLOW}Checking server health...${NC}"
if ! curl -sf "$BASE_URL/health" > /dev/null; then
    echo -e "${RED}Error: Server not running at $BASE_URL${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Server is healthy${NC}\n"

# Clean up
echo -e "${YELLOW}Cleaning up previous test data...${NC}"
rm -rf indices/bench_d3 2>/dev/null || true
echo -e "${GREEN}✓ Cleanup complete${NC}\n"

# Setup test index
echo -e "${YELLOW}Setting up test index...${NC}"
curl -sf -X POST "$BASE_URL/create_index" \
    -H "Content-Type: application/json" \
    -d '{"name":"bench","dimension":3,"k":10}' > /dev/null 2>&1
echo -e "${GREEN}✓ Test index created${NC}\n"

# Pre-populate with test data
echo -e "${YELLOW}Pre-populating with 200 documents...${NC}"
for i in {1..200}; do
    curl -sf -X POST "$BASE_URL/add" \
        -H "Content-Type: application/json" \
        -d "{\"index\":\"bench_d3\",\"text\":\"test document $i\",\"vector\":[1.0,2.0,3.0]}" > /dev/null &
done
wait
echo -e "${GREEN}✓ Pre-populated with 200 documents${NC}\n"

sleep 2

# Test 1: Hybrid Search - Max Concurrency for Reads
echo -e "${MAGENTA}========================================${NC}"
echo -e "${MAGENTA}Test 1: Hybrid Search (MAX READS)${NC}"
echo -e "${MAGENTA}========================================${NC}"
echo -e "${YELLOW}Threads: 8, Connections: 50, Duration: $TEST_DURATION${NC}\n"
wrk -t8 -c50 -d$TEST_DURATION -s benchmarks/search.lua "$BASE_URL/search"
echo ""

sleep 2

# Test 2: Hybrid Search - Even Higher
echo -e "${MAGENTA}========================================${NC}"
echo -e "${MAGENTA}Test 2: Hybrid Search (EXTREME)${NC}"
echo -e "${MAGENTA}========================================${NC}"
echo -e "${YELLOW}Threads: 12, Connections: 100, Duration: $TEST_DURATION${NC}\n"
wrk -t12 -c100 -d$TEST_DURATION -s benchmarks/search.lua "$BASE_URL/search"
echo ""

sleep 2

# Test 3: Single Add - Max Throughput (serialized by semaphore)
echo -e "${MAGENTA}========================================${NC}"
echo -e "${MAGENTA}Test 3: Single Add (MAX WRITES)${NC}"
echo -e "${MAGENTA}========================================${NC}"
echo -e "${YELLOW}Threads: 8, Connections: 50, Duration: $TEST_DURATION${NC}\n"
wrk -t8 -c50 -d$TEST_DURATION -s benchmarks/add.lua "$BASE_URL/add"
echo ""

sleep 2

# Test 4: Batch Add - Max Batch Throughput
echo -e "${MAGENTA}========================================${NC}"
echo -e "${MAGENTA}Test 4: Batch Add (MAX BATCHES)${NC}"
echo -e "${MAGENTA}========================================${NC}"
echo -e "${YELLOW}Threads: 8, Connections: 20, Duration: $TEST_DURATION${NC}"
echo -e "${YELLOW}(10 documents per batch)${NC}\n"
wrk -t8 -c20 -d$TEST_DURATION -s benchmarks/batch_add.lua "$BASE_URL/add_batch"
echo ""

sleep 2

# Test 5: Vector-Only Search (bypass SeekStorm)
echo -e "${MAGENTA}========================================${NC}"
echo -e "${MAGENTA}Test 5: Vector-Only Search (FAISS MAX)${NC}"
echo -e "${MAGENTA}========================================${NC}"
echo -e "${YELLOW}Threads: 12, Connections: 100, Duration: $TEST_DURATION${NC}\n"
wrk -t12 -c100 -d$TEST_DURATION -s benchmarks/vector_only.lua "$BASE_URL/search"
echo ""

# Summary
echo -e "${MAGENTA}========================================${NC}"
echo -e "${MAGENTA}  MAX PERFORMANCE TEST COMPLETE${NC}"
echo -e "${MAGENTA}========================================${NC}\n"

echo -e "${GREEN}All extreme tests completed!${NC}"
echo -e "${YELLOW}Note: These tests push the system to its limits${NC}"
echo ""
