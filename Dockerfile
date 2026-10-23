FROM python:3.13-slim
WORKDIR /app
COPY motor.py .
COPY regras/ regras/
ENTRYPOINT ["python", "/app/motor.py"]
