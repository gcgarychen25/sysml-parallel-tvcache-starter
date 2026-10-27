FROM python:3.12-slim
COPY parallel_tvcache/inference/model_transport.py /opt/model_transport.py
ENTRYPOINT ["python", "/opt/model_transport.py", "host", "--socket", "/bridge/model.sock", "--backend-host", "host.docker.internal", "--backend-port", "18080", "--records", "/records"]
