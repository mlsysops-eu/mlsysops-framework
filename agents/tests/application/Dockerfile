# Use the official slim Python image as the base image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the necessary scripts into the container
COPY TcpClient.py .
COPY TcpServer.py .

# Install any required Python dependencies (no additional ones in this case)
RUN pip install --no-cache-dir mlstelemetry

# Allow the command to define which script to run (server or client)
ENTRYPOINT ["sh", "-c"]

# CMD will execute the desired script based on the argument passed
CMD ["python TcpServer.py"]