# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3.10-slim-bullseye




# Keeps Python from generating .pyc files in the container, Turns off buffering for easier container logging
ENV PYTHONDONTWRITEBYTECODE=1\
 PYTHONUNBUFFERED=1 \
 PYTHONPATH=/app



WORKDIR /app

# Install pip requirements
COPY requirements.txt .
#Install system updates
RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# Creates a non-root user with an explicit UID and adds permission to access the /app folder
# For more info, please refer to https://aka.ms/vscode-docker-python-configure-containers
RUN adduser -u 5678 --disabled-password --gecos "" appuser \
    && chown -R appuser /app \
    && chmod -R a+r /app/dashboard

# Download NLTK stopwords once during build
#RUN python -m nltk.downloader stopwords &&\ 
 #   python -m nltk.downloader punkt

# Preload a summarization model to cache it in the image (small models only!)
#RUN python -c "from transformers import pipeline; pipeline('summarization', model='sshleifer/distilbart-cnn-12-6')"


USER appuser


EXPOSE 8000

# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
# File wsgi.py was not found. Please enter the Python path to wsgi file.
CMD ["sh", "-c", "python manage.py collectstatic --noinput && gunicorn dashboard.wsgi:application --bind 0.0.0.0:8000 --timeout 300"]