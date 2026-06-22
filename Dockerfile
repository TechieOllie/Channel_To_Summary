FROM python:3.12-slim

WORKDIR /app

# Install build dependencies for llama-cpp-python
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python3 download_model.py

VOLUME ["/app/data"]

CMD ["python", "main.py"]
