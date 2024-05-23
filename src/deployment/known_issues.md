- need to adjust encryption key in .env
- celery workers are being run as super users
    - don't solve this. its ok because its in a contianer, and the permissions are required for some actions.




- ollama needs to be run manually
- should ollama url be local host?
- switch celery back to forks, instead of gevents

- azure model repository blob container can't be empty when accessed. Gives not a valid directory error
- triton model repo will fail if there needs to be other files (other than modelfile and config)

- triton works on models that have been loaded previously, does not load models that are pushed from the backend for some reason. We can push model + config files to azure, but not load into triton.
- The multi-container application consumes a lot of memory, which in turn triggers a variety of other problems.
- Docker Desktop (at least on Windows) may glitch and cause an error like this:

```text
request returned Internal Server Error for API route and version http://%2F%2F.%2Fpipe%2Fdocker_engine/v1.45/containers/30029d548eed6d45c3ed1293801be04d241b674f1cfccfba01dd0ad34ce50408/json, check if the server supports the requested API version
```

This glitch is caused by Docker Desktop not being able to communicate with the Docker daemon. To fix it, restart Docker Desktop. If that doesn't work, restart your computer. For me (JohnScience), it happens to Kibana service.

- Docker Desktop for Windows has a glitch where it will occasionally be using only 1 CPU insteal of all the available ones.
- Occasionally, the `es01` service fails with `2024-05-17 13:54:06 ERROR: Elasticsearch exited unexpectedly, with exit code 137`. It indicates excessive memory consumption and subsequent lack of it.
- The `api` service consistently fails with errors when loading a file. See the logs:

```text
2024-05-17 13:48:19 [2024-05-17 19:48:19,968: INFO/MainProcess] mingle: searching for neighbors
2024-05-17 13:48:21 [2024-05-17 19:48:21,172: INFO/MainProcess] mingle: all alone
2024-05-17 13:48:21 [2024-05-17 19:48:21,235: INFO/MainProcess] celery@bb290e15a4d2 ready.
2024-05-17 13:48:24 INFO: 05/17/2024 07:48:24 PM               api.py  99 : LOAD accepted: sampleunsecuredpdf.pdf
2024-05-17 13:48:24 [2024-05-17 19:48:24,626: INFO/MainProcess] Task load_data_task[a750cecd-46d7-4b24-b1ff-c44ac7810f46] received
2024-05-17 13:48:24 [2024-05-17 19:48:24,872: INFO/ForkPoolWorker-4] pikepdf C++ to Python logger bridge initialized
2024-05-17 13:48:25 [nltk_data] Downloading package punkt to /root/nltk_data...
2024-05-17 13:48:26 [nltk_data]   Unzipping tokenizers/punkt.zip.
2024-05-17 13:48:27 [nltk_data] Downloading package averaged_perceptron_tagger to
2024-05-17 13:48:27 [nltk_data]     /root/nltk_data...
2024-05-17 13:48:28 [nltk_data]   Unzipping taggers/averaged_perceptron_tagger.zip.
2024-05-17 13:48:30 [2024-05-17 19:48:30,601: INFO/ForkPoolWorker-4] generated new fontManager
2024-05-17 13:48:51 [2024-05-17 19:48:51,245: INFO/ForkPoolWorker-4] Reading PDF for file: /app/tmp/sampleunsecuredpdf.pdf ...
2024-05-17 13:48:51 [2024-05-17 19:48:51,778: INFO/ForkPoolWorker-4] Detecting page elements ...
2024-05-17 13:49:38 [2024-05-17 19:49:22,898: INFO/ForkPoolWorker-4] Processing entire page OCR with tesseract...
2024-05-17 13:49:38 [2024-05-17 19:49:37,023: ERROR/MainProcess] Process 'ForkPoolWorker-4' pid:114 exited with 'signal 9 (SIGKILL)'
2024-05-17 13:49:38 [2024-05-17 19:49:37,357: ERROR/MainProcess] Task handler raised error: WorkerLostError('Worker exited prematurely: signal 9 (SIGKILL) Job: 0.')
2024-05-17 13:49:38 Traceback (most recent call last):
2024-05-17 13:49:38   File "/usr/local/lib/python3.11/site-packages/billiard/pool.py", line 1264, in mark_as_worker_lost
2024-05-17 13:49:38     raise WorkerLostError(
2024-05-17 13:49:38 billiard.einfo.ExceptionWithTraceback: 
2024-05-17 13:49:38 """
2024-05-17 13:49:38 Traceback (most recent call last):
2024-05-17 13:49:38   File "/usr/local/lib/python3.11/site-packages/billiard/pool.py", line 1264, in mark_as_worker_lost
2024-05-17 13:49:38     raise WorkerLostError(
2024-05-17 13:49:38 billiard.exceptions.WorkerLostError: Worker exited prematurely: signal 9 (SIGKILL) Job: 0.
2024-05-17 13:49:38 """
```

Based on answers online, the problem is related to shortage of memory.
