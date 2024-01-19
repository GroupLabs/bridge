

  

- Marker
- Embedding
- Ephemeral Embedding store
- TATR
- DocVQA





# Objective

The main goal with all the work we did so far is to improve the legacy data ingestion process at Tressl. In the provided data, we identified that there are two general groups of data extraction.

1. Grouped Values Extraction (Tables)
2. Singular Value Extraction
# What we tried

This is somewhat an unsolved problem. There is no one method fits all solution here, but people are working towards it. However, everything that we will mention is the state-of-the-art in PDF ingestion.

There are several ways to ingest legacy information stored in PDF. There are several forms of PDF (image/text based).

Ingestion
- Marker
- Table Transformer (w/ OCR)
- Donut/Tesseract/TrOCR
- DocVQA Transformer

Storing
- FAISS
- ColBERT [Ragatouille]

Indexing Strategies
- LayoutLM → OCR on paragraphs, TATR to identify & convert tables → Embed → Store in FAISS/ColBERT - This works, but it foregoes structural information in the document
- Marker (capture page number) → TATR to identify tables → markdown tables to CSV → Embed Marker output → Store in FAISS/ColBERT

Query Strategies
- IR by index method → Feed into context → Language model response
- IR by index method → DocVQA on returned pages
# What we built

Ideally, we want to create a one-click solution that fills in an excel file. However, we know that this is not infallible, so we designed two prototypes with a human in the loop.

| Sidebar | Main |
| ---- | ---- |
| Import PDF Button | File Explorer |
| Export Button |  |
## Prototype 1

The first prototype demonstrates single value extraction. It picks out single answers from text. This should be really strong when it comes to complex document understanding, like for the map example we went over previously.

This searches over the entire document and tries to find an answer that can fulfill your question.

**How this can improve**
- Switching OCR engines
- Better embedding and IR
- Better DocVQA
- More complex questions/answers with vllms
- Try SuryaOCR
- Focus mode (highlight where you want the model to look)
## Prototype 2

The second demonstrates grouped values extraction. This is capable of identifying and extracting entire tables of data at once. This will be strong for summary reports as seen in the data.

This identifies tables, tries to define its structure, then runs OCR over each cell.

**How this can improve**
- Improved table reconciliation
- Switching OCR engines
- Focus mode (highlight where you want the model to look)
# What we can build

In the next iteration, we want to build a process that combines the two prototypes and helps Tressl with their legacy data ingestion with a one-click solution.

# Steps forward
Flexible
Hourly: $65
Hours per week: 10 - 20
One month