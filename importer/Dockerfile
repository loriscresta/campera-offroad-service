FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir "psycopg[binary]==3.2.1"
COPY import_region_to_pg.py .
# Esegue l'import completo una volta e termina.
CMD ["python", "import_region_to_pg.py"]
