To build and use docker-compose on Azure, we can simply:
    1. Upload custom images to ACR
    2. Run on container instances

Here, `acrbridge` is the name of the ACR resource we're using.

Follow these steps to upload a custom image to the ACR.

1. Login to the ACR:

`docker login acrbridge.azurecr.io`

The credentials will be found in Azure:
-> Azure -> acrbridge -> access keys -> username and password (if username and password doesn't exist, hit adimin user check box)

2. Build your image if you haven't already:

`docker build -t custom_image . (run this in the directory containing your Dockerfile)`

> Note: the container instance your using may not be compatible with your image if the cpu arch/os are different. If this is the case, try the following:
>
> Get buildx:
> `docker buildx create --use`
>
> Build a multiarch image:
> `docker buildx build --platform linux/amd64,linux/arm64 --push -t acrbridge.azurecr.io/custom_image-multiarch .`
>
> This also pushes your image to ACR.

3. Tag your image:

`docker tag custom_image acrbridge.azurecr.io/custom_image`

4. Push your image to ACR:

`docker push acrbridge.azurecr.io/custom_image`

To deploy the containers, follow these steps:

Assuming your images are already in the ACR. Otherwise, use: `docker-compose push`

1. Login to Azure with Docker:

`docker login azure`

2. Create Azure Container Instance (ACI) context:

`docker context create aci bridgecontext`

Then select the appropriate resource group.

3. (Optional) View contexts:

`docker context ls`

4. Use the appropriate context:

`docker context use bridgecontext`

5. Run the docker compose:

`docker compose up`

6. (Optional) See running containers:

`docker ps`

7. (Optional) Stop the compose with:

`docker compose down`



