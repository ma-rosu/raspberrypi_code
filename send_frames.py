import base64
import time
import cv2
import websocket
import threading
import json
from agents.speak_agent import SpeakAgent

sends_count = 0
results_count = 0

def websocket_api():
    global sends_count, results_count 

    WS_URL = "ws://18.197.7.3:5001/ws"

    latest_frame = None
    lock = threading.Lock()
    stop_event = threading.Event()

    def on_message(ws, message):
        global results_count
        try:
            result = json.loads(message)
            results_count += 1
            
            reminders = result['reminders']
            if len(reminders) > 0:
                for reminder in reminders:
                        SpeakAgent('~'+reminder)

            if result['fall'] == 1:
                SpeakAgent('fall')

            if result['sleep'] == 1:
                SpeakAgent('sleep')

            if result['move'] == 1:
                SpeakAgent('move')

        except Exception as e:
            print("Error parsing message:", e)

    def on_error(ws, error):
        print("WebSocket error:", error)

    def on_close(ws, close_status_code, close_msg):
        print("WebSocket closed")

    def on_open(ws):
        def run():
            global sends_count, results_count, current_sleep_time, initial_sleep_time, min_sleep_time, max_sleep_time, sleep_adjustment_factor

            while not stop_event.is_set():
                with lock:
                    frame_copy = latest_frame.copy() if latest_frame is not None else None

                if frame_copy is not None:
                    _, buffer = cv2.imencode('.jpg', frame_copy, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
                    jpg_as_text = base64.b64encode(buffer).decode('utf-8')
                    try:
                        ws.send(jpg_as_text)
                        sends_count += 1
                    except Exception as e:
                        print("Error sending message:", e)
                        print(sends_count)

                if sends_count > (results_count + 1):
                    current_sleep_time = min(current_sleep_time + sleep_adjustment_factor, max_sleep_time)
                elif sends_count < (results_count + 1):
                    current_sleep_time = max(current_sleep_time - sleep_adjustment_factor, min_sleep_time)
                else:
                    current_sleep_time = max(current_sleep_time - sleep_adjustment_factor, min_sleep_time)

                

                time.sleep(current_sleep_time)


        threading.Thread(target=run).start()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Cannot open camera")
        exit()

    ws = websocket.WebSocketApp(
        WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    ws_thread = threading.Thread(target=ws.run_forever)
    ws_thread.start()

    
    prev_time = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Can't receive frame. Exiting...")
                break

            
            current_time_cap = time.time()
            fps = 1 / (current_time_cap - prev_time)
            prev_time = current_time_cap

            
            cv2.putText(frame, f"FPS: {fps:.2f}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            with lock:
                latest_frame = frame

            cv2.imshow('Camera Feed', frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        stop_event.set()
        cap.release()
        cv2.destroyAllWindows()
        ws.close()


initial_sleep_time = 0.1
min_sleep_time = 0.1
max_sleep_time = 1
current_sleep_time = initial_sleep_time
sleep_adjustment_factor = 0.1

websocket_api()
