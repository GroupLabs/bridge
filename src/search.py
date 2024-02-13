from vespa.deployment import VespaDocker
from vespa.io import VespaQueryResponse

from unstructured.cleaners.core import clean
from unstructured.documents.elements import Element
from unstructured.partition.pdf import partition_pdf

import hashlib
import unicodedata


class Search:
    def __init__(self, name="search", app_root="./search-config"):
        # TODO: check if already deployed

        self.app = VespaDocker().deploy_from_disk(
            application_name=name, application_root=app_root
        )

    def __len__(self) -> int:
        return self.app.query(
            yql="select * from sources * where true"
        ).number_documents_indexed

    def __repr__(self) -> str:
        r = ""
        r = r + "Search: \n"
        r = r + f".... status: {self.app.get_application_status()}\n"
        r = r + f".... storing {len(self)} value(s)"
        return r

    def __del__(self):
        pass

    def upload(self, schema: str, data_id: str, fields: dict):
        self.app.feed_data_point(schema=schema, data_id=data_id, fields=fields)

    def query(
        self,
        query: str,
        yql: str = "select id,title,page,chunkno,chunk from pdf where userQuery() or ({targetHits:10}nearestNeighbor(embedding,q))",
        ranking: str = "colbert",
    ):
        response: VespaQueryResponse = self.app.query(
            yql=yql,
            ranking=ranking,
            query=query,
            body={
                "presentation.format.tensors": "short-value",
                f"input.query(q)": 'embed(e5, "{query}")',
                f"input.query(qt)": 'embed(colbert, "{query}")',
            },
        )

        return response.hits[0]

    # connectors

    def pdf(self, input):
        # assume schema exists

        # elements = partition_pdf(input, strategy="fast", chunking_strategy="by_title")
        elements = partition_pdf(input, strategy="hi_res", chunking_strategy="by_title")

        for i, e in enumerate(elements):
            vespa_id = f"{e.metadata.to_dict()['filename']}#{e.metadata.to_dict()['page_number']}#{i}"
            hash_value = hashlib.sha1(vespa_id.encode()).hexdigest()  # hash of id

            chunk = "".join(
                ch for ch in e.text if unicodedata.category(ch)[0] != "C"
            )  # remove control characters

            fields = {
                "title": e.metadata.filename,
                "url": "",
                "page": 0,
                "id": hash_value,
                "authors": [],
                "chunkno": i,
                "chunk": chunk,
            }

            self.upload(schema="pdf", data_id=hash_value, fields=fields)

        return

    def sql(self):
        pass


if __name__ == "__main__":
    s = Search()

    s.pdf(
        "/Users/noelthomas/Documents/GitHub/Bridge/data/datasets/pdf_tressl/Summary Report.pdf"
    )

    s.query("List of projects")

    print(len(s))

    print(s)
