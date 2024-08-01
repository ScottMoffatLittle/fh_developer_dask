# Use CUDA base image
FROM nvidia/cuda:12.5.1-cudnn-runtime-ubuntu20.04

WORKDIR /app

# Copy the necessary files into the container
COPY inference.py /app/inference.py
COPY requirements.txt /app/requirements.txt
ADD test_images /app/test_images

# Install necessary system packages
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and setuptools
RUN pip3 install --upgrade pip setuptools

# Install the remaining packages
RUN pip3 install --no-cache-dir -r requirements.txt

# Install flash_attn separately to handle CUDA dependencies
RUN pip3 install --no-cache-dir flash_attn

# Run the inference script by default
CMD ["python3", "/app/inference.py"]