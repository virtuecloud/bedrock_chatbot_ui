# Base image with Python and required build tools
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y build-essential || cat /var/log/apt/term.log

# Copy only requirements first (for caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy application code
COPY . .

# Expose Streamlit default port
EXPOSE 8501

# Streamlit entrypoint
CMD ["streamlit", "run", "ask_to_ui.py"]
