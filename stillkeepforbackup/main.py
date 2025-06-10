import base64
import time
import cv2
import websocket
import threading
import json

def websocket_api():
    WS_URL = "ws://3.73.38.71:5000/ws"

    latest_frame = None
    lock = threading.Lock()
    stop_event = threading.Event()

    def on_message(ws, message):
        try:
            result = json.loads(message)
            print("fall:", result["fall"], "| fire:", result["fire"])
        except Exception as e:
            print("Error parsing message:", e)

    def on_error(ws, error):
        print("WebSocket error:", error)

    def on_close(ws, close_status_code, close_msg):
        print("WebSocket closed")

    def on_open(ws):
        def run():
            while not stop_event.is_set():
                with lock:
                    frame_copy = latest_frame.copy() if latest_frame is not None else None

                if frame_copy is not None:
                    _, buffer = cv2.imencode('.jpg', frame_copy, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
                    jpg_as_text = base64.b64encode(buffer).decode('utf-8')
                    ws.send(jpg_as_text)

                time.sleep(0.1)

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

    # FPS calculation
    prev_time = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Can't receive frame. Exiting...")
                break

            # Calculate FPS
            current_time = time.time()
            fps = 1 / (current_time - prev_time)
            prev_time = current_time

            # Draw FPS on the frame
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

websocket_api()
