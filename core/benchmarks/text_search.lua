-- Text-only search benchmark
-- Usage: wrk -t8 -c64 -d30s -s text_search.lua http://localhost:8080/search
-- Set INDEX_NAME environment variable or edit below

local index_name = os.getenv("INDEX_NAME") or "test_d128"

wrk.method = "POST"
wrk.headers["Content-Type"] = "application/json"

local counter = 0

request = function()
    counter = counter + 1
    return wrk.format("POST", "/search", nil,
        '{"index":"' .. index_name .. '","text_query":"d' .. (counter % 100000) .. '","k":10}')
end
