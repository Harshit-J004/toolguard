# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the project files
COPY . .

# Install ToolGuard with server and enterprise extensions
RUN pip install --no-cache-dir -e .[server,enterprise]

# Expose the proxy port
EXPOSE 8080

# The default command runs the ToolGuard proxy serve command
# ENTRYPOINT is the fixed binary; CMD provides overridable defaults
# If no security.yaml is mounted, serve_cmd uses a default permissive policy
ENTRYPOINT ["toolguard", "serve", "--host", "0.0.0.0", "--port", "8080"]
CMD ["--policy", "/app/security.yaml"]
