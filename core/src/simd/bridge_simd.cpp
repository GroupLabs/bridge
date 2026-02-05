// SIMD-optimized distance functions for Bridge vector search
// Supports: AVX2 (x86_64), NEON (ARM64), and scalar fallback

#include "bridge_simd.h"

// Detect architecture and include appropriate headers
#if defined(__x86_64__) || defined(_M_X64)
    #include <immintrin.h>
    #define USE_AVX2 1
#elif defined(__aarch64__) || defined(_M_ARM64)
    #include <arm_neon.h>
    #define USE_NEON 1
#endif

// ============== AVX2 Implementation (x86_64) ==============
#ifdef USE_AVX2

// Process 32 int8 elements at a time using AVX2
// Strategy: load 32 bytes, widen to 16-bit, compute squared differences, accumulate
static int32_t bridge_l2_distance_i8_avx2(const int8_t* a, const int8_t* b, size_t dim) {
    __m256i sum = _mm256_setzero_si256();

    size_t i = 0;
    // Process 32 elements at a time
    for (; i + 32 <= dim; i += 32) {
        // Load 32 int8 values
        __m256i va = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(a + i));
        __m256i vb = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(b + i));

        // Split into low and high 128-bit halves
        __m128i va_lo = _mm256_castsi256_si128(va);
        __m128i va_hi = _mm256_extracti128_si256(va, 1);
        __m128i vb_lo = _mm256_castsi256_si128(vb);
        __m128i vb_hi = _mm256_extracti128_si256(vb, 1);

        // Widen to 16-bit (signed extension)
        __m256i va16_lo = _mm256_cvtepi8_epi16(va_lo);
        __m256i va16_hi = _mm256_cvtepi8_epi16(va_hi);
        __m256i vb16_lo = _mm256_cvtepi8_epi16(vb_lo);
        __m256i vb16_hi = _mm256_cvtepi8_epi16(vb_hi);

        // Compute differences
        __m256i diff_lo = _mm256_sub_epi16(va16_lo, vb16_lo);
        __m256i diff_hi = _mm256_sub_epi16(va16_hi, vb16_hi);

        // Square and accumulate using madd (a*a + b*b for adjacent pairs)
        // madd_epi16 multiplies pairs and adds horizontally to 32-bit
        __m256i sq_lo = _mm256_madd_epi16(diff_lo, diff_lo);
        __m256i sq_hi = _mm256_madd_epi16(diff_hi, diff_hi);

        // Accumulate
        sum = _mm256_add_epi32(sum, sq_lo);
        sum = _mm256_add_epi32(sum, sq_hi);
    }

    // Process 16 elements if remaining
    if (i + 16 <= dim) {
        __m128i va = _mm_loadu_si128(reinterpret_cast<const __m128i*>(a + i));
        __m128i vb = _mm_loadu_si128(reinterpret_cast<const __m128i*>(b + i));

        // Widen to 16-bit
        __m256i va16 = _mm256_cvtepi8_epi16(va);
        __m256i vb16 = _mm256_cvtepi8_epi16(vb);

        // Compute differences and square
        __m256i diff = _mm256_sub_epi16(va16, vb16);
        __m256i sq = _mm256_madd_epi16(diff, diff);

        sum = _mm256_add_epi32(sum, sq);
        i += 16;
    }

    // Horizontal sum of 8 x 32-bit integers
    __m128i sum128 = _mm_add_epi32(
        _mm256_castsi256_si128(sum),
        _mm256_extracti128_si256(sum, 1)
    );
    // sum128 now has 4 x 32-bit values
    sum128 = _mm_hadd_epi32(sum128, sum128);  // 2 values
    sum128 = _mm_hadd_epi32(sum128, sum128);  // 1 value
    int32_t result = _mm_cvtsi128_si32(sum128);

    // Handle remainder
    for (; i < dim; i++) {
        int32_t d = static_cast<int32_t>(a[i]) - static_cast<int32_t>(b[i]);
        result += d * d;
    }

    return result;
}

#endif // USE_AVX2

// ============== NEON Implementation (ARM64) ==============
#ifdef USE_NEON

// Process 16 int8 elements at a time using NEON
static int32_t bridge_l2_distance_i8_neon(const int8_t* a, const int8_t* b, size_t dim) {
    int32x4_t sum0 = vdupq_n_s32(0);
    int32x4_t sum1 = vdupq_n_s32(0);
    int32x4_t sum2 = vdupq_n_s32(0);
    int32x4_t sum3 = vdupq_n_s32(0);

    size_t i = 0;
    // Process 16 elements at a time
    for (; i + 16 <= dim; i += 16) {
        // Load 16 int8 values
        int8x16_t va = vld1q_s8(a + i);
        int8x16_t vb = vld1q_s8(b + i);

        // Widen lower 8 elements to 16-bit and compute difference
        int16x8_t diff_lo = vsubl_s8(vget_low_s8(va), vget_low_s8(vb));
        // Widen upper 8 elements to 16-bit and compute difference
        int16x8_t diff_hi = vsubl_high_s8(va, vb);

        // Square and widen to 32-bit, then accumulate
        // Process diff_lo (8 elements -> 4+4)
        sum0 = vmlal_s16(sum0, vget_low_s16(diff_lo), vget_low_s16(diff_lo));
        sum1 = vmlal_high_s16(sum1, diff_lo, diff_lo);

        // Process diff_hi (8 elements -> 4+4)
        sum2 = vmlal_s16(sum2, vget_low_s16(diff_hi), vget_low_s16(diff_hi));
        sum3 = vmlal_high_s16(sum3, diff_hi, diff_hi);
    }

    // Combine partial sums
    int32x4_t sum = vaddq_s32(vaddq_s32(sum0, sum1), vaddq_s32(sum2, sum3));

    // Horizontal sum
    int32_t result = vaddvq_s32(sum);

    // Handle remainder
    for (; i < dim; i++) {
        int32_t d = static_cast<int32_t>(a[i]) - static_cast<int32_t>(b[i]);
        result += d * d;
    }

    return result;
}

#endif // USE_NEON

// ============== Scalar Fallback ==============
static int32_t bridge_l2_distance_i8_scalar(const int8_t* a, const int8_t* b, size_t dim) {
    // Use 4 accumulators to break dependency chain
    int32_t sum0 = 0, sum1 = 0, sum2 = 0, sum3 = 0;

    size_t i = 0;
    size_t chunks = dim / 4;
    for (size_t c = 0; c < chunks; c++) {
        int32_t d0 = static_cast<int32_t>(a[i]) - static_cast<int32_t>(b[i]);
        int32_t d1 = static_cast<int32_t>(a[i+1]) - static_cast<int32_t>(b[i+1]);
        int32_t d2 = static_cast<int32_t>(a[i+2]) - static_cast<int32_t>(b[i+2]);
        int32_t d3 = static_cast<int32_t>(a[i+3]) - static_cast<int32_t>(b[i+3]);
        sum0 += d0 * d0;
        sum1 += d1 * d1;
        sum2 += d2 * d2;
        sum3 += d3 * d3;
        i += 4;
    }

    // Handle remainder
    for (; i < dim; i++) {
        int32_t d = static_cast<int32_t>(a[i]) - static_cast<int32_t>(b[i]);
        sum0 += d * d;
    }

    return sum0 + sum1 + sum2 + sum3;
}

// ============== Public API ==============
extern "C" {

int32_t bridge_l2_distance_i8(const int8_t* a, const int8_t* b, size_t dim) {
#ifdef USE_AVX2
    return bridge_l2_distance_i8_avx2(a, b, dim);
#elif defined(USE_NEON)
    return bridge_l2_distance_i8_neon(a, b, dim);
#else
    return bridge_l2_distance_i8_scalar(a, b, dim);
#endif
}

void bridge_l2_distances_i8_batch(
    const int8_t* query,
    const int8_t* vectors,
    size_t dim,
    size_t n,
    int32_t* distances
) {
    for (size_t i = 0; i < n; i++) {
        distances[i] = bridge_l2_distance_i8(query, vectors + i * dim, dim);
    }
}

int bridge_simd_type(void) {
#ifdef USE_AVX2
    return 2;  // AVX2
#elif defined(USE_NEON)
    return 1;  // NEON
#else
    return 0;  // Scalar
#endif
}

} // extern "C"
