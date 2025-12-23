# Base image
FROM harbor.nbfc.io/proxy_cache/library/python:3.10-slim

# Set up a working directory
WORKDIR /workdir

# Copy all application files into the image
COPY ./cluster /workdir/cluster
COPY ./mlsysops /workdir/mlsysops

# Install dependencies from requirements.txt
RUN pip install --no-cache-dir -r /workdir/mlsysops/requirements.txt
RUN pip install --no-cache-dir -r /workdir/cluster/requirements.txt
RUN pip install --no-cache-dir -r /workdir/cluster/fluidity/requirements.txt


# Set up a working directory
WORKDIR /workdir/cluster

# Export PYTHONPATH for the working directory
ENV PYTHONPATH=/workdir:/workdir/cluster:/workdir/cluster/fluidity

# Default command to start the application
CMD ["python3", "main.py"]