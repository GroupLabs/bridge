// maybe we can store relationships as CYPHER or as JSON?
MATCH (a:Person {name: "Alice"}), (b:Person {name: "Bob"})
CREATE (a)-[:KNOWS]->(b);

// Here the JOIN (or KNOWS) relationship is implicit
[
    {
        "Alice" : "Bob"
    },
    {
        "Alice" : "Sally"
    }
]