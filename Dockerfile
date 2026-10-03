FROM python:3.10-slim

WORKDIR /app

# อัปเดตระบบ ดาวน์โหลด และติดตั้ง Google Chrome 
# (วิธีนี้ apt จะไปตามหาไลบรารีที่ Chrome ต้องการมาติดตั้งให้อัตโนมัติ หมดปัญหาหาไฟล์ไม่เจอ)
RUN apt-get update && apt-get install -y wget \
    && wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y ./google-chrome-stable_current_amd64.deb \
    && rm google-chrome-stable_current_amd64.deb \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# คัดลอกและติดตั้งไลบรารี Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# สั่งรันบอท
CMD ["python", "bot.py"]
