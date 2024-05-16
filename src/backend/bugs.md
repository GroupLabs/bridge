List of bugs: 
1. trying to load model. It successfully lods the model, but an error is raised 30 seconds after.

2024-05-16 10:16:25 [2024-05-16 14:16:25,164: INFO/ForkPoolWorker-6] All files successfully uploaded to Azure Blob Storage.
2024-05-16 10:16:25 INFO: 05/16/2024 02:16:25 PM       tritonutils.py  77 : Successfully added model to /modeltmp
2024-05-16 10:16:25 [2024-05-16 14:16:25,176: INFO/ForkPoolWorker-6] Successfully added model to /modeltmp
2024-05-16 10:16:55 [2024-05-16 14:16:55,184: WARNING/ForkPoolWorker-6] POST /v2/repository/models/distil_alert_v1/load, headers {}
2024-05-16 10:16:55 {}
2024-05-16 10:16:55 [2024-05-16 14:16:55,203: WARNING/ForkPoolWorker-6] <HTTPSocketPoolResponse status=503 headers={'content-type': 'application/json', 'content-length': '77'}>
2024-05-16 10:16:55 [2024-05-16 14:16:55,246: ERROR/ForkPoolWorker-6] Task load_model_task[1582eaec-2452-4bac-8236-6f4e5c30db05] raised unexpected: UnpickleableExceptionWrapper('tritonclient.utils', 'InferenceServerException', (), 'InferenceServerException()')
2024-05-16 10:16:55 Traceback (most recent call last):
2024-05-16 10:16:55   File "/usr/local/lib/python3.11/site-packages/celery/app/trace.py", line 453, in trace_task
2024-05-16 10:16:55     R = retval = fun(*args, **kwargs)
2024-05-16 10:16:55                  ^^^^^^^^^^^^^^^^^^^^
2024-05-16 10:16:55   File "/usr/local/lib/python3.11/site-packages/celery/app/trace.py", line 736, in __protected_call__
2024-05-16 10:16:55     return self.run(*args, **kwargs)
2024-05-16 10:16:55            ^^^^^^^^^^^^^^^^^^^^^^^^^
2024-05-16 10:16:55   File "/app/storage.py", line 106, in load_model
2024-05-16 10:16:55     tc.add_model(model,config) # TODO this function needs to leave the path of the original alone so that
2024-05-16 10:16:55     ^^^^^^^^^^^^^^^^^^^^^^^^^^
2024-05-16 10:16:55   File "/app/tritonutils.py", line 80, in add_model
2024-05-16 10:16:55     self.triton_client.load_model(model_name)
2024-05-16 10:16:55   File "/usr/local/lib/python3.11/site-packages/tritonclient/http/_client.py", line 669, in load_model
2024-05-16 10:16:55     _raise_if_error(response)
2024-05-16 10:16:55   File "/usr/local/lib/python3.11/site-packages/tritonclient/http/_utils.py", line 69, in _raise_if_error
2024-05-16 10:16:55     raise error
2024-05-16 10:16:55 celery.utils.serialization.UnpickleableExceptionWrapper: InferenceServerException()

