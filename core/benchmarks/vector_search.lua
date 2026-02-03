-- Vector-only search benchmark
-- Usage: wrk -t8 -c64 -d30s -s vector_search.lua http://localhost:8080/search
-- Set INDEX_NAME and DIMS environment variables or edit below

local index_name = os.getenv("INDEX_NAME") or "test_d128"
local dims = tonumber(os.getenv("DIMS")) or 128

math.randomseed(os.time())

local function gen_vec()
    local d = {}
    for i = 1, dims do
        d[i] = string.format("%.4f", math.random() * 2 - 1)
    end
    return "[" .. table.concat(d, ",") .. "]"
end

local vec = gen_vec()

wrk.method = "POST"
wrk.headers["Content-Type"] = "application/json"

request = function()
    return wrk.format("POST", "/search", nil,
        '{"index":"' .. index_name .. '","vector_query":' .. vec .. ',"k":10}')
end

local counter = 0
response = function(status, headers, body)
    counter = counter + 1
    if counter % 500 == 0 then
        vec = gen_vec()
    end
end
