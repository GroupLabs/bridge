# llama.cpp

## 1. Build llama.cpp
```
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
make
python3 -m pip install -r requirements.txt
```


## 2. Convert and quantize model
Check on the google drive if the model has already been quantized. If not, follow these steps.
### Prerequisites
* Install and build llama.cpp as describe above
* Install need **git-lfs** (on Fedora: `sudo dns install -y git-lfs`)
* A huggingface account - `git clone` will aks for your userid and password.
### Download (clone) model
Find the model you need on huggingface, the URL can be used as the git repository.  
Note: By default the model name in the URL starts with an upper case, but you can clone them all lower case.

Example for `llama-2-7b-chat-hf`, replace the model name as required. This is assuming you are already in the `llama.cpp` directory.
```
cd models
git clone https://huggingface.co/meta-llama/llama-2-7b-chat-hf
cd llama-2-7b-chat-hf
git lfs pull # **TAKES A LONG TIME** (45 minutes, the bottleneck seems to be huggingface rate limit)
```
### Convert and quantize
```
cd ../..
python3 convert.py models/llama-2-7b-chat-hf
./quantize models/llama-2-7b-chat-hf/ggml-model-f16.gguf models/llama-2-7b-chat-hf/ggml-model-q4_0.gguf q4_0
```
### Upload the artifact
Upload the new artifact on the google drive.

## 3. Test
`./main -m ./models/llama-2-7b-chat-hf/ggml-model-q4_0.gguf -n 256 --repeat_penalty 1.0 --color -i -r "User:" -f prompts/chat-with-bob.txt`
