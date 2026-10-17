FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY app.py /app/app.py
RUN groupadd --system --gid 10001 nexus && useradd --system --uid 10001 --gid nexus nexus
USER nexus
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=10 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
CMD ["python", "/app/app.py"]
