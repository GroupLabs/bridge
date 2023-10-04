# llama.cpp

llama.cpp can be used to:
* run against an LLM
* convert LLM data to ggml format
* quantize ggml files to different formats (run `./quantize -h` for available formats)


## 1. Build llama.cpp
Check the github page for instruction to compile with the appropriate options for your GPU:
```
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
make
python3 -m pip install -r requirements.txt
```


## 2. Models
Models need to be downloaded and converted to ggml format. By default the ggml file is in f16 (floating point 16 bytes, not quantized) format, but it can be quantized to other format, trading size for perplexity (see https://github.com/ggerganov/llama.cpp#quantization)

Downloading the original file can take a long time, it's worth keeping around the file in the format we've decided on. Note: When uploading a file on a google shared folder, the space is taken from the account of the owner of the file, i.e.: the uploader, not the owner of the shared drive!!

### Prerequisites
* Install and build llama.cpp as describe above
* Install the **git-lfs** extension (on Fedora: `sudo dns install -y git-lfs`)
* A Hugging Face account - `git clone` will aks for your userid and password.

### Download (clone) model
Find the model you need on Hugging Face, the URL of the page where the model is described can be used as the git repository.  
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
### Options
Options to tweak:
* increase/remove token limit (`-n`): The default is 512! Use `-2` for unlimited, which did not give any issue with a proper prompt
* number of threads (`-n`). Increasing thread improved timing. The default is 4
* temperature (`--temp`): The default is 0.8, lowering it to 0.6 yield better result without paralysis (empty result, repeat of the question)
* numa (--numa): slight performance increase (check if available on your hardware)

### Prompt
A few changes to the prompt made dramatic differences both in performance and accuracy (better code quality):
* Use quotes around file names
* use actual column header, and quote them. Do not let any space for guessing
* enclose your query in `[INST]`/`[/INST]`
* example of prompt which produced good runable code:
```
Generate python code to output the number of employee by department name given that I have a csv file "A.csv" with columns "first_name", "last_name" and "salary", a csv file "B.csv" with columns "employee_id" and "deparment_id" and a file "C.csv" with columns "department_id" and "department_name"
```


## 5. llama.cpp Python binding
Note: Use options to make use of for your GPU  
* https://github.com/abetlen/llama-cpp-python
* https://python.langchain.com/docs/integrations/llms/llamacpp

Never managed to get a good answer. The answwers make more sense with higher temperature than with the binary llamacpp, but are never as good. The only difference I can see is `n_ctx_train` but cannot find a way to change, I assume it is a compile option.

