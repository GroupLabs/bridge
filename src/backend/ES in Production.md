Currently, we're using the standard ES in prod.

There's a dockerfile that sets 

docker login acrbridge.azurecr.io

Go to acrbridge -> Access keys -> username and password

if username and password doesn't exist, hit adimin user check box

docker buildx build --platform linux/amd64,linux/arm64 --push -t acrbridge.azurecr.io/es_bridge-multiarch .



