FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV PORT=9004
ENV MOCK_MODE=true
EXPOSE 9004

CMD ["python", "-m", "app.server"]
