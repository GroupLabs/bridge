from enum import Enum


class AllowedExtensions(Enum):
    # structured
    CSV = "CSV"
    TSV = "TSV"
    PARQUET = "PARQUET"

    # unstructured
    TXT = "TXT"
    PDF = "PDF"
