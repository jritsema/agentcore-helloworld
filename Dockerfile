FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

# Copy uv files
COPY piplock.txt ./

# Install dependencies (including strands-agents)
RUN pip3 install -r piplock.txt

# Copy agent file
COPY main.py ./

# Expose port
EXPOSE 8080

# Run application
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
