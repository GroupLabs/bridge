# llama.cpp

llama.cpp can be used to:
* run against an LLM
* convert LLM data to ggml format
* quantize ggml files to different formats (run `./quantize -h` for available formats)


## 1. Build llama.cpp
```
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
make
python3 -m pip install -r requirements.txt
```


## 2. Models
Models need to be downloaded and converted to ggml format. By default the ggml file is in f16 format, but it can be quantized to other format, trading size for perplexity (see https://github.com/ggerganov/llama.cpp#quantization)

Downloading the original file can take a long time, it's worth keeping around the file in the format we've decided on. Note: When uploading a file on a google shared folder, the space is taken from the account of the owner of the file, i.e.: the uploader, not the owner of the shared drive!!

### Prerequisites
* Install and build llama.cpp as describe above
* Install the **git-lfs** extension (on Fedora: `sudo dns install -y git-lfs`)
* A huggingface account - `git clone` will aks for your userid and password.

### Download (clone) model
Find the model you need on huggingface, the URL of the page where the model is described can be used as the git repository.  
Note: By default the model name in the URL starts with an upper case, but you can clone them all lower case.

Warning: It looks as though Hugging Face is rate limiting, this can take a long time, 45 minutes to an hour for a 7B models.  
```
cd models
git lfs install
git clone https://huggingface.co/meta-llama/llama-2-7b-chat-hf
cd llama-2-7b-chat-hf
git lfs pull
```
Note: Once you've run `git lfs install`, you will not need to run `git lfs pull`, it'll be done automatically during the clone ; it also doesn't hurt anything if you run it again.

### Convert and quantize
```
cd ../..
python3 ./convert.py models/llama-2-7b-chat-hf
./quantize models/llama-2-7b-chat-hf/ggml-model-f16.gguf models/llama-2-7b-chat-hf/ggml-model-q4_0.gguf q4_0
```


## 4. Run llama.cpp


## 5. llama.cpp Python binding
