
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


install llvm libomp gcc gflags

in faiss/

cmake -B build . \
  -DFAISS_ENABLE_GPU=OFF \
  -DFAISS_ENABLE_PYTHON=OFF \
  -DBUILD_SHARED_LIBS=ON \
  -DFAISS_ENABLE_C_API=ON \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER=/opt/homebrew/opt/llvm/bin/clang \
  -DCMAKE_CXX_COMPILER=/opt/homebrew/opt/llvm/bin/clang++

make -C build

export DYLD_LIBRARY_PATH=/Users/noelthomas/Documents/GitHub/grouplabs/bridge/core/faiss/build/faiss:/Users/noelthomas/Documents/GitHub/grouplabs/bridge/core/faiss/build/c_api:/opt/homebrew/opt/libomp/lib:$DYLD_LIBRARY_PATH

in core/

cargo run --release

OR:

export DYLD_LIBRARY_PATH=$(pwd)/faiss/build/faiss:$(pwd)/faiss/build/c_api:/opt/homebrew/opt/
  libomp/lib:$DYLD_LIBRARY_PATH && cargo run --release

Only runs in release mode for some reason (https://github.com/SeekStorm/SeekStorm/issues/20)

If release does not build on Mac, you may need to do:
```
# Make sure Xcode CLI tools are installed
xcode-select --install

# In your shell, override CC and CXX to Apple Clang
export CC=clang
export CXX=clang++

# Then build again
cargo build --release
```

Requires cargo@1.82 or higher

many vectors, single text -> some algorithms can accept multiple query vectors per query
