FROM python:3.11-slim

# Tell matplotlib not to look for a display
ENV MPLBACKEND=Agg
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# fontconfig: matplotlib font rendering
# libgomp1: numpy/scipy parallel operations
RUN apt-get update && apt-get install -y --no-install-recommends \
    libfontconfig1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (cached layer — only re-runs when requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
