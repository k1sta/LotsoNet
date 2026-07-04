FROM python:3.11-alpine

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV LOTSONET_INTERFACE=0.0.0.0

CMD ["python", "bootstrap.py"]
