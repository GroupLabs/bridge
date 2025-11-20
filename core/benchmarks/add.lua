-- wrk script for benchmarking document addition
-- Usage: wrk -t4 -c100 -d30s -s benchmarks/add.lua http://localhost:8080/add

-- Counter for generating unique documents
local counter = 0
local thread_id = 0

-- Initialize thread
function setup(thread)
    thread_id = thread_id + 1
    thread:set("id", thread_id)
end

-- Initialize per-thread counter
function init(args)
    counter = id * 1000000  -- Offset by thread ID to avoid collisions
end

-- Generate request
function request()
    counter = counter + 1

    -- Generate random vector (3 dimensions)
    local vec = string.format("[%.2f,%.2f,%.2f]",
        math.random() * 10,
        math.random() * 10,
        math.random() * 10)

    -- Generate text content with variety
    local texts = {
        "machine learning algorithm optimization",
        "deep neural network training data",
        "vector search hybrid database",
        "faiss similarity indexing performance",
        "seekstorm text search engine",
        "rust async tokio runtime",
        "reciprocal rank fusion algorithm",
        "semantic search embedding model",
        "approximate nearest neighbor query",
        "inverted index full text search"
    }
    local text = texts[math.random(#texts)]

    local body = string.format([[{
        "index":"bench_d3",
        "text":"%s %d",
        "vector":%s
    }]], text, counter, vec)

    return wrk.format("POST", "/add",
        {["Content-Type"] = "application/json"},
        body)
end

-- Response callback
function response(status, headers, body)
    if status ~= 200 then
        print("Error: " .. status .. " - " .. body)
    end
end
