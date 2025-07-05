# Use an official Python runtime as a parent image
FROM python:3.11-slim

WORKDIR /

# Upgrade pip to the latest version
RUN pip install --no-cache-dir --upgrade pip

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port your FastAPI app runs on
EXPOSE 5000

CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "5000", "--reload"]
