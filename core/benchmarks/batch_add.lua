-- wrk script for benchmarking batch document addition
-- Usage: wrk -t2 -c10 -d30s -s benchmarks/batch_add.lua http://localhost:8080/add_batch

local counter = 0
local thread_id = 0

function setup(thread)
    thread_id = thread_id + 1
    thread:set("id", thread_id)
end

function init(args)
    counter = id * 10000000
end

-- Generate batch of documents (10 per request)
function request()
    local batch_size = 10
    local docs = {}

    for i = 1, batch_size do
        counter = counter + 1

        local vec = string.format("[%.2f,%.2f,%.2f]",
            math.random() * 10,
            math.random() * 10,
            math.random() * 10)

        local texts = {
            "distributed system architecture design",
            "concurrent programming parallel processing",
            "high performance computing cluster",
            "real-time data processing pipeline",
            "scalable microservices deployment",
            "cloud native application development",
            "container orchestration kubernetes",
            "message queue event streaming",
            "cache layer redis memcached",
            "load balancing traffic distribution"
        }

        table.insert(docs, string.format([[{
            "text":"%s %d",
            "vector":%s
        }]], texts[math.random(#texts)], counter, vec))
    end

    local body = string.format([[{
        "index":"bench_d3",
        "documents":[%s]
    }]], table.concat(docs, ","))

    return wrk.format("POST", "/add_batch",
        {["Content-Type"] = "application/json"},
        body)
end

function response(status, headers, body)
    if status ~= 200 then
        print("Error: " .. status)
    end
end

function done(summary, latency, requests)
    io.write("\n--- Batch Add Performance ---\n")
    io.write(string.format("  Total Batches:  %d\n", summary.requests))
    io.write(string.format("  Total Docs:     ~%d (10 per batch)\n", summary.requests * 10))
    io.write(string.format("  Batches/sec:    %.2f\n", summary.requests / (summary.duration / 1000000)))
    io.write(string.format("  Docs/sec:       ~%.2f\n", (summary.requests * 10) / (summary.duration / 1000000)))
    io.write(string.format("  Avg Latency:    %.2f ms\n", latency.mean / 1000))
    io.write(string.format("  P99 Latency:    %.2f ms\n", latency:percentile(99) / 1000))
end
