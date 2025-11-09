# pen_client.py
import websocket
import time
import json

def on_open(ws):
    print("Connected to server as pen.")
    # Send periodic heartbeat or data
    def run():
        while True:
            ws.send(json.dumps({"status": "alive"}))
            time.sleep(1)
    run()

def on_message(ws, message):
    print("From server:", message)

def on_close(ws, code, msg):
    print("Pen disconnected from server.")

if __name__ == "__main__":
    ws = websocket.WebSocketApp(
        "ws://127.0.0.1:8000/ws/pen",
        on_open=on_open,
        on_message=on_message,
        on_close=on_close,
    )
    ws.run_forever()
