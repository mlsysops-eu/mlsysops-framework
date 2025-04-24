FROM python:3.10

WORKDIR /appServer

COPY . .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port FastAPI will run on
EXPOSE 8091

# Start the FastAPI server
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8091"]
