import base64
import time
import cv2
import websocket
import threading
import json
import subprocess
import queue

from agents.speak_agent import SpeakAgent

# --- Funcții de vorbire (rulate în thread-uri separate) ---
def speak_fall():
    SpeakAgent('fall')

def speak_move():
    SpeakAgent('move')

def speak_sleep():
    SpeakAgent('sleep')

# --- Configurări Globale ---
WS_URL = "ws://18.197.7.3:5001/ws"
IVS_RTMPS_URL = "rtmps://2376ef63e32c.global-contribute.live-video.net:443/app/sk_eu-central-1_t5DRKo1B2j1k_a51pvib2DpVcAiIz7VF3L9Z3qd3A2h"
FFMPEG_EXE_PATH = r'C:\ProgramData\chocolatey\lib\ffmpeg\tools\ffmpeg\bin\ffmpeg.exe'

# Eveniment pentru a semnala oprirea tuturor thread-urilor
stop_event = threading.Event()

# Cozi pentru comunicarea între thread-uri
frame_queue_ws = queue.Queue(maxsize=50) # Cadre pentru WebSocket
frame_queue_ffmpeg = queue.Queue(maxsize=50) # Cadre pentru FFmpeg
results_queue = queue.Queue(maxsize=100) # Rezultate de la server

# --- Variabile pentru controlul dinamic al sleep-ului (Globale) ---
# Acestea vor fi modificate de thread-ul websocket_sender_thread
initial_sleep_time = 0.1
min_sleep_time = 0.05 # Redus pentru a permite o accelerare mai mare
max_sleep_time = 0.6
current_sleep_time = initial_sleep_time
sleep_adjustment_factor = 0.05 # Ajustat pentru o adaptare mai fină

# Contoare globale pentru cadre trimise și rezultate primite de WS
sends_count = 0
results_count = 0

# --- Funcții pentru WebSocket Sender ---
def websocket_sender_thread(ws_url, frame_q_in, results_q_out, stop_event):
    """
    Thread dedicat trimiterii cadrelor către serverul WebSocket și preluării rezultatelor.
    Preia cadrele dintr-o coadă thread-safe și pune rezultatele în altă coadă.
    De asemenea, gestionează logica de dynamic sleep.
    """
    global sends_count, results_count, current_sleep_time, initial_sleep_time, min_sleep_time, max_sleep_time, sleep_adjustment_factor

    def on_message(ws, message):
        """Callback atunci când se primește un mesaj de la serverul WebSocket."""
        global results_count # Modificăm variabila globală results_count
        try:
            result = json.loads(message)
            results_count += 1 # Incrementăm contorul de rezultate
            try:
                results_q_out.put(result, timeout=0.01)
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
            global sends_count, results_count, current_sleep_time # Re-declarăm global aici pentru acces în bucla internă

            while not stop_event.is_set():
                frame_to_send = None
                try:
                    # Încercăm să luăm un cadru din coadă. Timeout mic pentru a nu bloca.
                    frame_to_send = frame_q_in.get(timeout=0.01)
                except queue.Empty:
                    # Dacă nu e nimic în coadă, nu trimitem, dar continuăm logica de sleep
                    pass

                if frame_to_send is not None:
                    try:
                        _, buffer = cv2.imencode('.jpg', frame_to_send, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
                        jpg_as_text = base64.b64encode(buffer).decode('utf-8')
                        ws.send(jpg_as_text)
                        sends_count += 1 # Incrementăm contorul de trimiteri
                    except websocket.WebSocketConnectionClosedException:
                        print("WebSocket connection closed unexpectedly during send.")
                        break
                    except Exception as e:
                        print(f"Error sending frame via WebSocket: {e}")
                        # Poate reîncerca, sau opri thread-ul dacă eroarea e persistentă
                        time.sleep(1) # Pauză scurtă după eroare
                        continue # Trece la următoarea iterație

                if sends_count > (results_count + 1):
                    current_sleep_time = min(current_sleep_time + sleep_adjustment_factor * 2, max_sleep_time)
                elif sends_count > (results_count + 1):
                    current_sleep_time = min(current_sleep_time + sleep_adjustment_factor, max_sleep_time)
                else:
                    current_sleep_time = max(current_sleep_time - sleep_adjustment_factor, min_sleep_time)

                # Afișează starea din acest thread
                print(f'sent: {sends_count} | results: {results_count} | sleep: {current_sleep_time:.2f}')

                # Așteaptă înainte de a trimite următorul cadru
                time.sleep(current_sleep_time)

            print("WebSocket sender run_sender thread stopping.")

        threading.Thread(target=run_sender, daemon=True).start()

    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever() # Aceasta este o operație blocantă care menține thread-ul activ
    print("WebSocket sender thread finished run_forever.")
    stop_event.set() # Asigură-te că evenimentul de stop este setat și aici


# --- Funcții pentru FFmpeg Streamer (fără modificări majore, doar context) ---
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
            frame_to_send = frame_q_in.get(timeout=0.01) # Redus timeout
        except queue.Empty:
            time.sleep(0.001) # Redus sleep
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

        time.sleep(0.001) # Ajustat sleep

    print("FFmpeg streamer thread stopping.")
    if ffmpeg_process:
        try:
            if ffmpeg_process.stdin:
                ffmpeg_process.stdin.close()

            # Încercați să comunicați și să așteptați terminarea procesului
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
        fps = 30 # Valoare implicită dacă nu poate fi determinată
    print(f"Camera resolution: {width}x{height} at {fps} FPS")

    # Pornește thread-ul WebSocket (transmite coada de rezultate)
    ws_thread = threading.Thread(target=websocket_sender_thread,
                                 args=(WS_URL, frame_queue_ws, results_queue, stop_event),
                                 daemon=True)
    ws_thread.start()

    # Pornește thread-ul FFmpeg
    ffmpeg_thread = threading.Thread(target=ffmpeg_streamer_thread,
                                     args=(
                                     IVS_RTMPS_URL, FFMPEG_EXE_PATH, frame_queue_ffmpeg, stop_event, width, height,
                                     fps),
                                     daemon=True)
    ffmpeg_thread.start()


    prev_time = time.time()

    # Variabile pentru a stoca cel mai recent rezultat primit
    latest_fall_status = 0 # 0 sau 1
    latest_fire_status = 0 # 0 sau 1
    latest_move_status = 0 # 0 sau 1
    latest_sleep_status = 0 # 0 sau 1

    try:
        while not stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                print("Can't receive frame from camera. Exiting...")
                break

            current_time_display = time.time() # Timp pentru calculul FPS-ului de afișare
            display_fps = 1 / (current_time_display - prev_time)
            prev_time = current_time_display

            # Preia toate rezultatele disponibile din coadă
            while True:
                try:
                    result = results_queue.get_nowait()
                    # Actualizează statusurile doar dacă valoarea este 1 (True)
                    # Astfel, statusurile rămân TRUE până când un nou eveniment ar fi detectat
                    # sau până la o logică de resetare pe server.
                    latest_fall_status = result.get("fall", 0) or latest_fall_status
                    latest_fire_status = result.get("fire", 0) or latest_fire_status
                    latest_move_status = result.get("move", 0) or latest_move_status
                    latest_sleep_status = result.get("sleep", 0) or latest_sleep_status

                    if result.get("fall", 0) > 0:
                        threading.Thread(target=speak_fall, daemon=True).start()

                    if result.get("move", 0) > 0:
                        threading.Thread(target=speak_move, daemon=True).start()

                    if result.get("sleep", 0) > 0:
                        threading.Thread(target=speak_sleep, daemon=True).start()

                except queue.Empty:
                    break  # Nu mai sunt rezultate de preluat
                except Exception as e:
                    print(f"Error processing local result: {e}")
                    break

            # Afișează FPS-ul și statusul pe ecranul local
            cv2.putText(frame, f"FPS: {display_fps:.2f}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(frame, f"Fall: {latest_fall_status}", (10, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255) if latest_fall_status else (0, 255, 0), 2)
            cv2.putText(frame, f"Fire: {latest_fire_status}", (10, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255) if latest_fire_status else (0, 255, 0), 2)
            cv2.putText(frame, f"Move: {latest_move_status}", (10, 150),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255) if latest_move_status else (0, 255, 0), 2)
            cv2.putText(frame, f"Sleep: {latest_sleep_status}", (10, 190),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255) if latest_sleep_status else (0, 255, 0), 2)


            # Pune cadrele în cozi pentru alte thread-uri
            # Folosim try-except queue.Full pentru a nu bloca aplicația dacă cozile sunt pline
            try:
                frame_queue_ws.put(frame.copy(), timeout=0.01)
            except queue.Full:
                # print("WS Queue full, skipping frame.") # Poate fi prea mult zgomot
                pass

            try:
                frame_queue_ffmpeg.put(frame.copy(), timeout=0.01)
            except queue.Full:
                # print("FFmpeg Queue full, skipping frame.") # Poate fi prea mult zgomot
                pass

            cv2.imshow('Camera Feed', frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        print("Main loop exiting. Signaling threads to stop...")
        stop_event.set()

        # Așteaptă thread-urile să se termine (cu timeout)
        ws_thread.join(timeout=5)
        ffmpeg_thread.join(timeout=5)

        cap.release()
        cv2.destroyAllWindows()
        print("Resources released. Application finished.")


if __name__ == "__main__":
    main()