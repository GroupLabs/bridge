#[allow(non_upper_case_globals)] // suppress non upper case globals warning
#[allow(non_camel_case_types)] // suppress non camel case warning
#[allow(dead_code)] // suppress function not used warning
mod bindings {
    include!(concat!(env!("OUT_DIR"), "/bindings.rs"));
}

use bindings::*;
use libc::{c_float, c_int, c_longlong};
use rand::Rng;
use std::ffi::CString;
use std::ptr;

fn main() {
    unsafe {
        // Define the dimension and metric
        let d: c_int = 4096; // Dimension of the vectors
        let nb: c_longlong = 10000; // Number of database vectors
        let nq: c_longlong = 10; // Number of query vectors
        let k: c_longlong = 5; // Number of nearest neighbors to retrieve

        let metric_description = CString::new("Flat").unwrap();

        // Create the index using faiss_index_factory
        let mut index: *mut FaissIndex = ptr::null_mut();
        let status = faiss_index_factory(
            &mut index,
            d,
            metric_description.as_ptr(),
            FaissMetricType_METRIC_L2,
        );

        if status != 0 {
            let error = faiss_get_last_error();
            let error_message = std::ffi::CStr::from_ptr(error).to_string_lossy();
            eprintln!("Error creating FAISS index: {}", error_message);
            return;
        }

        println!("FAISS index created successfully.");

        // Generate random database vectors
        let mut rng = rand::thread_rng();
        let xb: Vec<c_float> = (0..(nb * d as c_longlong))
            .map(|_| rng.gen_range(0.0..1.0))
            .collect();

        // Add vectors to the index
        let add_status = faiss_Index_add(index, nb, xb.as_ptr());

        if add_status != 0 {
            let error = faiss_get_last_error();
            let error_message = std::ffi::CStr::from_ptr(error).to_string_lossy();
            eprintln!("Error adding vectors to FAISS index: {}", error_message);
            faiss_Index_free(index);
            return;
        }

        println!("Added {} vectors to the FAISS index.", nb);

        // Generate random query vectors
        let xq: Vec<c_float> = (0..(nq * d as c_longlong))
            .map(|_| rng.gen_range(0.0..1.0))
            .collect();

        // Prepare space for search results
        let mut distances: Vec<c_float> = vec![0.0; (nq * k) as usize];
        let mut labels: Vec<c_longlong> = vec![-1; (nq * k) as usize];

        // Perform a search
        let search_status = faiss_Index_search(
            index,
            nq,
            xq.as_ptr(),
            k,
            distances.as_mut_ptr(),
            labels.as_mut_ptr(),
        );

        if search_status != 0 {
            let error = faiss_get_last_error();
            let error_message = std::ffi::CStr::from_ptr(error).to_string_lossy();
            eprintln!("Error searching FAISS index: {}", error_message);
            faiss_Index_free(index);
            return;
        }

        // Print the search results
        for i in 0..nq {
            println!("Query {}:", i);
            for j in 0..k {
                let idx = i * k + j;
                println!(
                    "  Neighbor {}: label = {}, distance = {}",
                    j, labels[idx as usize], distances[idx as usize]
                );
            }
        }

        // Clean up the index
        faiss_Index_free(index);
    }
}
