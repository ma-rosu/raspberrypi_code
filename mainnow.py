import base64
import time
import cv2
import websocket
import threading
import json
import subprocess
import numpy as np
import queue  # Importă modulul queue

from agents.speak_agent import SpeakAgent

def speak_fall():
    SpeakAgent('fall')

def speak_move():
    SpeakAgent('move')

def speak_sleep():
    SpeakAgent('sleep')

# --- Configurări Globale ---
# WS_URL = "ws://3.73.38.71:5000/ws"
WS_URL = "ws://localhost:8000/ws"
IVS_RTMPS_URL = "rtmps://2376ef63e32c.global-contribute.live-video.net:443/app/sk_eu-central-1_t5DRKo1B2j1k_a51pvib2DpVcAiIz7VF3L9Z3qd3A2h"
FFMPEG_EXE_PATH = r'C:\ProgramData\chocolatey\lib\ffmpeg\tools\ffmpeg\bin\ffmpeg.exe'

# Eveniment pentru a semnala oprirea tuturor thread-urilor
stop_event = threading.Event()

# Cozi separate pentru a transfera cadrele de la thread-ul principal (camera)
# către thread-urile WebSocket și FFmpeg.
frame_queue_ws = queue.Queue(maxsize=5)  # Coadă pentru WebSocket (5 cadre tampon)
frame_queue_ffmpeg = queue.Queue(maxsize=5)  # Coadă pentru FFmpeg (5 cadre tampon)

# Coadă pentru a transfera rezultatele de la thread-ul WebSocket către thread-ul principal
results_queue = queue.Queue(maxsize=10)  # Coadă pentru rezultate (10 elemente tampon)


# --- Funcții pentru WebSocket Sender ---
def websocket_sender_thread(ws_url, frame_q_in, results_q_out, stop_event):
    """
    Thread dedicat trimiterii cadrelor către serverul WebSocket și preluării rezultatelor.
    Preia cadrele dintr-o coadă thread-safe și pune rezultatele în altă coadă.
    """

    def on_message(ws, message):
        """Callback atunci când se primește un mesaj de la serverul WebSocket."""
        try:
            result = json.loads(message)
            # NOU: Pune rezultatul în coada de rezultate pentru thread-ul principal
            try:
                results_q_out.put(result, timeout=0.01)  # Punem rezultatul în coadă
            except queue.Full:
                print("Results queue is full, dropping result.")
        except Exception as e:
            print("Error parsing message from WebSocket:", e)

    def on_error(ws, error):
        """Callback atunci când apare o eroare WebSocket."""
        print("WebSocket error:", error)

    def on_close(ws, close_status_code, close_msg):
        """Callback atunci când conexiunea WebSocket se închide."""
        print("WebSocket closed")
        if not stop_event.is_set():
            stop_event.set()

    def on_open(ws):
        """Callback atunci când conexiunea WebSocket se deschide."""
        print("WebSocket connection opened.")

        def run_sender():
            """Buclă internă pentru a trimite cadrele prin WebSocket."""
            while not stop_event.is_set():
                try:
                    frame_to_send = frame_q_in.get(timeout=0.1)
                except queue.Empty:
                    time.sleep(0.05)
                    continue

                if frame_to_send is not None:
                    try:
                        _, buffer = cv2.imencode('.jpg', frame_to_send, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
                        jpg_as_text = base64.b64encode(buffer).decode('utf-8')
                        ws.send(jpg_as_text)
                    except websocket.WebSocketConnectionClosedException:
                        print("WebSocket connection closed unexpectedly during send.")
                        break
                    except Exception as e:
                        print(f"Error sending frame via WebSocket: {e}")

                time.sleep(0.1)
            print("WebSocket sender run_sender thread stopping.")

        threading.Thread(target=run_sender, daemon=True).start()

    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()
    print("WebSocket sender thread finished run_forever.")
    stop_event.set()


# --- Funcții pentru FFmpeg Streamer ---
def read_ffmpeg_stderr(process, stop_event):
    """Citeste erorile (stderr) de la procesul FFmpeg."""
    for line in process.stderr:
        decoded_line = line.decode('utf-8').strip()
        if "frame=" not in decoded_line and "fps=" not in decoded_line:
            print(f"[FFmpeg stderr]: {decoded_line}")
        if stop_event.is_set():
            break
    print("FFmpeg stderr reader thread stopping.")


def ffmpeg_streamer_thread(ivs_rtmps_url, ffmpeg_exe_path, frame_q_in, stop_event, width, height, fps):
    """
    Thread dedicat streaming-ului video către un server RTMP/RTMPS folosind FFmpeg.
    Preia cadrele dintr-o coadă thread-safe.
    """
    ffmpeg_process = None
    command = [
        ffmpeg_exe_path,
        '-y',
        '-f', 'rawvideo',
        '-vcodec', 'rawvideo',
        '-pix_fmt', 'bgr24',
        '-s', f'{width}x{height}',
        '-r', str(fps),
        '-i', '-',
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-tune', 'zerolatency',
        '-r', str(fps),
        '-g', str(int(fps * 2)),
        '-b:v', '2500k',
        '-maxrate', '3000k',
        '-bufsize', '6000k',
        '-pix_fmt', 'yuv420p',
        '-f', 'flv',
        ivs_rtmps_url
    ]

    print(f"Starting FFmpeg with command: {' '.join(command)}")

    try:
        ffmpeg_process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                          stderr=subprocess.PIPE)
        time.sleep(1)

        stderr_output = ""
        try:
            stderr_output = ffmpeg_process.stderr.read(1024).decode('utf-8')
        except Exception as e:
            print(f"Error reading initial FFmpeg stderr: {e}")

        if stderr_output:
            print(f"[FFmpeg Initial stderr]:\n{stderr_output}")
            if "Error" in stderr_output or "failed" in stderr_output:
                print("FFmpeg reported an error during startup. Exiting FFmpeg streamer.")
                stop_event.set()
                return

        threading.Thread(target=read_ffmpeg_stderr, args=(ffmpeg_process, stop_event), daemon=True).start()

    except FileNotFoundError:
        print(
            f"Error: FFmpeg not found at {ffmpeg_exe_path}. Please ensure FFmpeg is installed and the path is correct.")
        stop_event.set()
        return
    except Exception as e:
        print(f"Error starting FFmpeg process: {e}")
        stop_event.set()
        return

    while not stop_event.is_set():
        frame_to_send = None
        try:
            frame_to_send = frame_q_in.get(timeout=0.1)
        except queue.Empty:
            time.sleep(0.01)
            continue

        if frame_to_send is not None:
            if ffmpeg_process and ffmpeg_process.stdin and ffmpeg_process.poll() is None:
                try:
                    ffmpeg_process.stdin.write(frame_to_send.tobytes())
                except BrokenPipeError:
                    print("FFmpeg pipe broken, likely exited. Stopping FFmpeg streamer.")
                    break
                except Exception as e:
                    print(f"Error writing to FFmpeg stdin: {e}. Stopping FFmpeg streamer.")
                    break
            else:
                if ffmpeg_process and ffmpeg_process.poll() is not None:
                    print("FFmpeg process has terminated. Stopping FFmpeg streamer.")
                else:
                    print("FFmpeg process is not running or stdin is unavailable. Skipping frame write.")
                break

        time.sleep(0.001)

    print("FFmpeg streamer thread stopping.")
    if ffmpeg_process:
        try:
            if ffmpeg_process.stdin:
                ffmpeg_process.stdin.close()

            stdout_data, stderr_data = ffmpeg_process.communicate(timeout=5)
            if stdout_data:
                print(f"[FFmpeg final stdout]:\n{stdout_data.decode('utf-8')}")
            if stderr_data:
                print(f"[FFmpeg final stderr]:\n{stderr_data.decode('utf-8')}")

            if ffmpeg_process.poll() is None:
                ffmpeg_process.terminate()
                print("FFmpeg process terminated forcibly.")
        except Exception as e:
            print(f"Error during FFmpeg process cleanup: {e}")


# --- Funcția Principală (Main) ---
def main():
    """
    Funcția principală care inițializează camera, pornește thread-urile
    și gestionează bucla de citire a cadrelor și afișare, preluând și rezultatele.
    """
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Cannot open camera. Exiting.")
        stop_event.set()
        return

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    if fps == 0:
        fps = 30
    print(f"Camera resolution: {width}x{height} at {fps} FPS")

    # Pornește thread-ul WebSocket (transmite coada de rezultate)
    ws_thread = threading.Thread(target=websocket_sender_thread,
                                 args=(WS_URL, frame_queue_ws, results_queue, stop_event),
                                 daemon=True)
    ws_thread.start()

    # Pornește thread-ul FFmpeg
    # ffmpeg_thread = threading.Thread(target=ffmpeg_streamer_thread,
    #                                  args=(
    #                                  IVS_RTMPS_URL, FFMPEG_EXE_PATH, frame_queue_ffmpeg, stop_event, width, height,
    #                                  fps),
    #                                  daemon=True)
    # ffmpeg_thread.start()

    prev_time = time.time()

    # Variabile pentru a stoca cel mai recent rezultat primit
    latest_fall_status = False
    latest_fire_status = False
    latest_move_status = False
    latest_sleep_status = False

    try:
        while not stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                print("Can't receive frame from camera. Exiting...")
                break

            current_time = time.time()
            display_fps = 1 / (current_time - prev_time)
            prev_time = current_time

            # NOU: Încearcă să preiei rezultatele din coada de rezultate
            while True:
                try:
                    result = results_queue.get_nowait()
                    latest_fall_status = result.get("fall", latest_fall_status)
                    latest_fire_status = result.get("fire", latest_fire_status)
                    latest_move_status = result.get("move", latest_move_status)
                    latest_sleep_status = result.get("sleep", latest_sleep_status)

                    if latest_fall_status > 0:
                        fall_thread = threading.Thread(target=speak_fall)
                        fall_thread.start()

                    if latest_move_status > 0:
                        move_thread = threading.Thread(target=speak_move)
                        move_thread.start()

                    if latest_sleep_status > 0:
                        sleep_thread = threading.Thread(target=speak_sleep)
                        sleep_thread.start()

                except queue.Empty:
                    break  # Nu mai sunt rezultate de preluat, ieși din bucla interioară
                except Exception as e:
                    print(f"Error processing local result: {e}")
                    break  # Ieși din bucla interioară la eroare

            # Afișează FPS-ul și statusul de fall/fire pe ecranul local
            cv2.putText(frame, f"FPS: {display_fps:.2f}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(frame, f"Fall: {latest_fall_status}", (10, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255) if latest_fall_status else (0, 255, 0), 2)
            cv2.putText(frame, f"Fire: {latest_fire_status}", (10, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255) if latest_fire_status else (0, 255, 0), 2)

            # Pune cadrul în coada pentru WebSocket (face o copie)
            try:
                frame_queue_ws.put(frame.copy(), timeout=0.01)
            except queue.Full:
                pass

                # Pune cadrul în coada pentru FFmpeg (face o altă copie)
            try:
                frame_queue_ffmpeg.put(frame.copy(), timeout=0.01)
            except queue.Full:
                pass

            cv2.imshow('Camera Feed', frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        print("Main loop exiting. Signaling threads to stop...")
        stop_event.set()

        ws_thread.join(timeout=10)
        # ffmpeg_thread.join(timeout=10)

        cap.release()
        cv2.destroyAllWindows()
        print("Resources released. Application finished.")


if __name__ == "__main__":
    main()