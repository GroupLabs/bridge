-- wrk script for benchmarking document addition with 4096D vectors
-- Usage: wrk -t8 -c50 -d30s -s benchmarks/add_4096d.lua http://localhost:8080/add

local counter = 0
local thread_id = 0

function setup(thread)
    thread_id = thread_id + 1
    thread:set("id", thread_id)
end

function init(args)
    counter = id * 10000000
end

-- Pre-generate a few random vectors for reuse
local function gen_vec()
    local vec = {}
    for i = 1, 4096 do
        vec[i] = string.format("%.4f", (math.random() - 0.5) * 2)
    end
    return "[" .. table.concat(vec, ",") .. "]"
end

local pregenerated_vecs = {}
for i = 1, 20 do
    pregenerated_vecs[i] = gen_vec()
end

function request()
    counter = counter + 1

    local vec = pregenerated_vecs[math.random(#pregenerated_vecs)]

    local texts = {
        "machine learning algorithm optimization",
        "deep neural network training data",
        "vector search hybrid database",
        "faiss similarity indexing performance",
        "seekstorm text search engine"
    }

    local body = string.format([[{
        "index":"bench_d4096",
        "text":"%s %d",
        "vector":%s
    }]], texts[math.random(#texts)], counter, vec)

    return wrk.format("POST", "/add",
        {["Content-Type"] = "application/json"},
        body)
end

function response(status, headers, body)
    if status ~= 200 then
        print("Error: " .. status .. " - " .. body)
    end
end
