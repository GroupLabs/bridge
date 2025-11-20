-- wrk script for benchmarking hybrid search
-- Usage: wrk -t4 -c100 -d30s -s benchmarks/search.lua http://localhost:8080/search

-- Search query templates
local queries = {
    {text = "machine learning neural network", vec = {1.5, 2.5, 3.5}},
    {text = "vector search database index", vec = {2.0, 3.0, 4.0}},
    {text = "faiss similarity search", vec = {1.0, 2.0, 3.0}},
    {text = "text search engine optimization", vec = {3.0, 4.0, 5.0}},
    {text = "hybrid search algorithm", vec = {2.5, 3.5, 4.5}},
    {text = "semantic embedding model", vec = {1.8, 2.8, 3.8}},
    {text = "approximate nearest neighbor", vec = {2.2, 3.2, 4.2}},
    {text = "reciprocal rank fusion", vec = {1.7, 2.7, 3.7}},
    {text = "inverted index query", vec = {2.3, 3.3, 4.3}},
    {text = "rust async performance", vec = {1.9, 2.9, 3.9}}
}

-- Generate request
function request()
    local query = queries[math.random(#queries)]

    local body = string.format([[{
        "index":"bench_d3",
        "vector_query":[%.2f,%.2f,%.2f],
        "text_query":"%s",
        "vector_weight":0.6,
        "text_weight":0.4,
        "k":10
    }]], query.vec[1], query.vec[2], query.vec[3], query.text)

    return wrk.format("POST", "/search",
        {["Content-Type"] = "application/json"},
        body)
end

-- Track latency stats
local latencies = {}

function response(status, headers, body)
    if status ~= 200 then
        print("Error: " .. status .. " - " .. body)
    end
end

-- Print custom stats
function done(summary, latency, requests)
    io.write("\n--- Hybrid Search Performance ---\n")
    io.write(string.format("  Requests/sec:   %.2f\n", summary.requests / (summary.duration / 1000000)))
    io.write(string.format("  Avg Latency:    %.2f ms\n", latency.mean / 1000))
    io.write(string.format("  P50 Latency:    %.2f ms\n", latency:percentile(50) / 1000))
    io.write(string.format("  P95 Latency:    %.2f ms\n", latency:percentile(95) / 1000))
    io.write(string.format("  P99 Latency:    %.2f ms\n", latency:percentile(99) / 1000))
    io.write(string.format("  Max Latency:    %.2f ms\n", latency.max / 1000))
end
