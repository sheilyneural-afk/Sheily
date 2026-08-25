FROM python:3.12-slim AS runtime

ARG SERVICE_DIR
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/packages/python

WORKDIR /app
RUN addgroup --system noosfera && adduser --system --ingroup noosfera noosfera
COPY pyproject.toml /app/pyproject.toml
COPY packages/python/noosfera_core /app/packages/python/noosfera_core
COPY services/${SERVICE_DIR}/ /app/service/
RUN pip install --no-cache-dir .
USER noosfera
WORKDIR /app/service
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
