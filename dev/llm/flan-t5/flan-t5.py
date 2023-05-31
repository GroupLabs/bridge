from transformers import T5Tokenizer, T5ForConditionalGeneration
import torch
import time
import os

# ANSI escape codes for text colors
class TextColors:
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    RESET = '\033[0m'

# choose size: "small", "base", "large", "xl", "xxl"
size = "xl"

model_name = "google/flan-t5-" + size
cache_dir = "./" + size + "_flan-t5_cache"

print(TextColors.BLUE + "Model name: " + str(model_name) + TextColors.RESET)

load_start_time = time.time()
# Check if the model is already downloaded
if not os.path.isdir(cache_dir):
    print(TextColors.RED + "Model cache not found" + TextColors.RESET)
    # Download and save the model to the specified cache directory
    model = T5ForConditionalGeneration.from_pretrained(model_name)
    tokenizer = T5Tokenizer.from_pretrained(model_name)
    model.save_pretrained(cache_dir)
    tokenizer.save_pretrained(cache_dir)
else:
    print(TextColors.CYAN + "Using cached model" + TextColors.RESET)
    # If the model is already downloaded, load it from the cache directory
    model = T5ForConditionalGeneration.from_pretrained(cache_dir)
    tokenizer = T5Tokenizer.from_pretrained(cache_dir)

print("Load time: %s seconds" % (time.time() - load_start_time))

while True:

    print(TextColors.BLUE + ">>> " + TextColors.RESET, end="")

    lines = []
    while True:
        line = input("")
        if line:
            lines.append(line)
        else:
            break

    input_text = '\n'.join(lines)

    start_time = time.time()
    input_ids = tokenizer(input_text, return_tensors="pt").input_ids

    outputs = model.generate(input_ids, max_new_tokens=50)
    print(TextColors.GREEN + ">>> " + str(tokenizer.decode(outputs[0])).replace("<pad>", "").replace("</s>", "") + TextColors.RESET)

    print("--- %s seconds ---" % (time.time() - start_time))
