# start vespa container
docker pull vespaengine/vespa
docker run --detach --name vespa --hostname vespa-container -p 8080:8080 vespaengine/vespa

# deploy the app
docker cp path/to/your/application.zip vespa:/opt/vespa-app.zip

# enter docker container shell
docker exec -it vespa bash

# run vespa commands to deploy app and exit
vespa-deploy prepare /opt/my_vespa_app_package.zip
vespa-deploy activate
exit

# verify deployment
docker exec vespa vespa-get-cluster-state


<!---
schema yamls {
    document yamls {
        struct dimension {
            field name type string {}
            field type type string {}
            field sql type string {}
        }
        field id type string {
            indexing: summary
        }
        field name type string {
            indexing: summary | index
        }
        field sql_name type string {
            indexing: summary | index
        }
        field dimensions type array<dimension> {
            indexing: summary | index
            struct-field name {
                indexing: summary | index
            }
            struct-field type{
                indexing: summary | index
            }
            struct-field sql{
                indexing: summary | index
            }
        }
        field joins type array<string> {
            indexing: summary | index
        }
        field metadata type map<string,string> {
            indexing: summary | index
        }
        field chunkno type int {
            indexing: summary | attribute
        }
        field chunk type string {
            indexing: summary | index
        }
    }
    field embedding type tensor<bfloat16>(x[384]) {
        indexing: "passage: " . (input name || "") . " " . (input chunk || "") | embed e5 | attribute
        attribute {
            distance-metric: angular
        }
    }
    field colbert type tensor<int8>(dt{}, x[16]) {
        indexing: (input name || "") . " " . (input chunk || "") | embed colbert | attribute
    }
    fieldset default {
        fields: name, chunk
    }
    rank-profile colbert {
        inputs {
            query(q) tensor<float>(x[384])             
            query(qt) tensor<float>(qt{}, x[128])             
        
        }
        function unpack() {
            expression {
                unpack_bits(attribute(colbert))
            }
        }
        function cos_sim() {
            expression {
                closeness(field, embedding)
            }
        }
        function max_sim() {
            expression {
                
                                sum(
                                    reduce(
                                        sum(
                                            query(qt) * unpack() , x
                                        ),
                                        max, dt
                                    ),
                                    qt
                                )
                            
            }
        }
        first-phase {
            expression {
                cos_sim
            }
        }
        second-phase {
            rerank-count: 100
            expression {
                max_sim
            }
        }
        match-features {
            max_sim
            cos_sim
        }
    }
}
-->