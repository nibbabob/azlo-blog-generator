# 1. Base Image
# Start with a slim and secure Python base image.
FROM python:3.13.5-slim

# 2. Set Working Directory
WORKDIR /app

# 3. Install System Dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    fontconfig \
    fonts-freefont-ttf \
    && rm -rf /var/lib/apt/lists/*

# 4. Copy and Install Python Requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy Project Files
COPY . .

# 6. Create and Define Volume for Output
RUN mkdir /app/output
VOLUME /app/output

# 7. Command
# The container expects the API key to be present as an environment
# variable when it's run, but it's no longer baked into the image.
CMD ["python", "main.py", "blog_titles.csv", "/app/output"]