- need to adjust encryption key in .env
- celery workers are being run as super users
- ollama needs to be run manually
- should ollama url be local host?
- switch celery back to forks, instead of gevents

- azure model repository blob container can't be empty when accessed. Gives not a valid directory error
- triton model repo will fail if there needs to be other files (other than modelfile and config)

- triton works on models that have been loaded previously, does not load models that are pushed from the backend for some reason. We can push model + config files to azure, but not load into triton.