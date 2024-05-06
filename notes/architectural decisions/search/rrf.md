> May 6, 2024

Reciprocal Ranked Fusion (RRF) is a simple way to combine rankings from various ranking systems. [See the RRF Paper](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf). It is ideal for the Bridge use case, because it allows us to combine multiple weaker IR systems (such as embedding based IR, and BM25) into one aggregate system.

$$RRFscore(d \in D) = \sum_{r \in R} \frac{1}{k + r(d)}$$

where
- D is a set of documents
- R is a set of rankings, where eash is a permutation of 1..|D|
- k is a constant

The constant k helps to mitigate high scores of outlier systems.