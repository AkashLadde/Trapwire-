FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application
COPY . .

EXPOSE 8080

# Start the TRAPWIRE defender server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
