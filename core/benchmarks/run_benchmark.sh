#!/bin/bash
# Bridge Search Benchmark Runner
# Usage: ./run_benchmark.sh <index_name> <dimensions> [duration]
#
# Example:
#   ./run_benchmark.sh myindex_d128 128 30s
#   ./run_benchmark.sh myindex_d4096 4096 30s

set -e

INDEX_NAME=${1:-"test_d128"}
DIMS=${2:-128}
DURATION=${3:-30s}
BASE_URL="http://localhost:8080"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=============================================="
echo "Bridge Search Benchmark"
echo "=============================================="
echo "Index: $INDEX_NAME"
echo "Dimensions: $DIMS"
echo "Duration: $DURATION"
echo ""

# Check server health
if ! curl -s "$BASE_URL/health" > /dev/null; then
    echo "ERROR: Server not running at $BASE_URL"
    exit 1
fi

export INDEX_NAME DIMS

# Warmup
echo "Warming up (5s)..."
wrk -t4 -c32 -d5s -s "$SCRIPT_DIR/vector_search.lua" "$BASE_URL/search" > /dev/null 2>&1

echo ""
echo "=== Vector Search ==="
wrk -t8 -c64 -d$DURATION -s "$SCRIPT_DIR/vector_search.lua" "$BASE_URL/search" 2>&1 | grep -E "Latency|Requests/sec|Thread Stats"

echo ""
echo "=== Text Search ==="
wrk -t8 -c64 -d$DURATION -s "$SCRIPT_DIR/text_search.lua" "$BASE_URL/search" 2>&1 | grep -E "Latency|Requests/sec|Thread Stats"

echo ""
echo "=== Hybrid Search ==="
wrk -t8 -c64 -d$DURATION -s "$SCRIPT_DIR/hybrid_search.lua" "$BASE_URL/search" 2>&1 | grep -E "Latency|Requests/sec|Thread Stats"

echo ""
echo "=== Single-thread Latency ==="
echo "Vector (1 conn):"
wrk -t1 -c1 -d5s -s "$SCRIPT_DIR/vector_search.lua" "$BASE_URL/search" 2>&1 | grep "Latency"
echo "Text (1 conn):"
wrk -t1 -c1 -d5s -s "$SCRIPT_DIR/text_search.lua" "$BASE_URL/search" 2>&1 | grep "Latency"

echo ""
echo "Done!"
