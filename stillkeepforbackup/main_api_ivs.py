import base64
import time
import cv2
import websocket
import threading
import json
import subprocess
import numpy as np

def websocket_api():
    WS_URL = "ws://3.73.38.71:5000/ws"
    IVS_RTMPS_URL = "rtmps://2376ef63e32c.global-contribute.live-video.net:443/app/sk_eu-central-1_t5DRKo1B2j1k_a51pvib2DpVcAiIz7VF3L9Z3qd3A2h"

    latest_frame = None
    lock = threading.Lock()
    stop_event = threading.Event()

    def on_message(ws, message):
        try:
            result = json.loads(message)
            print("fall:", result["fall"], "| fire:", result["fire"])
            pass
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
                time.sleep(0.2)

        threading.Thread(target=run).start()

    ffmpeg_process = None # Declară-l aici pentru claritate, deși e global

    FFMPEG_EXE_PATH = r'C:\ProgramData\chocolatey\lib\ffmpeg\tools\ffmpeg\bin\ffmpeg.exe'

    def start_ffmpeg_process(width, height, fps):
        nonlocal ffmpeg_process
        command = [
            FFMPEG_EXE_PATH,  # Use the absolute path here
            '-y',
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-pix_fmt', 'bgr24',
            '-s', f'{width}x{height}',
            '-r', str(fps),
            '-i', '-',
            '-c:v', 'libx264',
            '-preset', 'ultrafast',#'veryfast',
            '-tune', 'zerolatency',
            '-r', str(fps),
            '-g', str(int(fps * 2)),
            '-b:v', '2500k',
            '-maxrate', '3000k',
            '-bufsize', '6000k',
            '-pix_fmt', 'yuv420p',
            '-f', 'flv',
            IVS_RTMPS_URL
        ]
        print(f"Starting FFmpeg with command: {' '.join(command)}")
        try:
            ffmpeg_process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                              stderr=subprocess.PIPE)
            time.sleep(1)  # Give FFmpeg a moment to start and print errors

            # Try to read some initial stderr output immediately
            stderr_output = ""
            try:
                # Non-blocking read (read available data without waiting)
                stderr_output = ffmpeg_process.stderr.read(1024).decode('utf-8')
            except Exception as e:
                print(f"Error reading initial stderr: {e}")

            if stderr_output:
                print(f"[FFmpeg Initial stderr]:\n{stderr_output}")
                if "Error" in stderr_output or "failed" in stderr_output:
                    print("FFmpeg reported an error during startup. Exiting.")
                    ffmpeg_process = None
                    return

            # If no immediate errors, start the stderr reader thread
            threading.Thread(target=read_ffmpeg_stderr, args=(ffmpeg_process,)).start()

        except FileNotFoundError:
            print(
                "Error: FFmpeg not found at the specified path. Please ensure FFmpeg is installed and the path is correct.")
            ffmpeg_process = None
            return
        except Exception as e:
            print(f"Error starting FFmpeg process: {e}")
            ffmpeg_process = None
            return

    def read_ffmpeg_stderr(process):
        for line in process.stderr:
            print(f"[FFmpeg stderr]: {line.decode('utf-8').strip()}")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Cannot open camera")
        exit()

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    if fps == 0:
        fps = 30
    print(f"Camera resolution: {width}x{height} at {fps} FPS")

    start_ffmpeg_process(width, height, fps)

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

            current_time = time.time()
            display_fps = 1 / (current_time - prev_time)
            prev_time = current_time

            cv2.putText(frame, f"FPS: {display_fps:.2f}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            with lock:
                latest_frame = frame.copy()

            if ffmpeg_process and ffmpeg_process.stdin: # Acum, acest if este crucial
                try:
                    ffmpeg_process.stdin.write(frame.tobytes())
                    ffmpeg_process.stdin.flush() # Adaugă acest flush()
                except BrokenPipeError:
                    print("FFmpeg pipe broken, likely exited.")
                    break
                except Exception as e:
                    print(f"Error writing to FFmpeg stdin: {e}")
                    break
            else:
                # Acest else se va declanșa dacă ffmpeg_process este None (adică nu a pornit)
                print("FFmpeg process not running, skipping frame write.")
                # Puteti adauga un break aici daca doriti sa opriti programul
                # break

            cv2.imshow('Camera Feed', frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        stop_event.set()
        cap.release()
        cv2.destroyAllWindows()
        if ffmpeg_process:
            ffmpeg_process.stdin.close()
            # Incearca sa citesti orice output ramas de la FFmpeg inainte de a-l termina
            # Acest lucru poate fi util pentru a prinde erori care apar la inchidere
            stdout_data, stderr_data = ffmpeg_process.communicate(timeout=5)
            if stdout_data:
                print(f"[FFmpeg final stdout]:\n{stdout_data.decode('utf-8')}")
            if stderr_data:
                print(f"[FFmpeg final stderr]:\n{stderr_data.decode('utf-8')}")

            # Dupa communicate, procesul ar trebui sa fie deja terminat
            if ffmpeg_process.poll() is None:
                ffmpeg_process.terminate()
            print("FFmpeg process terminated.")
        ws.close()
        ws_thread.join(timeout=5)

websocket_api()