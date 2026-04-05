FROM python:3.13-slim

# Prevent Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1

# Ensure logs appear immediately
ENV PYTHONUNBUFFERED=1

# Service identity (can be overridden)
ENV SERVICE_NAME=receipt

# Set working directory
WORKDIR /app
COPY shared/ /app/shared
COPY receipt_service/ /app


# Install dependencies first (better layer caching)
COPY receipt_service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Expose the service port
EXPOSE 5000

# Run the service
CMD ["python", "receipt_service.py"]