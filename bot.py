import os
import time
import asyncio
from threading import Thread
from flask import Flask

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# ==============================================================================
# 1. FLASK WEB SERVER (สำหรับ Render Health Check / Sleep Prevention)
# ==============================================================================
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    # use_reloader=False ป้องกันไม่ให้ Flask สร้าง Process ซ้ำจนเกิด Conflict
    web_app.run(host="0.0.0.0", port=port, use_reloader=False)


# ==============================================================================
# 2. BANK CODE CONVERTER
# ==============================================================================
def convert_bank_code(input_str: str) -> str:
    """แปลงคำค้นหาภาษาไทยหรือชื่อย่อ ให้เป็นรหัสธนาคารที่เว็บปลายทางรองรับ"""
    if not input_str:
        return ""
    name = input_str.strip().lower()

    if "กสิกรไทย" in name or name == "kbank":
        return "kbank"
    if "ไทยพาณิชย์" in name or name == "scb":
        return "scb"
    if "กรุงเทพ" in name or name == "bbl":
        return "bbl"
    if "กรุงไทย" in name or name == "ktb":
        return "ktb"
    if "กรุงศรี" in name or name == "bay":
        return "bay"
    if "ทหารไทย" in name or "ทีทีบี" in name or name == "ttb":
        return "ttb"
    if "ออมสิน" in name or name == "gsb":
        return "gsb"
    if "ธกส" in name or name == "baac":
        return "baac"
    if "เกียรตินาคินภัทร" in name or name == "kkp":
        return "kkp"
    if "ซีไอเอ็มบี" in name or name == "cimb":
        return "cimb"
    if "ยูโอบี" in name or name == "uob":
        return "uob"
    if "แลนด์แอนด์เฮ้าส์" in name or name == "lhbank":
        return "lhbank"
    if "ธอส" in name or name == "ghb":
        return "ghb"
    if "อิสลาม" in name or name == "isbt":
        return "isbt"
    if "ไทยเครดิต" in name or name == "tcrb":
        return "tcrb"
    if "ไอซีบีซี" in name or name == "icbc":
        return "icbc"

    return name  # คืนค่าเดิมกรณีพิมพ์เป็นรหัสตรงอยู่แล้ว


# ==============================================================================
# 3. SELENIUM SCRAPER
# ==============================================================================
def scrape_with_selenium(bank_code: str, account_no: str) -> str:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # ซ่อนร่องรอยการเป็น Headless Browser
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=options)
    
    # ลบ Flag webdriver เพื่อหลบเลี่ยงการตรวจจับ
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    try:
        print(f"[Scraper] กำลังเปิดเว็บค้นหา: {bank_code} - {account_no}")
        driver.get("https://acc-name-check.vercel.app/")

        wait = WebDriverWait(driver, 12)

        # รอช่องกรอกเลขบัญชีปรากฏ
        account_input = wait.until(EC.presence_of_element_located((By.ID, "account")))

        # กำหนดค่ารหัสธนาคาร และส่ง Event ให้ JavaScript ฝั่งปลายทางรับรู้
        driver.execute_script("""
            var bankInput = document.getElementById('bank');
            if (bankInput) {
                bankInput.value = arguments[0];
                bankInput.dispatchEvent(new Event('input', { bubbles: true }));
                bankInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
        """, bank_code)

        # กรอกเลขบัญชี
        account_input.clear()
        account_input.send_keys(account_no)
        
        # กด ENTER เพื่อส่งฟอร์ม
        account_input.send_keys(Keys.ENTER)

        # รอระบบดึงผลลัพธ์
        time.sleep(4)

        result_section = driver.find_element(By.ID, "results")
        result_text = result_section.text.strip()

        print(f"[Scraper] ผลลัพธ์ที่ได้: {result_text}")

        if not result_text:
            return None

        return result_text

    except Exception as e:
        print(f"[Scraper Error] {str(e)}")
        return f"เกิดข้อผิดพลาด: {str(e)}"

    finally:
        driver.quit()


# ==============================================================================
# 4. TELEGRAM BOT HANDLER
# ==============================================================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text:
        return

    text = msg.text.strip()
    parts = text.split()

    # รับเฉพาะข้อความรูปแบบ [BANK] [ACCOUNT_NO]
    if len(parts) != 2:
        return

    raw_bank_input = parts[0]
    account_no = parts[1]

    # แปลงรหัสธนาคารผ่านฟังก์ชันที่กำหนด
    bank_code = convert_bank_code(raw_bank_input)
    display_bank = bank_code.upper()

    # ข้อความสถานะการทำงาน
    loading_msg = await msg.reply_text(
        f"⏳ <b>กำลังตรวจสอบข้อมูล...</b>\n"
        f"🏦 ธนาคาร: <code>{display_bank}</code>\n"
        f"🔢 เลขบัญชี: <code>{account_no}</code>",
        parse_mode="HTML"
    )

    # รัน Selenium บน Thread แยก
    raw_result = await asyncio.to_thread(scrape_with_selenium, bank_code, account_no)

    try:
        await loading_msg.delete()
    except Exception:
        pass

    if not raw_result or "เกิดข้อผิดพลาด" in raw_result:
        error_msg = (
            f"❌ <b>ตรวจสอบไม่สำเร็จ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏦 <b>ธนาคาร:</b> <code>{display_bank}</code>\n"
            f"🔢 <b>เลขบัญชี:</b> <code>{account_no}</code>\n"
            f"⚠️ <b>สถานะ:</b> ไม่พบข้อมูล หรือระบบขัดข้อง"
        )
        await msg.reply_text(error_msg, parse_mode="HTML")
        return

    clean_result = raw_result.replace("<", "&lt;").replace(">", "&gt;")

    formatted_msg = (
        f"✅ <b>ผลการตรวจสอบบัญชี</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏦 <b>ธนาคาร:</b> <code>{display_bank}</code>\n"
        f"🔢 <b>เลขบัญชี:</b> <code>{account_no}</code>\n"
        f"👤 <b>รายละเอียด:</b> {clean_result}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

    await msg.reply_text(formatted_msg, parse_mode="HTML")


# ==============================================================================
# 5. MAIN EXECUTION
# ==============================================================================
if __name__ == '__main__':
    t = Thread(target=run_web, daemon=True)
    t.start()

    token = os.environ.get("TELEGRAM_TOKEN", "ใส่_TOKEN_ตรงนี้ถ้าทดสอบแบบ_LOCAL")

    app = ApplicationBuilder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Bot is running...")
    app.run_polling()
