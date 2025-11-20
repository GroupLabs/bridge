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
echo -e "${MAGENTA}  REALISTIC PERFORMANCE TEST${NC}"
echo -e "${MAGENTA}  100K docs × 4096D vectors${NC}"
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
rm -rf indices/bench_d4096 2>/dev/null || true
echo -e "${GREEN}✓ Cleanup complete${NC}\n"

# Setup test index
echo -e "${YELLOW}Setting up test index (4096D)...${NC}"
curl -sf -X POST "$BASE_URL/create_index" \
    -H "Content-Type: application/json" \
    -d '{"name":"bench","dimension":4096,"k":10}' > /dev/null 2>&1
echo -e "${GREEN}✓ Test index created${NC}\n"

# Pre-populate with test data using Python
echo -e "${YELLOW}Pre-populating with 100,000 documents (4096D vectors)...${NC}"
echo -e "${YELLOW}This will take a few minutes...${NC}\n"
python3 benchmarks/realistic_benchmark.py populate
echo -e "${GREEN}✓ Pre-population complete${NC}\n"

sleep 2

# Test 1: Hybrid Search - Max Concurrency for Reads
echo -e "${MAGENTA}========================================${NC}"
echo -e "${MAGENTA}Test 1: Hybrid Search (50 connections)${NC}"
echo -e "${MAGENTA}========================================${NC}"
echo -e "${YELLOW}Threads: 8, Connections: 50, Duration: $TEST_DURATION${NC}\n"
wrk -t8 -c50 -d$TEST_DURATION -s benchmarks/search_4096d.lua "$BASE_URL/search"
echo ""

sleep 2

# Test 2: Hybrid Search - Even Higher
echo -e "${MAGENTA}========================================${NC}"
echo -e "${MAGENTA}Test 2: Hybrid Search (100 connections)${NC}"
echo -e "${MAGENTA}========================================${NC}"
echo -e "${YELLOW}Threads: 12, Connections: 100, Duration: $TEST_DURATION${NC}\n"
wrk -t12 -c100 -d$TEST_DURATION -s benchmarks/search_4096d.lua "$BASE_URL/search"
echo ""

sleep 2

# Test 3: Single Add - Max Throughput (serialized by semaphore)
echo -e "${MAGENTA}========================================${NC}"
echo -e "${MAGENTA}Test 3: Single Add (50 connections)${NC}"
echo -e "${MAGENTA}========================================${NC}"
echo -e "${YELLOW}Threads: 8, Connections: 50, Duration: $TEST_DURATION${NC}\n"
wrk -t8 -c50 -d$TEST_DURATION -s benchmarks/add_4096d.lua "$BASE_URL/add"
echo ""

sleep 2

# Summary
echo -e "${MAGENTA}========================================${NC}"
echo -e "${MAGENTA}  REALISTIC BENCHMARK COMPLETE${NC}"
echo -e "${MAGENTA}========================================${NC}\n"

echo -e "${GREEN}All tests completed!${NC}"
echo -e "${YELLOW}Configuration: 100K documents, 4096D vectors${NC}"
echo ""
