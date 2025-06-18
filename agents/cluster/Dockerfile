# Base image
FROM python:3.10-slim

# Set up a working directory
WORKDIR /workdir

# Copy all application files into the image
COPY . /workdir

# Install dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r fluidity/requirements.txt
RUN #pip install mlsysops-0.0.0-py3-none-any.whl

# Export PYTHONPATH for the working directory
ENV PYTHONPATH=/workdir


# Default command to start the application
CMD ["python3", "main.py"]