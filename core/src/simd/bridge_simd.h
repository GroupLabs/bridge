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

// L2 squared distance for float32 vectors
// Returns sum of (a[i] - b[i])^2
float bridge_l2_distance_f32(const float* a, const float* b, size_t dim);

// Batch L2 distances for float32: compute distance from query to n vectors
// vectors must be contiguous: vectors[i * dim + d] = vector i, dimension d
void bridge_l2_distances_f32_batch(
    const float* query,
    const float* vectors,
    size_t dim,
    size_t n,
    float* distances);

// Scatter-gather batch: compute distances for vectors at given indices
// indices[i] is the row index into contiguous vector storage
void bridge_l2_distances_f32_indexed(
    const float* query,
    const float* vectors,
    size_t dim,
    const size_t* indices,
    size_t n,
    float* distances);

// Check which SIMD implementation is being used
// Returns: 0 = scalar, 1 = NEON, 2 = AVX2
int bridge_simd_type(void);

#ifdef __cplusplus
}
#endif

#endif // BRIDGE_SIMD_H
