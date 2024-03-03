from celery import Celery

celery_app = Celery(
    "worker",
    broker="amqp://guest:guest@localhost",  # Default RabbitMQ credentials
    backend="rpc://",  # Use RPC as the backend with RabbitMQ
)

# Optional: Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],  # Ignore other content
    result_serializer='json',
    timezone='Europe/London',
    enable_utc=True,
)