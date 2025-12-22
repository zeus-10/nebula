# Celery worker entrypoint - initializes Celery app, registers tasks for FFmpeg transcoding

from celery import Celery
import os

celery_app = Celery(
    "nebula_worker",
    broker=os.getenv("REDIS_URL"),
    backend=os.getenv("REDIS_URL")
)

@celery_app.task
def dummy_task():
    return "Worker is alive"

