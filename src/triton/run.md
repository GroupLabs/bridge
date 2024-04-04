# Triton Inference Server

> Run command: `docker run --rm -p8000:8000 -p8001:8001 -p8002:8002 -v ./model_repository:/models nvcr.io/nvidia/tritonserver:22.08-py3 tritonserver --model-repository=/models`

To get started, there are two things that need to be present:

1. Model Repository
2. Triton Container

For inference, the models need to be in torchscript. The container can be pulled from the NVIDIA container registry. Use the tracer notebook for help to trace!