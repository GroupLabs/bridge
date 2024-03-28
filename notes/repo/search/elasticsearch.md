Why are we using ES?

- auto scaling
- full text search, and vector search
- 

ES STARTUP NOTES ------------


docker network create elastic

docker run --name es01 --net elastic \
  -p 9200:9200 -p 9300:9300 \
  -e "discovery.type=single-node" \
  -e "xpack.license.self_generated.type: basic" \
  -t docker.elastic.co/elasticsearch/elasticsearch:8.13.0


export ELASTIC_PASSWORD=v4Ci+biLJxCFS=s5arr1

docker cp es01:/usr/share/elasticsearch/config/certs/http_ca.crt .

docker run --name kibana --net elastic -p 5601:5601 docker.elastic.co/kibana/kibana:8.13.0

use kibana enrollment token

use user=elastic, password=ELASTIC_PASSWORD



----------












docker run -p 9200:9200 --name elasticsearch \
  -e "discovery.type=single-node" \
  -e "xpack.license.self_generated.type: basic" \
  docker.elastic.co/elasticsearch/elasticsearch:8.13.0

No security
docker run -p 9200:9200 -d --name elasticsearch \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  -e "xpack.security.http.ssl.enabled=false" \
  -e "xpack.license.self_generated.type: basic" \
  docker.elastic.co/elasticsearch/elasticsearch:8.13.0