FROM python:3.10-slim

# ติดตั้ง Google Chrome และ Dependencies ที่จำเป็นสำหรับ Selenium
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg \
    unzip \
    libxi6 \
    libgconf-2-4 \
    libnss3 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libgdk-pixbuf2.0-0 \
    libnspr4 \
    libx11-xcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxrandr2 \
    libxrender1 \
    libxtst6 \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# ติดตั้ง ChromeDriver และ Google Chrome เวอร์ชันล่าสุด
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | awk -F'.' '{print $1}') \
    && CHROMEDRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROME_VERSION") \
    && wget -N https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip \
    && unzip chromedriver_linux64.zip \
    && chmod +x chromedriver \
    && mv chromedriver /usr/local/bin/ \
    && rm chromedriver_linux64.zip

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# กำหนดให้รันไฟล์ bot.py
CMD ["python", "bot.py"]