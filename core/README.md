
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

## Build Bridge (Core)

```bash
cd core/

# Build in release mode (required for SeekStorm performance)
cargo build --release
```

Only runs in release mode for some reason (https://github.com/SeekStorm/SeekStorm/issues/20)

## Run Bridge

Set library paths and run:
```bash
export DYLD_LIBRARY_PATH=$(pwd)/faiss/build/faiss:$(pwd)/faiss/build/c_api:/opt/homebrew/opt/libomp/lib:$DYLD_LIBRARY_PATH

./target/release/core
```

Or in one line:
```bash
export DYLD_LIBRARY_PATH=$(pwd)/faiss/build/faiss:$(pwd)/faiss/build/c_api:/opt/homebrew/opt/libomp/lib:$DYLD_LIBRARY_PATH && cargo run --release
```

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

## Configuration Notes

- HNSW efSearch is configured at runtime via SearchParametersHNSW (currently set to 128 for production quality)
- efSearch=128 provides 95%+ recall with good performance (~3,350 req/s for hybrid search)
- No FAISS source modifications required - all configuration done through C API

many vectors, single text -> some algorithms can accept multiple query vectors per query
