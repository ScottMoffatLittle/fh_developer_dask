FROM pytorch/pytorch:2.2.2-cuda11.7-cudnn8-runtime

WORKDIR /app

# Copy the necessary files into the container
COPY inference.py /app/inference.py
COPY requirements.txt /app/requirements.txt
ADD test_images /app/test_images

# Upgrade pip and setuptools
RUN pip install --upgrade pip setuptools

# Install necessary system packages
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install the remaining packages
RUN pip install --no-cache-dir -r requirements.txt

# Set the CUDA_HOME environment variable
ENV CUDA_HOME=/usr/local/cuda

# Install flash_attn separately to handle CUDA dependencies
RUN pip install --no-cache-dir flash_attn

# Run the inference script by default
CMD ["python", "/app/inference.py"]