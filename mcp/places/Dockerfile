FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV PORT=9003
ENV MOCK_MODE=true
EXPOSE 9003

CMD ["python", "-m", "app.server"]
