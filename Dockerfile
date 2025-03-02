# Use the official Python base image
FROM python:3.9-slim

# Install required system packages
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY . .

# Set up Xvfb
ENV DISPLAY=:99
ENV PYTHONUNBUFFERED=1

# Start Xvfb and run the application
CMD Xvfb :99 -screen 0 1024x768x16 & streamlit run app.py --server.address=0.0.0.0 --server.port=8501
