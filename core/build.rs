use std::env;
use std::path::PathBuf;

fn main() {
    // Get the project root directory (works on any machine)
    let manifest_dir = env::var("CARGO_MANIFEST_DIR").unwrap();
    let out_path = PathBuf::from(env::var("OUT_DIR").unwrap());

    // Compile bridge_simd.cpp with SIMD optimizations
    let mut simd_build = cc::Build::new();
    simd_build
        .cpp(true)
        .flag("-std=c++11")
        .file("src/simd/bridge_simd.cpp")
        .opt_level(3);

    // Add architecture-specific flags
    let target_arch = env::var("CARGO_CFG_TARGET_ARCH").unwrap_or_default();
    if target_arch == "x86_64" {
        simd_build.flag("-mavx2");
        simd_build.flag("-mfma");
    }
    // ARM NEON is enabled by default on aarch64

    simd_build.compile("bridge_simd");

    // Pass the static library directly to the linker
    // Using rustc-link-arg because rustc-link-lib doesn't seem to propagate to bin targets
    let simd_lib_path = out_path.join("libbridge_simd.a");
    println!("cargo:rustc-link-arg={}", simd_lib_path.display());

    println!("cargo:rerun-if-changed=src/simd/bridge_simd.cpp");
    println!("cargo:rerun-if-changed=src/simd/bridge_simd.h");

    // Add the directory containing FAISS libraries to the library search path
    println!("cargo:rustc-link-search=native={}/faiss/build/c_api", manifest_dir);
    println!("cargo:rustc-link-search=native={}/faiss/build/faiss", manifest_dir);
    // Also check /usr/local/lib for system-installed FAISS
    println!("cargo:rustc-link-search=native=/usr/local/lib");

    // Link against FAISS libraries (dynamic linking)
    println!("cargo:rustc-link-lib=dylib=faiss_c");
    println!("cargo:rustc-link-lib=dylib=faiss");

    // Link against C++ standard library (required for static FAISS)
    let target_os = env::var("CARGO_CFG_TARGET_OS").unwrap_or_default();
    if target_os == "macos" {
        println!("cargo:rustc-link-lib=dylib=c++");
    } else {
        println!("cargo:rustc-link-lib=dylib=stdc++");
    }

    // Link against OpenMP (required for FAISS parallelism)
    if target_os == "macos" {
        let libomp_path = env::var("LIBOMP_PATH").unwrap_or_else(|_| "/opt/homebrew/opt/libomp/lib".to_string());
        println!("cargo:rustc-link-search=native={}", libomp_path);
        println!("cargo:rustc-link-lib=dylib=omp");
        println!("cargo:rustc-link-arg=-Wl,-rpath,{}", libomp_path);
        // Link against Apple's Accelerate framework (provides BLAS/LAPACK)
        println!("cargo:rustc-link-lib=framework=Accelerate");
    } else {
        // Linux: OpenMP is typically gomp, and BLAS is openblas
        println!("cargo:rustc-link-lib=dylib=gomp");
        println!("cargo:rustc-link-lib=dylib=openblas");
    }

    // Set rpath so binaries find FAISS libraries at runtime
    println!("cargo:rustc-link-arg=-Wl,-rpath,{}/faiss/build/faiss", manifest_dir);
    println!("cargo:rustc-link-arg=-Wl,-rpath,{}/faiss/build/c_api", manifest_dir);

    // Generate bindings for the FAISS C API
    let faiss_bindings = bindgen::Builder::default()
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
        .expect("Unable to generate FAISS bindings");

    faiss_bindings
        .write_to_file(out_path.join("bindings.rs"))
        .expect("Couldn't write FAISS bindings!");

    // FoundationDB bindings (only when fdb feature is enabled)
    #[cfg(feature = "fdb")]
    {
        let fdb_include_path = format!("{}/foundationdb/bindings/c", manifest_dir);
        let fdb_lib_path = format!("{}/foundationdb/build/lib", manifest_dir);

        // Link against FDB client library
        println!("cargo:rustc-link-search=native={}", fdb_lib_path);
        println!("cargo:rustc-link-lib=dylib=fdb_c");
        println!("cargo:rustc-link-arg=-Wl,-rpath,{}", fdb_lib_path);

        // Generate FDB bindings
        let fdb_bindings = bindgen::Builder::default()
            .header(format!("{}/foundationdb/fdb_c.h", fdb_include_path))
            .clang_arg(format!("-I{}", fdb_include_path))
            .allowlist_function("^fdb_.*")
            .allowlist_type("^FDB.*")
            .allowlist_var("^FDB_.*")
            .generate()
            .expect("Unable to generate FDB bindings");

        fdb_bindings
            .write_to_file(out_path.join("fdb_bindings.rs"))
            .expect("Couldn't write FDB bindings!");

        println!("cargo:rerun-if-changed=foundationdb/bindings/c/foundationdb/fdb_c.h");
    }
}
