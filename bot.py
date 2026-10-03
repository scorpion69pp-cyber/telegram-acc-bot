import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

def scrape_with_selenium(bank_code, account_no):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    
    # Render จะรันบน Linux บรรทัดนี้จะเรียก Chrome อัตโนมัติ
    driver = webdriver.Chrome(options=options)
    
    try:
        # 1. เปิดหน้าเว็บเป้าหมาย เพื่อสร้าง Session
        driver.get("https://acc-name-check.vercel.app/")
        time.sleep(3)
        
        # 2. กำหนดค่ารหัสธนาคารลงใน hidden input
        driver.execute_script(f"document.getElementById('bank').value = '{bank_code}';")
        
        # 3. กรอกเลขบัญชี
        account_input = driver.find_element(By.ID, "account")
        account_input.clear()
        account_input.send_keys(account_no)
        account_input.submit()
        
        # 4. รอผลลัพธ์ปรากฏ
        time.sleep(4)
        
        # 5. ดึงข้อมูลผลลัพธ์
        result_section = driver.find_element(By.ID, "results")
        result_text = result_section.text.strip()
        
        if not result_text:
            return None
            
        return result_text
        
    except Exception as e:
        return f"เกิดข้อผิดพลาด: {str(e)}"
        
    finally:
        driver.quit()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    parts = text.split()
    
    # ตรวจสอบว่าผู้ใช้พิมพ์ส่งมา 2 ค่า (เช่น KBANK และ เลขบัญชี)
    if len(parts) != 2:
        return # ถ้าไม่ใช่รูปแบบที่กำหนด ให้ข้ามไปไม่ต้องตอบกลับ
        
    bank_code = parts[0].upper()
    account_no = parts[1]
    
    # ส่งข้อความแจ้งสถานะกำลังค้นหา
    loading_msg = await update.message.reply_text(f"⏳ กำลังตรวจสอบข้อมูล...\n🏦 ธนาคาร: `{bank_code}`\n🔢 เลขบัญชี: `{account_no}`", parse_mode="Markdown")
    
    # รัน Selenium เพื่อดึงข้อมูล
    raw_result = scrape_with_selenium(bank_code, account_no)
    
    # ลบข้อความกำลังโหลดทิ้ง เพื่อความสะอาดเรียบร้อย
    await loading_msg.delete()
    
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

    # จัดรูปแบบข้อความผลลัพธ์ให้สวยงามและอ่านง่าย
    formatted_msg = (
        f"✅ **ผลการตรวจสอบบัญชี**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏦 **ธนาคาร:** `{bank_code}`\n"
        f"🔢 **เลขบัญชี:** `{account_no}`\n"
        f"👤 **รายละเอียด:** {raw_result}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    
    await update.message.reply_text(formatted_msg, parse_mode="Markdown")

import os
from threading import Thread
from flask import Flask

# สร้าง Flask เล็กๆ เพื่อให้ Render ผ่าน Health Check (กันแอปดับ)
web_app = Flask('')

@web_app.route('/')
def home():
    return "Bot is running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

# ... (ฟังก์ชัน scrape_with_selenium และ handle_message เหมือนเดิม) ...

if __name__ == '__main__':
    # รัน Flask บนเธรดแยก
    t = Thread(target=run_web)
    t.start()
    
    TOKEN = "8802624972:AAE9cIT04blM68yLn3u7FgWuerkzKOvMUOA"
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("Bot is running...")
    app.run_polling()