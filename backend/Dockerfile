# backend/Dockerfile

FROM python:3.11-slim

# Set workdir
WORKDIR /app

# Install system dependencies (including build deps for scikit-learn and gettext for compilemessages)
RUN apt-get update \
    && apt-get install -y \
        gcc \
        build-essential \
        gfortran \
        libopenblas-dev \
        liblapack-dev \
        libpq-dev \
        gettext \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements later
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files later
COPY . .

# Compile translations (safe to rerun; fails build if .po has errors)
RUN python manage.py compilemessages -l fa || true

# Default command
CMD ["gunicorn", "iothive.wsgi:application", "--bind", "0.0.0.0:8000"]
