use std::env;
use std::path::PathBuf;

fn main() {
    // Get the project root directory (works on any machine)
    let manifest_dir = env::var("CARGO_MANIFEST_DIR").unwrap();

    // Add the directory containing FAISS libraries to the library search path
    println!("cargo:rustc-link-search=native={}/faiss/build/c_api", manifest_dir);
    println!("cargo:rustc-link-search=native={}/faiss/build/faiss", manifest_dir);

    // Link against FAISS libraries (dynamic linking)
    println!("cargo:rustc-link-lib=dylib=faiss_c");
    println!("cargo:rustc-link-lib=dylib=faiss");

    // Link against C++ standard library (required for static FAISS)
    println!("cargo:rustc-link-lib=dylib=c++");

    // Link against OpenMP (required for FAISS parallelism)
    // Path is configured in .cargo/config.toml via LIBOMP_PATH
    let libomp_path = env::var("LIBOMP_PATH").unwrap_or_else(|_| "/opt/homebrew/opt/libomp/lib".to_string());
    println!("cargo:rustc-link-search=native={}", libomp_path);
    println!("cargo:rustc-link-lib=dylib=omp");

    // Link against Apple's Accelerate framework (provides BLAS/LAPACK)
    println!("cargo:rustc-link-lib=framework=Accelerate");

    // Set rpath so binaries find FAISS libraries at runtime
    // Use absolute paths for reliability
    println!("cargo:rustc-link-arg=-Wl,-rpath,{}/faiss/build/faiss", manifest_dir);
    println!("cargo:rustc-link-arg=-Wl,-rpath,{}/faiss/build/c_api", manifest_dir);
    println!("cargo:rustc-link-arg=-Wl,-rpath,{}", libomp_path);

    // Generate bindings for the FAISS C API
    let bindings = bindgen::Builder::default()
        .header("faiss/c_api/Index_c.h")
        .header("faiss/c_api/IndexFlat_c.h")
        .header("faiss/c_api/clone_index_c.h")
        .header("faiss/c_api/index_factory_c.h")
        .header("faiss/c_api/index_io_c.h")
        .header("faiss/c_api/AutoTune_c.h")
        .header("faiss/c_api/error_c.h")
        .header("faiss/c_api/IndexIVF_c.h")
        .clang_arg("-I./faiss/c_api") // Path to FAISS headers
        .allowlist_function("^faiss_.*") // Include all functions starting with 'faiss_'
        .allowlist_type("^Faiss.*") // Include all types starting with 'Faiss'
        .allowlist_var("^METRIC_.*") // Include all variables like METRIC_L2
        .generate()
        .expect("Unable to generate bindings");

    // Write the bindings to the $OUT_DIR/bindings.rs
    let out_path = PathBuf::from(env::var("OUT_DIR").unwrap());
    bindings
        .write_to_file(out_path.join("bindings.rs"))
        .expect("Couldn't write bindings!");
}
