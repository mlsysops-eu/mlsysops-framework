# Use the official slim Python image as the base image
FROM harbor.nbfc.io/proxy_cache/library/python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the necessary scripts into the container
COPY TcpClient.py .
COPY TcpServer.py .
COPY requirements.txt .
# Install any required Python dependencies (no additional ones in this case)
RUN pip install --no-cache-dir -r requirements.txt

# Allow the command to define which script to run (server or client)
ENTRYPOINT ["sh", "-c"]

# CMD will execute the desired script based on the argument passed
CMD ["python TcpServer.py"]