-- wrk script for benchmarking VECTOR-ONLY search (bypasses SeekStorm)
-- Usage: wrk -t4 -c100 -d30s -s benchmarks/vector_only.lua http://localhost:8080/search

-- Search query templates with vector_weight=1.0, text_weight=0.0 (vector-only)
local queries = {
    {vec = {1.5, 2.5, 3.5}},
    {vec = {2.0, 3.0, 4.0}},
    {vec = {1.0, 2.0, 3.0}},
    {vec = {3.0, 4.0, 5.0}},
    {vec = {2.5, 3.5, 4.5}},
    {vec = {1.8, 2.8, 3.8}},
    {vec = {2.2, 3.2, 4.2}},
    {vec = {1.7, 2.7, 3.7}},
    {vec = {2.3, 3.3, 4.3}},
    {vec = {1.9, 2.9, 3.9}}
}

-- Generate request
function request()
    local query = queries[math.random(#queries)]

    local body = string.format([[{
        "index":"bench_d3",
        "vector_query":[%.2f,%.2f,%.2f],
        "text_query":"",
        "vector_weight":1.0,
        "text_weight":0.0,
        "k":10
    }]], query.vec[1], query.vec[2], query.vec[3])

    return wrk.format("POST", "/search",
        {["Content-Type"] = "application/json"},
        body)
end

function response(status, headers, body)
    if status ~= 200 then
        print("Error: " .. status .. " - " .. body)
    end
end

-- Print custom stats
function done(summary, latency, requests)
    io.write("\n--- Vector-Only Search Performance ---\n")
    io.write(string.format("  Requests/sec:   %.2f\n", summary.requests / (summary.duration / 1000000)))
    io.write(string.format("  Avg Latency:    %.2f ms\n", latency.mean / 1000))
    io.write(string.format("  P50 Latency:    %.2f ms\n", latency:percentile(50) / 1000))
    io.write(string.format("  P95 Latency:    %.2f ms\n", latency:percentile(95) / 1000))
    io.write(string.format("  P99 Latency:    %.2f ms\n", latency:percentile(99) / 1000))
    io.write(string.format("  Max Latency:    %.2f ms\n", latency.max / 1000))
end
