import time
import json
import random
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

# --- CONFIGURATION ---
MIN_PRICE = 35000
MAX_PRICE = 55000

# List of Pakistani Airports to identify "Local" flights
PAK_AIRPORTS = [
    "KHI", "LHE", "ISB", "PEW", "MUX", "SKT", "LYP", 
    "GIL", "UET", "GWD", "TUK", "DGE", "BHV", "PJG", "RZS"
]

def generate_fake_price():
    return random.randint(MIN_PRICE, MAX_PRICE)

def get_duration(dep, arr):
    try:
        FMT = '%H:%M'
        tdelta = datetime.strptime(arr, FMT) - datetime.strptime(dep, FMT)
        if tdelta.days < 0: tdelta = timedelta(days=0, seconds=tdelta.seconds)
        total_seconds = tdelta.total_seconds()
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        return f"{hours}h {minutes}m"
    except: return "2h 00m"

def add_time(start_time_str, minutes_to_add):
    try:
        FMT = '%H:%M'
        dt = datetime.strptime(start_time_str, FMT)
        new_dt = dt + timedelta(minutes=minutes_to_add)
        return new_dt.strftime(FMT)
    except:
        return start_time_str

def create_synthetic_flights(origin, destination, date_str):
    results = []
    current_id = 1
    
    # Airline Sequence: Airblue -> Fly Jinnah -> Air Sial
    airlines_sequence = [
        ("Airblue", "PA"),
        ("Fly Jinnah", "9P"),
        ("Air Sial", "PF")
    ]
    
    # Base times for the 4 pages (to make them distinct)
    # Page 1 (Morning), Page 2 (Noon), Page 3 (Afternoon), Page 4 (Evening)
    page_start_hours = [6, 10, 14, 18]
    
    # LOOP 1: PAGES (4 Pages)
    for page_idx, base_hour in enumerate(page_start_hours):
        
        # LOOP 2: AIRLINES (3 Airlines per Page)
        for name, code in airlines_sequence:
            
            # Start time for this airline's block on this page
            current_time = f"{base_hour:02d}:{random.randint(0, 30):02d}"
            
            # LOOP 3: FLIGHTS (5 Flights per Airline)
            for i in range(5):
                # 1. Increment time for the next flight in this block
                gap = random.randint(45, 90) # Gap between flights
                depart_time = add_time(current_time, gap)
                current_time = depart_time # Update for next iteration
                
                # 2. Duration
                duration_mins = random.randint(105, 130)
                arrive_time = add_time(depart_time, duration_mins)
                
                # 3. Flight Number
                flight_num = f"{code}-{random.randint(100, 999)}"
                
                results.append({
                    "id": current_id,
                    "airline": name,
                    "flight_no": flight_num,
                    "origin": origin,
                    "destination": destination,
                    "date": date_str,
                    "depart_time": depart_time,
                    "arrive_time": arrive_time,
                    "duration": get_duration(depart_time, arrive_time),
                    "price": generate_fake_price(),
                    "currency": "PKR",
                    "is_scraper": True
                })
                current_id += 1

    # CRITICAL: This return is OUTSIDE all loops. 
    # It returns 60 flights total.
    return results

@app.route('/')
def home(): return send_file('index.html')

@app.route('/api/search', methods=['POST'])
def search_flights():
    data = request.json
    origin = data.get('origin', '').upper()
    destination = data.get('destination', '').upper()
    date = data.get('date')
    
    if not origin or not destination or not date: return jsonify([])

    # International Check
    if origin not in PAK_AIRPORTS or destination not in PAK_AIRPORTS:
        return jsonify([])

    # Local Check
    final_results = create_synthetic_flights(origin, destination, date)
    return jsonify(final_results)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860)