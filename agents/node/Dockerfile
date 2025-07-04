# Base image
FROM harbor.nbfc.io/proxy_cache/library/python:3.10-slim

# Set up a working directory
WORKDIR /workdir

# Copy requirements to the image
COPY requirements.txt /workdir

# Install dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Export PYTHONPATH for the working directory
ENV PYTHONPATH=/workdir

# Copy all application files into the image
COPY . /workdir

# Default command to start the application
CMD ["python3", "main.py"]