#ifndef BRIDGE_SIMD_H
#define BRIDGE_SIMD_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

// L2 squared distance for int8 vectors (SQ8)
// Returns sum of (a[i] - b[i])^2
int32_t bridge_l2_distance_i8(const int8_t* a, const int8_t* b, size_t dim);

// Batch L2 distances: compute distance from query to n vectors
// distances[i] = L2(query, vectors[i * dim])
void bridge_l2_distances_i8_batch(
    const int8_t* query,
    const int8_t* vectors,
    size_t dim,
    size_t n,
    int32_t* distances);

// Check which SIMD implementation is being used
// Returns: 0 = scalar, 1 = NEON, 2 = AVX2
int bridge_simd_type(void);

#ifdef __cplusplus
}
#endif

#endif // BRIDGE_SIMD_H
