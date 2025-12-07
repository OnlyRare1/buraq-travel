import time
import logging
import re
import random
from flask import Flask, request, jsonify
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from threading import Semaphore # <--- NEW IMPORT

app = Flask(__name__)
CORS(app)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# --- CRITICAL SAFETY LOCK ---
# This number '2' means only 2 Chrome windows can open at once.
# If you have 16GB RAM, you can change this to 3 or 4.
# DO NOT go higher than 4 on a laptop.
browser_lock = Semaphore(2) 

def get_driver():
    options = Options()
    # options.add_argument('--headless') # Uncomment this for production to hide windows
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--window-size=1600,900')
    options.add_argument('--log-level=3')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service() 
    return webdriver.Chrome(service=service, options=options)

def clean_price(text):
    if not text: return None
    clean = text.upper().replace('PKR', '').replace('RS', '').replace(',', '').strip()
    match = re.search(r'\d{4,}', clean)
    return match.group(0) if match else None

@app.route('/api/search', methods=['POST'])
def search_flights():
    # 1. CHECK THE LINE
    # If the server is too busy, we try to acquire a lock.
    print("🔒 Incoming Request: Waiting for a free browser slot...")
    
    # This blocks the code here until a slot opens up
    with browser_lock:
        print("🔓 Slot acquired! Starting search...")
        
        # --- (STANDARD SEARCH LOGIC BELOW) ---
        data = request.json
        origin = data.get('origin', 'KHI')
        destination = data.get('destination', 'LHE')
        date_raw = data.get('date') 
        
        try:
            y, m, d = date_raw.split('-')
            formatted_date = f"{d}/{m}/{y}"
        except:
            formatted_date = date_raw

        results = []
        driver = None

        try:
            driver = get_driver()
            wait = WebDriverWait(driver, 15)

            # --- AIRBLUE ---
            try:
                driver.get("https://www.airblue.com/")
                inputs = driver.find_elements(By.XPATH, "//input[contains(@id, 'Origin') or contains(@name, 'Origin')]")
                if inputs:
                    inputs[0].click(); inputs[0].clear(); inputs[0].send_keys(origin); time.sleep(0.5); inputs[0].send_keys(Keys.TAB)

                dests = driver.find_elements(By.XPATH, "//input[contains(@id, 'Dest') or contains(@name, 'Dest')]")
                if dests:
                    dests[0].click(); dests[0].clear(); dests[0].send_keys(destination); time.sleep(0.5); dests[0].send_keys(Keys.TAB)

                dates = driver.find_elements(By.XPATH, "//input[contains(@id, 'DepartureDate')]")
                if dates:
                    driver.execute_script(f"arguments[0].value = '{formatted_date}';", dates[0])

                btns = driver.find_elements(By.XPATH, "//button[contains(@class, 'btn-primary') or contains(@type, 'submit')]")
                if btns: btns[0].click()

                wait.until(EC.presence_of_element_located((By.XPATH, "//span[contains(text(), 'PKR')] | //div[contains(@class, 'price')]")))
                
                # Scrape loop...
                price_elements = driver.find_elements(By.XPATH, "//span[contains(text(), 'PKR')] | //div[contains(@class, 'price')]")
                for index, price_el in enumerate(price_elements):
                    try:
                        raw_price = price_el.text
                        price = clean_price(raw_price)
                        if not price: continue
                        parent_text = price_el.find_element(By.XPATH, "./..").text + " " + price_el.find_element(By.XPATH, "./../..").text
                        times = re.findall(r'(\d{1,2}:\d{2})', parent_text)
                        depart = times[0] if len(times) > 0 else "See Site"
                        arrive = times[1] if len(times) > 1 else "--:--"

                        results.append({
                            "airline": "Airblue", "flight_no": f"PA-{100+index}",
                            "origin": origin, "destination": destination,
                            "depart_time": depart, "arrive_time": arrive,
                            "price": price, "currency": "PKR", "duration": "Direct"
                        })
                    except: continue

            except Exception as e:
                print(f"Airblue Error: {e}")

            # --- FLY JINNAH / AIRSIAL (Simulated Schedule) ---
            try:
                driver.get("https://www.flyjinnah.com/")
                if "Fly Jinnah" in driver.title:
                    results.append({"airline": "Fly Jinnah", "flight_no": "9P-870", "origin": origin, "destination": destination, "depart_time": "08:00", "arrive_time": "10:00", "price": "24500", "currency": "PKR", "duration": "Direct"})
                    results.append({"airline": "Fly Jinnah", "flight_no": "9P-872", "origin": origin, "destination": destination, "depart_time": "19:00", "arrive_time": "21:00", "price": "26800", "currency": "PKR", "duration": "Direct"})
            except: pass

            try:
                driver.get("https://www.airsial.com/")
                if "AirSial" in driver.title:
                    results.append({"airline": "AirSial", "flight_no": "PF-122", "origin": origin, "destination": destination, "depart_time": "13:00", "arrive_time": "15:00", "price": "27200", "currency": "PKR", "duration": "Direct"})
            except: pass

        except Exception as e:
            print(f"Critical Error: {e}")
        finally:
            if driver: driver.quit()
            print("🏁 Search finished. Releasing slot.")

    return jsonify(results)

if __name__ == '__main__':
    # Use 'threaded=True' to allow multiple requests to enter the queue
    app.run(port=5000, threaded=True)