import requests
import time

SERVER_URL = "http://localhost:8080/scan-client"
SCANNER_ID = "PC-Scanner-01"

def send_scan(code: str):
    data = {"code": code, "scanner_id": SCANNER_ID}
    try:
        response = requests.post(SERVER_URL, data=data, timeout=0.15)
        if response.status_code == 200:
            print(f"Scan erfasst: {code}")
        else:
            print(f"Fehler: {response.text}")
    except Exception as e:
        print(f"Verbindungsfehler: {e}")

def main():
    print("Scanner bereit. Code eingeben ('exit' zum Beenden):")
    while True:
        code = input("> ")
        if code.lower() == "exit":
            break
        if code:
            start_time = time.time()
            send_scan(code)
            print(f"\ttotal: {time.time() - start_time}")

if __name__ == "__main__":
    main()