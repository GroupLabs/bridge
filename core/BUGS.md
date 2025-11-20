- seekstorm breaks if apostrophe is included. https://chatgpt.com/share/67cd6857-c6c8-800c-bae0-ae98bbd2174c

- seekstorm seems to have an issue with concurrent writes, so we had to do:
text_write_semaphore: Arc::new(tokio::sync::Semaphore::new(1))
