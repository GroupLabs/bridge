use std::env;
use std::path::PathBuf;

fn main() {
    // Add the directory containing `libfaiss_c.dylib` to the library search path
    println!("cargo:rustc-link-search=native=/Users/noelthomas/Documents/GitHub/bridge/core/faiss/build/c_api");

    // Tell the linker to link against `faiss_c` (remove the `lib` prefix and `.dylib` extension)
    println!("cargo:rustc-link-lib=dylib=faiss_c");

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
