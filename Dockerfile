FROM python:3.13-slim
RUN pip install --no-cache-dir --disable-pip-version-check orjson==3.11.9
WORKDIR /app
COPY motor.py .
COPY regras/ regras/
ENTRYPOINT ["python", "/app/motor.py"]
