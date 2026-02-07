# celery_app.py
from celery import Celery
from config import settings as cfg
import os

# 选择一个消息代理
CELERY_BROKER_URL = cfg.redis_host

celery_app = Celery(__name__)
celery_app.conf.broker_url = cfg.redis_host
celery_app.conf.result_backend = cfg.redis_host

# 可选: 配置序列化器等
celery_app.conf.task_serializer = 'json'
celery_app.conf.accept_content = ['json']
celery_app.conf.result_serializer = 'json'
celery_app.conf.timezone = 'UTC'