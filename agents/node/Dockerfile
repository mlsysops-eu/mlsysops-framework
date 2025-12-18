# Base image
FROM harbor.nbfc.io/proxy_cache/library/python:3.10-slim

# Export PYTHONPATH for the working directory
ENV PYTHONPATH=/workdir

WORKDIR /workdir

# Copy all application files into the image
COPY ./node /workdir/node
COPY ./mlsysops /workdir/mlsysops

# Set up a working directory
WORKDIR /workdir/node

# Install dependencies from requirements.txt
RUN pip install --no-cache-dir -r /workdir/mlsysops/requirements.txt
RUN pip install --no-cache-dir -r /workdir/node/requirements.txt

# Default command to start the application
CMD ["python3", "main.py"]