Tressl Consulting

# Backends

Donut/Tesseract/TrOCR as OCR Engine https://github.com/clovaai/donut, https://huggingface.co/spaces/nikhilba/donut-ocr
Table transformer for table recognition (requires OCR after) https://github.com/NielsRogge/Transformers-Tutorials/blob/master/Table%20Transformer/Using_Table_Transformer_for_table_detection_and_table_structure_recognition.ipynb, https://github.com/microsoft/table-transformer, https://huggingface.co/spaces/nielsr/tatr-demo/blob/main/app.py

Marker for PDF -> Markdown https://github.com/VikParuchuri/marker

Direct Donut DocVQA https://huggingface.co/spaces/nielsr/donut-docvqa

# Workflow

Objective: Extract predefined information from documents

Indexing Strategy:

Layout LM -> OCR method for paragraphs, and TATR for tables
|| Use Marker by page (capture page number) + identify & convert tables [how to make contiguous? - adjacent pages with ] + extract tables and -> md tables to csv
Embed into FAISS or ColBERT [Ragtouille]

Query Strategy:
IR by index method
DocVQA on returned page numbers 




Demo + Capabilities




Tressl
- Demo
    - One-click question answering
    - Develop the pipeline in Bridge further
- Designs
    - What are the expected capabilities?
    - Figma designs
    - Price and breakdown





Sidebar:
PDF -> Dataframe [export button]

Main:
File explorer

Highlighting (bounding boxes)
Table reconciliation
Switch OCR Engines

Complex question types
Focus