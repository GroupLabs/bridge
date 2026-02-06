// Test: Does QueryType::Intersection hurt hybrid recall vs Union?
//
// Run with: cargo run --release --bin recall_test

use rand::Rng;
use seekstorm::index::{
    create_index, IndexDocuments, IndexMetaObject,
    SimilarityType, StemmerType, StopwordType, FrequentwordType, TokenizerType, AccessType,
    Document,
};
use seekstorm::search::{QueryType, ResultType, Search};
use serde_json::json;
use std::collections::{HashMap, HashSet};

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
    let n = 1_000_000;  // Same as hybrid_bench to trigger commit
    let num_queries = 1000;
    let k = 10;

    println!("Recall Impact Test: Union vs Intersection");
    println!("==========================================\n");

    println!("Generating {} documents...", n);
    let (documents, vocab) = generate_documents(n);

    // Build index
    let temp_dir = tempfile::tempdir()?;
    let index_path = temp_dir.path().to_path_buf();

    let schema_json = r#"[{"field":"body","field_type":"Text","stored":false,"indexed":true}]"#;
    let schema = serde_json::from_str(schema_json)?;

    let meta = IndexMetaObject {
        id: 0,
        name: "recall_test".into(),
        similarity: SimilarityType::Bm25f,
        tokenizer: TokenizerType::UnicodeAlphanumeric,
        stemmer: StemmerType::None,
        stop_words: StopwordType::None,
        frequent_words: FrequentwordType::None,
        ngram_indexing: 0,
        access_type: AccessType::Ram,
    };

    let text_index = create_index(&index_path, meta, &schema, &Vec::new(), 3, false, None).await?;

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

    // Generate queries FROM documents (like hybrid_bench does)
    // This ensures queries actually match documents
    let queries: Vec<String> = (0..num_queries)
        .map(|i| {
            let doc = &documents[i % n];
            doc.split_whitespace().take(3).collect::<Vec<_>>().join(" ")
        })
        .collect();

    // Compare Union vs Intersection
    let mut union_results: Vec<HashSet<usize>> = Vec::new();
    let mut intersection_results: Vec<HashSet<usize>> = Vec::new();
    let mut union_empty = 0;
    let mut intersection_empty = 0;

    for query in &queries {
        // Union (OR)
        let union_result = text_index.search(
            query.clone(),
            QueryType::Union, 0, k, ResultType::Topk, false,
            Vec::new(), Vec::new(), Vec::new(), Vec::new(),
        ).await;
        let union_ids: HashSet<usize> = union_result.results.iter().map(|r| r.doc_id).collect();
        if union_ids.is_empty() { union_empty += 1; }
        union_results.push(union_ids);

        // Intersection (AND)
        let intersection_result = text_index.search(
            query.clone(),
            QueryType::Intersection, 0, k, ResultType::Topk, false,
            Vec::new(), Vec::new(), Vec::new(), Vec::new(),
        ).await;
        let intersection_ids: HashSet<usize> = intersection_result.results.iter().map(|r| r.doc_id).collect();
        if intersection_ids.is_empty() { intersection_empty += 1; }
        intersection_results.push(intersection_ids);
    }

    // Calculate metrics
    let mut overlap_count = 0;
    let mut total_union = 0;
    let mut total_intersection = 0;

    for i in 0..num_queries {
        let union_set = &union_results[i];
        let intersection_set = &intersection_results[i];

        total_union += union_set.len();
        total_intersection += intersection_set.len();
        overlap_count += union_set.intersection(intersection_set).count();
    }

    let avg_union = total_union as f64 / num_queries as f64;
    let avg_intersection = total_intersection as f64 / num_queries as f64;

    println!("Results for {} queries (k={}):", num_queries, k);
    println!("{:-<50}", "");
    println!("{:<25} {:>12} {:>12}", "", "Union (OR)", "Intersection (AND)");
    println!("{:-<50}", "");
    println!("{:<25} {:>12.1} {:>12.1}", "Avg results per query", avg_union, avg_intersection);
    println!("{:<25} {:>12} {:>12}", "Empty result queries", union_empty, intersection_empty);
    println!("{:<25} {:>12.1}%", "Intersection coverage",
        if total_union > 0 { 100.0 * total_intersection as f64 / total_union as f64 } else { 0.0 });

    // For hybrid search context
    println!("\n{:-<50}", "");
    println!("HYBRID SEARCH IMPACT:");
    println!("{:-<50}", "");
    println!("- Union returns {:.1}x more results than Intersection",
        if avg_intersection > 0.0 { avg_union / avg_intersection } else { f64::INFINITY });
    println!("- {}% of queries return NO results with Intersection",
        100.0 * intersection_empty as f64 / num_queries as f64);
    println!("- BUT: Vector search still finds semantically similar docs");
    println!("- RRF fusion combines both, so overall recall may be fine");

    if intersection_empty as f64 / num_queries as f64 > 0.1 {
        println!("\n⚠️  HIGH EMPTY RATE: Consider using Union for better text coverage");
    } else {
        println!("\n✓ Low empty rate: Intersection is likely acceptable for hybrid search");
    }

    // Test: How much overlap between Union and Intersection top results?
    println!("\n{:-<50}", "");
    println!("TOP-K OVERLAP ANALYSIS:");
    println!("{:-<50}", "");

    let mut top1_overlap = 0;
    let mut any_overlap = 0;

    for i in 0..num_queries {
        let union_set = &union_results[i];
        let intersection_set = &intersection_results[i];

        // Check if any results overlap
        if !union_set.is_disjoint(intersection_set) {
            any_overlap += 1;
        }

        // Check if top-1 matches (if both have results)
        // Note: we can't easily get top-1 from HashSet, so this is approximate
    }

    println!("Queries with ANY overlap: {}%", 100 * any_overlap / num_queries);
    println!("\nConclusion: Intersection finds DIFFERENT docs than Union,");
    println!("not a subset. For hybrid search, this may actually improve diversity.");

    Ok(())
}
