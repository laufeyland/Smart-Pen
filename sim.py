import requests
import random
import time


SERVER_URL = "http://127.0.0.1:8000/data" 

def simulate_mpu_data():
    """
    Generate pseudo-random MPU6050 data that looks realistic.
    - ax, ay, az in g (±2g range)
    - gx, gy, gz in deg/s (±250 range)
    """
    ax = round(random.uniform(-1.5, 1.5), 3)
    ay = round(random.uniform(-1.5, 1.5), 3)
    az = round(random.uniform(-1.5, 1.5), 3)
    gx = round(random.uniform(-180, 180), 3)
    gy = round(random.uniform(-180, 180), 3)
    gz = round(random.uniform(-180, 180), 3)
    temp = round(random.uniform(20, 35), 2)
    return {
        "ax": ax, "ay": ay, "az": az,
        "gx": gx, "gy": gy, "gz": gz,
        "temp": temp,
        "timestamp": time.time()
    }

def main():
    print("🧠 Simulating MPU6050 data stream...")
    while True:
        data = simulate_mpu_data()
        try:
            response = requests.post(SERVER_URL, json=data, timeout=2)
            print(f"Sent: {data} -> {response.status_code}")
        except Exception as e:
            print(f"Error sending data: {e}")
        time.sleep(0.1)  # send data at ~10Hz

if __name__ == "__main__":
    main()
