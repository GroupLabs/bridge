async fn seekstorm() {
    // Define the index path
    let index_path = Path::new("./index/");

    // Schema: only 'body' is indexed and stored
    let schema_json = r#"
    [{"field":"title","field_type":"Text","stored":false,"indexed":false},
    {"field":"body","field_type":"Text","stored":true,"indexed":true},
    {"field":"url","field_type":"Text","stored":false,"indexed":false}]"#;
    let schema = serde_json::from_str(schema_json).unwrap();

    // Create or open the index
    let meta = IndexMetaObject {
        id: 0,
        name: "test_index".to_string(),
        similarity: SimilarityType::Bm25f,
        tokenizer: TokenizerType::AsciiAlphabetic,
        access_type: AccessType::Mmap,
    };

    let serialize_schema = true;
    let segment_number_bits = 11;

    // Try to open index; if not found, create it
    // let mut index_arc = open_index(index_path, false).await.unwrap();

    let new_index = create_index(
        index_path,
        meta,
        &schema,
        serialize_schema,
        &Vec::new(),
        segment_number_bits,
        false,
    )
    .expect("Failed to create index");
    let mut index_arc = Arc::new(RwLock::new(new_index));

    // Documents to index - ensuring 'body' contains "test"
    let documents_json = r#"
    [
        {"title":"title1 test","body":"body1 here","url":"url1"},
        {"title":"title2","body":"this is body2 test text","url":"url2"},
        {"title":"title3 test","body":"body3 with the word test multiple times test","url":"url3"}
    ]
    "#;

    let documents: Vec<Document> = serde_json::from_str(documents_json).unwrap();

    // Index documents (uncommitted)
    index_arc.index_documents(documents).await;
    index_arc.commit().await;

    println!("Documents indexed.");

    let query = "test".to_string();
    let offset = 0; // Start from the first result
    let length = 10;
    let query_type = QueryType::Intersection;
    let result_type = ResultType::TopkCount;
    let include_uncommitted = true; // Include documents we just indexed
    let field_filter = Vec::new();
    let query_facets = Vec::new();
    let facet_filter = Vec::new();
    let highlight_config = vec![Highlight {
        field: "body".to_string(),
        name: String::new(),
        fragment_number: 2,
        fragment_size: 160,
        highlight_markup: true,
    }];

    println!("Search query: '{}'", query);

    let result_object = index_arc
        .search(
            query.to_owned(),
            query_type,
            offset,
            length,
            result_type,
            include_uncommitted,
            field_filter,
            query_facets,
            facet_filter,
            Vec::new(),
        )
        .await;

    println!("Search complete");
    println!("Number of results: {}", result_object.results.len());
    println!("Result Object: {:#?}", result_object); // Empty

    // Prepare highlighter
    let highlighter = Some(
        highlighter(
            &index_arc,
            highlight_config,
            result_object.query_terms.clone(),
        )
        .await,
    );
    let return_fields_filter = HashSet::new();

    // Acquire write lock to access documents
    let mut index = index_arc.write().await;
    let distance_fields: &[DistanceField] = &[]; // No distance fields used

    for result in result_object.results.iter() {
        // Retrieve the document
        let doc = index
            .get_document(
                result.doc_id,
                false,
                &highlighter,
                &return_fields_filter,
                distance_fields,
            )
            .expect("Failed to retrieve document");

        println!(
            "result {} rank {} body field {:?}",
            result.doc_id,
            result.score,
            doc.get("body")
        );
    }

    index.close_index();
}
