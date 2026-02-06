// SeekStorm Profiling Benchmark
// Tests different query patterns to isolate performance bottlenecks
//
// Run with: cargo run --release --bin seekstorm_profile

use rand::Rng;
use seekstorm::index::{
    create_index, IndexDocuments, IndexMetaObject,
    SimilarityType, StemmerType, StopwordType, FrequentwordType, TokenizerType, AccessType,
    Document, NgramSet,
};
use seekstorm::search::{QueryType, ResultType, Search};
use serde_json::json;
use std::collections::HashMap;
use std::time::Instant;

fn generate_documents(n: usize) -> (Vec<String>, Vec<String>) {
    let mut rng = rand::thread_rng();
    let vocab: Vec<String> = (0..10_000).map(|i| format!("word{}", i)).collect();

    let docs: Vec<String> = (0..n)
        .map(|_| {
            let num_words = rng.gen_range(20..100);
            (0..num_words)
                .map(|_| vocab[rng.gen_range(0..vocab.len())].clone())
                .collect::<Vec<_>>()
                .join(" ")
        })
        .collect();

    (docs, vocab)
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let n = 1_000_000;
    let num_queries = 5_000;

    println!("SeekStorm Performance Profiling");
    println!("================================\n");

    println!("Generating {} documents...", n);
    let (documents, vocab) = generate_documents(n);

    // Build index
    println!("Building SeekStorm index...");
    let temp_dir = tempfile::tempdir()?;
    let index_path = temp_dir.path().to_path_buf();

    let schema_json = r#"[{"field":"body","field_type":"Text","stored":false,"indexed":true}]"#;
    let schema = serde_json::from_str(schema_json)?;

    let meta = IndexMetaObject {
        id: 0,
        name: "profile".into(),
        similarity: SimilarityType::Bm25f,
        tokenizer: TokenizerType::UnicodeAlphanumeric,
        stemmer: StemmerType::None,
        stop_words: StopwordType::None,
        frequent_words: FrequentwordType::None,
        ngram_indexing: 0,  // No ngrams for simpler profiling
        access_type: AccessType::Ram,
    };

    let num_cores = std::thread::available_parallelism().map(|p| p.get()).unwrap_or(8);
    let segment_number_bits = (num_cores as f64).log2().ceil() as usize;

    let text_index = create_index(&index_path, meta, &schema, &Vec::new(), segment_number_bits, false, None).await?;

    let batch_size = 10_000;
    for batch_start in (0..n).step_by(batch_size) {
        let batch_end = (batch_start + batch_size).min(n);
        let docs: Vec<Document> = (batch_start..batch_end)
            .map(|i| {
                let mut doc: Document = HashMap::new();
                doc.insert("body".to_string(), json!(documents[i]));
                doc
            })
            .collect();
        text_index.index_documents(docs).await;
    }
    println!("Index built.\n");

    // Generate different query types
    let mut rng = rand::thread_rng();
    let single_word_queries: Vec<String> = (0..num_queries)
        .map(|_| vocab[rng.gen_range(0..vocab.len())].clone())
        .collect();

    let two_word_queries: Vec<String> = (0..num_queries)
        .map(|_| format!("{} {}",
            vocab[rng.gen_range(0..vocab.len())],
            vocab[rng.gen_range(0..vocab.len())]))
        .collect();

    let three_word_queries: Vec<String> = (0..num_queries)
        .map(|_| format!("{} {} {}",
            vocab[rng.gen_range(0..vocab.len())],
            vocab[rng.gen_range(0..vocab.len())],
            vocab[rng.gen_range(0..vocab.len())]))
        .collect();

    // Warmup
    println!("Warming up...");
    for i in 0..500 {
        let _ = text_index.search(
            single_word_queries[i % num_queries].clone(),
            QueryType::Union, 0, 10, ResultType::Topk, false,
            Vec::new(), Vec::new(), Vec::new(), Vec::new(),
        ).await;
    }

    println!("\n{:-<70}", "");
    println!("PROFILING RESULTS");
    println!("{:-<70}\n", "");

    // Test 1: Single word queries with different k values
    println!("Test 1: Single word queries, varying k");
    println!("{:<20} {:>12} {:>12}", "k", "QPS", "µs/query");
    println!("{:-<50}", "");

    for k in [1, 10, 50, 100, 500] {
        let start = Instant::now();
        for i in 0..num_queries {
            let _ = text_index.search(
                single_word_queries[i].clone(),
                QueryType::Union, 0, k, ResultType::Topk, false,
                Vec::new(), Vec::new(), Vec::new(), Vec::new(),
            ).await;
        }
        let elapsed = start.elapsed();
        let qps = num_queries as f64 / elapsed.as_secs_f64();
        let us_per_query = elapsed.as_micros() as f64 / num_queries as f64;
        println!("{:<20} {:>12.0} {:>12.1}", k, qps, us_per_query);
    }

    // Test 2: Multi-word queries (same k=10)
    println!("\nTest 2: Varying query length (k=10, Union)");
    println!("{:<20} {:>12} {:>12}", "Words", "QPS", "µs/query");
    println!("{:-<50}", "");

    for (name, queries) in [
        ("1 word", &single_word_queries),
        ("2 words", &two_word_queries),
        ("3 words", &three_word_queries),
    ] {
        let start = Instant::now();
        for i in 0..num_queries {
            let _ = text_index.search(
                queries[i].clone(),
                QueryType::Union, 0, 10, ResultType::Topk, false,
                Vec::new(), Vec::new(), Vec::new(), Vec::new(),
            ).await;
        }
        let elapsed = start.elapsed();
        let qps = num_queries as f64 / elapsed.as_secs_f64();
        let us_per_query = elapsed.as_micros() as f64 / num_queries as f64;
        println!("{:<20} {:>12.0} {:>12.1}", name, qps, us_per_query);
    }

    // Test 3: QueryType comparison
    println!("\nTest 3: QueryType comparison (2 words, k=10)");
    println!("{:<20} {:>12} {:>12}", "Type", "QPS", "µs/query");
    println!("{:-<50}", "");

    for (name, query_type) in [
        ("Union (OR)", QueryType::Union),
        ("Intersection (AND)", QueryType::Intersection),
    ] {
        let start = Instant::now();
        for i in 0..num_queries {
            let _ = text_index.search(
                two_word_queries[i].clone(),
                query_type.clone(), 0, 10, ResultType::Topk, false,
                Vec::new(), Vec::new(), Vec::new(), Vec::new(),
            ).await;
        }
        let elapsed = start.elapsed();
        let qps = num_queries as f64 / elapsed.as_secs_f64();
        let us_per_query = elapsed.as_micros() as f64 / num_queries as f64;
        println!("{:<20} {:>12.0} {:>12.1}", name, qps, us_per_query);
    }

    // Test 4: ResultType comparison
    println!("\nTest 4: ResultType comparison (1 word, k=10)");
    println!("{:<20} {:>12} {:>12}", "Type", "QPS", "µs/query");
    println!("{:-<50}", "");

    for (name, result_type) in [
        ("Topk", ResultType::Topk),
        ("TopkCount", ResultType::TopkCount),
        ("Count", ResultType::Count),
    ] {
        let start = Instant::now();
        for i in 0..num_queries {
            let _ = text_index.search(
                single_word_queries[i].clone(),
                QueryType::Union, 0, 10, result_type.clone(), false,
                Vec::new(), Vec::new(), Vec::new(), Vec::new(),
            ).await;
        }
        let elapsed = start.elapsed();
        let qps = num_queries as f64 / elapsed.as_secs_f64();
        let us_per_query = elapsed.as_micros() as f64 / num_queries as f64;
        println!("{:<20} {:>12.0} {:>12.1}", name, qps, us_per_query);
    }

    // Test 5: String allocation overhead
    println!("\nTest 5: Pre-cloned vs inline clone");
    println!("{:<20} {:>12} {:>12}", "Method", "QPS", "µs/query");
    println!("{:-<50}", "");

    // Pre-clone all strings
    let precloned: Vec<String> = single_word_queries.iter().cloned().collect();

    let start = Instant::now();
    for query in precloned.iter().take(num_queries) {
        let _ = text_index.search(
            query.clone(),
            QueryType::Union, 0, 10, ResultType::Topk, false,
            Vec::new(), Vec::new(), Vec::new(), Vec::new(),
        ).await;
    }
    let elapsed = start.elapsed();
    let qps = num_queries as f64 / elapsed.as_secs_f64();
    println!("{:<20} {:>12.0} {:>12.1}", "Pre-cloned", qps, elapsed.as_micros() as f64 / num_queries as f64);

    // Direct iteration (still needs clone for search)
    let start = Instant::now();
    for i in 0..num_queries {
        let _ = text_index.search(
            single_word_queries[i].clone(),
            QueryType::Union, 0, 10, ResultType::Topk, false,
            Vec::new(), Vec::new(), Vec::new(), Vec::new(),
        ).await;
    }
    let elapsed = start.elapsed();
    let qps = num_queries as f64 / elapsed.as_secs_f64();
    println!("{:<20} {:>12.0} {:>12.1}", "Index + clone", qps, elapsed.as_micros() as f64 / num_queries as f64);

    println!("\n{:-<70}", "");
    println!("ANALYSIS");
    println!("{:-<70}", "");
    println!("- If QPS drops significantly with higher k: scoring/heap is bottleneck");
    println!("- If QPS drops with more words: tokenization/posting merge is bottleneck");
    println!("- If Count >> Topk: BM25 scoring is bottleneck");
    println!("- If Intersection >> Union: posting list traversal is bottleneck");

    Ok(())
}
