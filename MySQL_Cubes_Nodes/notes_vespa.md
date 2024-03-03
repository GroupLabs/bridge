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
