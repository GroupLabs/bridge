# List of bugs

1. Cody: Trying to load model. It successfully lods the model, but an error is raised 30 seconds after.

2. Damian: the load model enpoint succesfully accepts models but they do not actually get added to Azure. Works for Cody. Additionally, I can't see models loaded on the Triton server.

3. Damian: Loading a PDF does not upload to ElasticSearch. Program gets stuck unzipping a tesseract library file. Works for Cody. Logs:

    """
    2024-05-16 10:53:28 INFO:     192.168.80.1:59336 - "POST /load HTTP/1.1" 202 Accepted
    2024-05-16 10:53:28 [2024-05-16 14:53:28,031: INFO/MainProcess] Task load_data_task[317bb904-0542-4c79-8a6e-3baa0295efea] received
    2024-05-16 10:53:28 [2024-05-16 14:53:28,328: INFO/ForkPoolWorker-14] pikepdf C++ to Python logger bridge initialized
    2024-05-16 10:53:51 [2024-05-16 14:53:51,520: INFO/ForkPoolWorker-14] generated new fontManager
    2024-05-16 10:54:15 [2024-05-16 14:54:15,748: INFO/ForkPoolWorker-14] Reading PDF for file: /app/tmp/Lecture 12.pdf ...
    2024-05-16 10:54:20 [2024-05-16 14:54:20,845: INFO/ForkPoolWorker-14] Detecting page elements ...
    2024-05-16 10:54:45 [2024-05-16 14:54:45,452: INFO/ForkPoolWorker-14] Processing entire page OCR with tesseract...
    2024-05-16 10:55:03 [nltk_data] Downloading package punkt to /root/nltk_data...
    2024-05-16 10:55:04 [nltk_data]   Unzipping tokenizers/punkt.zip.
    2024-05-16 10:55:05 [nltk_data] Downloading package averaged_perceptron_tagger to
    2024-05-16 10:55:05 [nltk_data]     /root/nltk_data...
    2024-05-16 10:55:05 [nltk_data]   Unzipping taggers/averaged_perceptron_tagger.zip.
    """
