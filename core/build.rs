use std::env;
use std::path::PathBuf;

fn main() {
    // Add the directory containing FAISS libraries to the library search path
    println!("cargo:rustc-link-search=native=/Users/noelthomas/Documents/GitHub/grouplabs/bridge/core/faiss/build/c_api");
    println!("cargo:rustc-link-search=native=/Users/noelthomas/Documents/GitHub/grouplabs/bridge/core/faiss/build/faiss");

    // Link against FAISS libraries (static linking)
    println!("cargo:rustc-link-lib=static=faiss_c");
    println!("cargo:rustc-link-lib=static=faiss");

    // Link against C++ standard library (required for static FAISS)
    println!("cargo:rustc-link-lib=dylib=c++");

    // Link against OpenMP (required for FAISS parallelism)
    println!("cargo:rustc-link-search=native=/opt/homebrew/opt/libomp/lib");
    println!("cargo:rustc-link-lib=dylib=omp");

    // Link against Apple's Accelerate framework (provides BLAS/LAPACK)
    println!("cargo:rustc-link-lib=framework=Accelerate");

    // Generate bindings for the FAISS C API
    let bindings = bindgen::Builder::default()
        .header("faiss/c_api/Index_c.h")
        .header("faiss/c_api/IndexFlat_c.h")
        .header("faiss/c_api/clone_index_c.h")
        .header("faiss/c_api/index_factory_c.h")
        .header("faiss/c_api/index_io_c.h")
        .header("faiss/c_api/AutoTune_c.h")
        .header("faiss/c_api/error_c.h")
        // Add other headers if needed
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
