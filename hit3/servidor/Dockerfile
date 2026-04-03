FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir flask docker requests

COPY app/servidor.py .

EXPOSE 5002

CMD ["python", "servidor.py"]