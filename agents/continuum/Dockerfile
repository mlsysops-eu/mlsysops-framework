# Base image
FROM harbor.nbfc.io/proxy_cache/library/python:3.10-slim

# Set up a working directory
WORKDIR /workdir

# Export PYTHONPATH for the working directory
ENV PYTHONPATH=/workdir

# Copy all application files into the image
COPY ./continuum /workdir/continuum
COPY ./mlsysops /workdir/mlsysops

# Install dependencies from requirements.txt
RUN pip install --no-cache-dir -r /workdir/mlsysops/requirements.txt
RUN pip install --no-cache-dir -r /workdir/continuum/requirements.txt

WORKDIR /workdir/continuum

# Default command to start the application
CMD ["python3", "main.py"]