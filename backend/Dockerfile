# backend/Dockerfile

FROM python:3.11-slim

# Set workdir
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y gcc libpq-dev

# Copy and install requirements later
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files later
COPY . .

# Default command
CMD ["gunicorn", "iothive.wsgi:application", "--bind", "0.0.0.0:8000"]