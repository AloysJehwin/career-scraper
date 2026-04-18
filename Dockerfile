FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir . && \
    playwright install chromium --with-deps

EXPOSE 8000
CMD ["career-api"]
