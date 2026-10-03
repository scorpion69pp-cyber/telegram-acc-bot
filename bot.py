import os
import time
import asyncio
from threading import Thread
from flask import Flask
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# 1. ตั้งค่า Flask Server สำหรับ Render Health Check
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port, use_reloader=False)

# 2. ฟังก์ชัน Selenium ดึงข้อมูล
def scrape_with_selenium(bank_code, account_no):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    
    driver = webdriver.Chrome(options=options)
    
    try:
        # เปิดหน้าเว็บเป้าหมาย
        driver.get("https://acc-name-check.vercel.app/")
        time.sleep(3)
        
        # กำหนดค่ารหัสธนาคารลงใน hidden input
        driver.execute_script(f"document.getElementById('bank').value = '{bank_code}';")
        
        # กรอกเลขบัญชีและกดค้นหา
        account_input = driver.find_element(By.ID, "account")
        account_input.clear()
        account_input.send_keys(account_no)
        account_input.submit()
        
        # รอผลลัพธ์
        time.sleep(4)
        
        result_section = driver.find_element(By.ID, "results")
        result_text = result_section.text.strip()
        
        if not result_text:
            return None
            
        return result_text
        
    except Exception as e:
        return f"เกิดข้อผิดพลาด: {str(e)}"
        
    finally:
        driver.quit()

# 3. จัดการข้อความ Telegram
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    parts = text.split()
    
    if len(parts) != 2:
        return
        
    bank_code = parts[0].upper()
    account_no = parts[1]
    
    loading_msg = await update.message.reply_text(
        f"⏳ กำลังตรวจสอบข้อมูล...\n🏦 ธนาคาร: `{bank_code}`\n🔢 เลขบัญชี: `{account_no}`", 
        parse_mode="Markdown"
    )
    
    # ใช้ asyncio.to_thread เพื่อแยกเธรด ไม่ให้ Selenium บล็อกการทำงานหลักของบอท
    raw_result = await asyncio.to_thread(scrape_with_selenium, bank_code, account_no)
    
    try:
        await loading_msg.delete()
    except Exception:
        pass
    
    if not raw_result or "เกิดข้อผิดพลาด" in raw_result:
        error_msg = (
            f"❌ **ตรวจสอบไม่สำเร็จ**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏦 **ธนาคาร:** `{bank_code}`\n"
            f"🔢 **เลขบัญชี:** `{account_no}`\n"
            f"⚠️ **สถานะ:** ไม่พบข้อมูล หรือระบบขัดข้อง"
        )
        await update.message.reply_text(error_msg, parse_mode="Markdown")
        return

    formatted_msg = (
        f"✅ **ผลการตรวจสอบบัญชี**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏦 **ธนาคาร:** `{bank_code}`\n"
        f"🔢 **เลขบัญชี:** `{account_no}`\n"
        f"👤 **รายละเอียด:** {raw_result}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    
    await update.message.reply_text(formatted_msg, parse_mode="Markdown")

if __name__ == '__main__':
    # รัน Flask บน background thread (ตั้ง daemon=True เพื่อปิดตามโปรเซสหลักเมื่อหยุดทำงาน)
    t = Thread(target=run_web, daemon=True)
    t.start()
    
    TOKEN = os.environ.get("TELEGRAM_TOKEN", "8802624972:AAE9cIT04blM68yLn3u7FgWuerkzKOvMUOA")
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("Bot is running...")
    app.run_polling()
