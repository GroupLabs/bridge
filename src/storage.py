import hashlib
import unicodedata
import os
import yaml

from vespa.deployment import VespaDocker
from vespa.io import VespaQueryResponse
from vespa.package import ApplicationPackage

from unstructured.partition.pdf import partition_pdf

from typeutils import get_pathtype

class Storage:
    def __init__(self, name="search", app_root="./search-config"):
        # TODO: check if already deployed

        self.app = VespaDocker().deploy_from_disk(
            application_name=name, application_root=app_root
        )

    def __len__(self) -> int:
        return self.app.query(
            yql="select * from sources * where true",
            groupname="all"
        ).number_documents_indexed

    def __repr__(self) -> str:
        r = ""
        r = r + "Search: \n"
        r = r + f".... status: {self.app.get_application_status()}\n"
        r = r + f".... storing {len(self)} value(s)"
        return r

    def __del__(self):
        pass

    def query(
        self,
        query: str,
        yql: str = "select id,title,page,chunkno,chunk_text from chunk where userQuery() or ({targetHits:10}nearestNeighbor(embedding,q))",
        ranking: str = "colbert",
    ):
        response: VespaQueryResponse = self.app.query(
            yql=yql,
            groupname="all",
            ranking=ranking,
            query=query,
            body={
                "presentation.format.tensors": "short-value",
                f"input.query(q)": 'embed(e5, "{query}")',
                f"input.query(qt)": 'embed(colbert, "{query}")',
            },
        )

        return response.hits

    def load_data(self, filepath: str):    
        # checks for illegal paths and returns type
        pathtype = get_pathtype(filepath)

        if pathtype == "pdf":
            self._pdf(filepath)
        elif pathtype == "dir":
            # check if database yamls
            if os.path.basename(filepath) == "noelthomas":
                self._db()
        else:
            print(pathtype)
            raise NotImplementedError("File type is not supported.")

        return pathtype
    
    def _upload(self, schema: str, data_id: str, fields: dict):

        self.app.feed_data_point(
            schema=schema,
            namespace="all",
            data_id=data_id,
            fields=fields,
            groupname= "all"
        )

    def _pdf(self, input):
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
                "chunk_text": chunk,
            }

            self._upload(schema="chunk", data_id=hash_value, fields=fields)

        return
    
    def _db(self):
        node_name = "noelthomas"

        data = {}

        for i, file in enumerate(os.listdir(node_name)):
            filepath = os.path.join(node_name, file)
            if file.endswith('.yaml') and os.path.isfile(filepath):
                with open(filepath, 'r') as f:
                    data = yaml.safe_load(f)

                    vespa_id = f"{os.path.basename(filepath)}#{i}"
                    hash_value = hashlib.sha1(vespa_id.encode()).hexdigest()

                    fields = {
                        "title": node_name,
                        "url": "",
                        "page": 0,
                        "id": hash_value,
                        "authors": [],
                        "chunkno": i,
                        "chunk_text": data[os.path.basename(filepath).split(".")[0]]["semantic_context"],
                    }

                    self._upload(schema="chunk", data_id=hash_value, fields=fields)
                    
                    print("stored: " + file.split(".")[0])

if __name__ == "__main__":
    s = Storage()
    print(s)

    s.load_data("noelthomas")

    print(s)
