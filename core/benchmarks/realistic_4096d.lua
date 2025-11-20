-- Lua helper to generate 4096D vectors for wrk benchmarks
-- Note: Generates random normalized vectors

function generate_vector_4096d()
    local vec = {}
    local sum_sq = 0

    -- Generate random components
    for i = 1, 4096 do
        local val = (math.random() - 0.5) * 2  -- Range [-1, 1]
        vec[i] = val
        sum_sq = sum_sq + val * val
    end

    -- Normalize
    local norm = math.sqrt(sum_sq)
    for i = 1, 4096 do
        vec[i] = vec[i] / norm
    end

    -- Format as JSON array
    local parts = {}
    for i = 1, 4096 do
        parts[i] = string.format("%.6f", vec[i])
    end

    return "[" .. table.concat(parts, ",") .. "]"
end
