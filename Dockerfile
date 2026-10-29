FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1

# Chrome browser + tools
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget curl unzip ca-certificates gnupg fonts-liberation \
    && wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y --no-install-recommends /tmp/chrome.deb \
    && rm -rf /tmp/chrome.deb /var/lib/apt/lists/*

# Chrome driver matching the installed Chrome version
RUN CHROME_VER=$(google-chrome --version | awk '{print $3}') \
    && wget -q -O /tmp/cd.zip "https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VER}/linux64/chromedriver-linux64.zip" \
    && unzip -q /tmp/cd.zip -d /tmp \
    && mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver \
    && chmod +x /usr/local/bin/chromedriver \
    && rm -rf /tmp/cd.zip /tmp/chromedriver-linux64

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

ENV REGISTRATION=FA23-BDS-002
EXPOSE 7000
CMD ["python", "app.py"]
