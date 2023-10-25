Oct 16, 2023

Performance
Big O notation depends on the density of densities (branching factor)
Our first part has O(n*d) [num_vectors, dimensionality], and the second has O(V*E) [num vertices, num edges]
The first part has is SOTA in accuracy vs performance, the second is using a well known algorithm which is the best at what it does

Capabilities
Can handle much larger contexts. Can theoretically handle millions of rows of context on just my laptop
Dependency resolution
Can be run locally
Highly secure - can be set up to never see the data or even the table names, etc. (KV store)
Function calling
Can trigger other models
Can add data at runtime

Competitors
Attention Sinks
Sliding Window

DEMO NOTES

1. Extra questions

List all the leagues names
Which game has the most goals?
Which player has the most goals?

2. Prepare a notebook to verify the above answers
3. Adding data @rt (remove players - question: How many goals does Lionel Messi have?)
4. Demonstrate relationships
5. Talk about how this is interoperable and can use engine (LLMs, translation, etc.)


Unique data problem, entity disambiguation
Why are we SOTA
Metrics
Competitors
Live @rt


We propose a novel solution that overcomes certain challenges faced by current implementations of data retrieval. Unlike predecessors, our method is capable of identifying appropriate resources, and resolving dependencies with only natural language. It can be dynamically updated in real time, and can be adjusted to retrofit other solutions such as natural language to code (SQL, NoSQL, etc.) translation models, or large language models.
