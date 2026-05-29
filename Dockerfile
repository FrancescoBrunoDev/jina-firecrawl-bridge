FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/ src/

# Expose port
EXPOSE 3838

# Run
CMD ["python", "-m", "src.main"]
