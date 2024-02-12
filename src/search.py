from vespa.deployment import VespaDocker


class Search:
    def __init__(self, name="bridge-research", app_root="..."):
        # convert vespa-colbert-e5 to config
        # deploy from disk
        # https://blog.vespa.ai/run-search-engine-experiments-in-Vespa-from-python/#deploy-from-vespa-config-files
        self.app = VespaDocker().deploy_from_disk(
            application_name=name, application_root=app_root
        )

        pass

    def __len__(self) -> int:
        return self.app.query(
            yql="select * from sources * where true"
        ).number_documents_indexed

    def __repr__(self) -> str:
        return str(len(self))

    def __del__(self):
        pass

    def ingest(self):
        # if pdf
        # pdf processor
        # if sql
        # sql processor
        pass

    def query(self):
        pass
