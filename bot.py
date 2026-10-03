import os
import time
import asyncio
from threading import Thread
from flask import Flask
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Import สำหรับ Telegram
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# ... (โค้ดส่วนอื่น ๆ ด้านล่าง) ...

def scrape_with_selenium(bank_code, account_no):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    
    # 1. กำหนดขนาดหน้าจอมาตรฐาน และหลบเลี่ยงการตรวจจับบอท
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=options)
    
    try:
        print(f"[Scraper] กำลังเปิดเว็บค้นหา: {bank_code} - {account_no}")
        driver.get("https://acc-name-check.vercel.app/")
        
        wait = WebDriverWait(driver, 10)
        
        # 2. รอช่องกรอกเลขบัญชีปรากฏขึ้นมา
        account_input = wait.until(EC.presence_of_element_located((By.ID, "account")))
        
        # 3. กำหนดค่ารหัสธนาคาร พร้อมยิง Event ให้ JS ฝั่งปลายทางรับรู้
        driver.execute_script("""
            var bankInput = document.getElementById('bank');
            if (bankInput) {
                bankInput.value = arguments[0];
                bankInput.dispatchEvent(new Event('input', { bubbles: true }));
                bankInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
        """, bank_code)
        
        # 4. กรอกเลขบัญชี
        account_input.clear()
        account_input.send_keys(account_no)
        
        # 5. กดส่งฟอร์ม
        account_input.submit()
        
        # 6. รอผลลัพธ์ดึงข้อมูลจากระบบปลายทาง
        time.sleep(5)
        
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
    
    TOKEN = os.environ.get("TELEGRAM_TOKEN", "...")
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("Bot is running...")
    app.run_polling()
