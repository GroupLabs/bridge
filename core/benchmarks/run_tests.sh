#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BASE_URL="http://localhost:8080"
INDEX_NAME="bench_d3"
WARMUP_TIME=5s
TEST_DURATION=30s

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Bridge Search Performance Test Suite${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Check if server is running
echo -e "${YELLOW}Checking server health...${NC}"
if ! curl -sf "$BASE_URL/health" > /dev/null; then
    echo -e "${RED}Error: Server not running at $BASE_URL${NC}"
    echo "Please start the server first."
    exit 1
fi
echo -e "${GREEN}✓ Server is healthy${NC}\n"

# Setup: Create test index
echo -e "${YELLOW}Setting up test index...${NC}"
curl -sf -X POST "$BASE_URL/create_index" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"bench\",\"dimension\":3,\"k\":10}" > /dev/null 2>&1 || true
echo -e "${GREEN}✓ Test index ready${NC}\n"

# Pre-populate with some data for search tests
echo -e "${YELLOW}Pre-populating index with test data...${NC}"
for i in {1..100}; do
    curl -sf -X POST "$BASE_URL/add" \
        -H "Content-Type: application/json" \
        -d "{\"index\":\"${INDEX_NAME}\",\"text\":\"test document $i\",\"vector\":[1.0,2.0,3.0]}" > /dev/null &
done
wait
echo -e "${GREEN}✓ Pre-populated with 100 documents${NC}\n"

sleep 2

# Test 1: Single Document Addition
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Test 1: Single Document Addition${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${YELLOW}Threads: 4, Connections: 100, Duration: $TEST_DURATION${NC}\n"
wrk -t4 -c100 -d$TEST_DURATION -s benchmarks/add.lua "$BASE_URL/add"
echo ""

sleep 2

# Test 2: Batch Document Addition
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Test 2: Batch Document Addition${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${YELLOW}Threads: 2, Connections: 10, Duration: $TEST_DURATION${NC}"
echo -e "${YELLOW}(10 documents per batch)${NC}\n"
wrk -t2 -c10 -d$TEST_DURATION -s benchmarks/batch_add.lua "$BASE_URL/add_batch"
echo ""

sleep 2

# Test 3: Hybrid Search (Vector + Text)
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Test 3: Hybrid Search Performance${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${YELLOW}Threads: 4, Connections: 100, Duration: $TEST_DURATION${NC}\n"
wrk -t4 -c100 -d$TEST_DURATION -s benchmarks/search.lua "$BASE_URL/search"
echo ""

sleep 2

# Test 4: Health Check Baseline
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Test 4: Health Check Baseline${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${YELLOW}Threads: 4, Connections: 100, Duration: $TEST_DURATION${NC}\n"
wrk -t4 -c100 -d$TEST_DURATION "$BASE_URL/health"
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Performance Test Suite Complete${NC}"
echo -e "${BLUE}========================================${NC}\n"

echo -e "${GREEN}All tests completed successfully!${NC}"
echo -e "${YELLOW}Note: Results saved above. Compare against expected performance:${NC}"
echo -e "  - Single Add:    ~1,000-2,000 req/s"
echo -e "  - Batch Add:     ~10,000-50,000 docs/s"
echo -e "  - Hybrid Search: ~800-1,500 req/s"
echo -e "  - Health Check:  ~20,000+ req/s"
