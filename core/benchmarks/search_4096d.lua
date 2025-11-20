-- wrk script for benchmarking hybrid search with 4096D vectors
-- Usage: wrk -t8 -c50 -d30s -s benchmarks/search_4096d.lua http://localhost:8080/search

-- Pre-generate some 4096D vectors (simplified for wrk performance)
local function gen_vec()
    local vec = {}
    for i = 1, 4096 do
        vec[i] = string.format("%.4f", (math.random() - 0.5) * 2)
    end
    return "[" .. table.concat(vec, ",") .. "]"
end

-- Pre-generate vectors at startup (not per-request)
-- Using 100 vectors to force L3 cache misses (100 * 4096 * 4 bytes = ~1.6MB)
local query_vectors = {}
for i = 1, 100 do
    query_vectors[i] = gen_vec()
end

local query_texts = {
    "machine learning neural network",
    "vector search database index",
    "faiss similarity search",
    "text search engine optimization",
    "hybrid search algorithm",
    "semantic embedding model",
    "approximate nearest neighbor",
    "reciprocal rank fusion",
    "inverted index query",
    "rust async performance"
}

function request()
    local idx = math.random(#query_vectors)

    local body = string.format([[{
        "index":"bench_d4096",
        "vector_query":%s,
        "text_query":"%s",
        "vector_weight":0.6,
        "text_weight":0.4,
        "k":10
    }]], query_vectors[idx], query_texts[idx])

    return wrk.format("POST", "/search",
        {["Content-Type"] = "application/json"},
        body)
end

function response(status, headers, body)
    if status ~= 200 then
        print("Error: " .. status .. " - " .. body)
    end
end

function done(summary, latency, requests)
    io.write("\n--- Hybrid Search Performance (4096D) ---\n")
    io.write(string.format("  Requests/sec:   %.2f\n", summary.requests / (summary.duration / 1000000)))
    io.write(string.format("  Avg Latency:    %.2f ms\n", latency.mean / 1000))
    io.write(string.format("  P50 Latency:    %.2f ms\n", latency:percentile(50) / 1000))
    io.write(string.format("  P95 Latency:    %.2f ms\n", latency:percentile(95) / 1000))
    io.write(string.format("  P99 Latency:    %.2f ms\n", latency:percentile(99) / 1000))
    io.write(string.format("  Max Latency:    %.2f ms\n", latency.max / 1000))
end
