FROM python:3.9.7-slim

COPY ./app /app

RUN mkdir -p /data
RUN pip install -r /app/requirement.txt

CMD ["python", "-u", "/app/main.py"]