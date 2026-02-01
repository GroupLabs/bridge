
Model Execution (Triton inference server / Mesh)

  Colpali embedding
  Rerankers

  Vector Search
    Scann
    TF C++


Core (Rust)
  connects [Model Execution] (if "Triton inference server" 'c++ api' else grpc )

  Ingest data
    Embedding

  Search
    Vector Search
      Faiss
        C++ -> Rust (bindings)
      Scann
        grpc to model execution
    Text Search
      Seekstorm
        Rust
    Hybrid
      RRF
    Reranking


# Build Instructions

## Prerequisites

Install required dependencies:
```bash
brew install libomp gflags
```

For Rust:
- Requires cargo@1.82 or higher

## Build FAISS

The FAISS library has been extended with custom SearchParametersHNSW C API support for runtime efSearch configuration.

```bash
cd faiss/

# Configure FAISS build with OpenMP support
cmake -B build . \
  -DFAISS_ENABLE_GPU=OFF \
  -DFAISS_ENABLE_PYTHON=OFF \
  -DBUILD_SHARED_LIBS=ON \
  -DFAISS_ENABLE_C_API=ON \
  -DCMAKE_BUILD_TYPE=Release \
  -DOpenMP_C_FLAGS="-Xpreprocessor -fopenmp -I/opt/homebrew/opt/libomp/include" \
  -DOpenMP_C_LIB_NAMES="omp" \
  -DOpenMP_CXX_FLAGS="-Xpreprocessor -fopenmp -I/opt/homebrew/opt/libomp/include" \
  -DOpenMP_CXX_LIB_NAMES="omp" \
  -DOpenMP_omp_LIBRARY=/opt/homebrew/opt/libomp/lib/libomp.dylib

# Build FAISS library and C API (skip tests)
make -C build faiss faiss_c -j4

cd ..
```

Note: Uses system Apple Clang by default. If you have LLVM installed, you can optionally specify:
- `-DCMAKE_C_COMPILER=/opt/homebrew/opt/llvm/bin/clang`
- `-DCMAKE_CXX_COMPILER=/opt/homebrew/opt/llvm/bin/clang++`

**Intel Mac users**: Replace `/opt/homebrew/opt/libomp` with `/usr/local/opt/libomp` in the cmake command above.

## Build Bridge (Core)

```bash
cd core/

# Configure local library paths (one-time setup)
cp .cargo/config.toml.example .cargo/config.toml
# Intel Mac users: edit LIBOMP_PATH to /usr/local/opt/libomp/lib

# Build in release mode (required for SeekStorm performance)
cargo build --release
```

Only runs in release mode for some reason (https://github.com/SeekStorm/SeekStorm/issues/20)

## Run Bridge

```bash
./target/release/core
```

No environment variables needed - library paths are embedded in the binary at build time.

## Profiling with Apple Instruments

The binary can be profiled directly with Instruments without any environment setup:
1. Open Instruments
2. Choose Time Profiler template
3. Select `target/release/core` as the target
4. Start recording

## Troubleshooting

If release build fails on Mac:
```bash
# Make sure Xcode CLI tools are installed
xcode-select --install

# In your shell, override CC and CXX to Apple Clang
export CC=clang
export CXX=clang++

# Then build again
cargo build --release
```

If you get "Library not loaded" errors at runtime:
```bash
# Verify rpath is embedded in the binary
otool -l target/release/core | grep -A2 LC_RPATH

# Should show paths like:
#   @executable_path/../../faiss/build/faiss
#   @executable_path/../../faiss/build/c_api
#   /opt/homebrew/opt/libomp/lib

# If missing, rebuild after setting up .cargo/config.toml
```

## Configuration Notes

- HNSW efSearch is configured at runtime via SearchParametersHNSW (currently set to 128 for production quality)
- efSearch=128 provides 95%+ recall with good performance (~3,350 req/s for hybrid search)
- No FAISS source modifications required - all configuration done through C API

many vectors, single text -> some algorithms can accept multiple query vectors per query
