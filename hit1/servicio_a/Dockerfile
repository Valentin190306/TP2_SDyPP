# Dockerfile Worker A
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir flask

COPY app/app_a.py .

EXPOSE 5001

CMD ["python", "app_a.py"]