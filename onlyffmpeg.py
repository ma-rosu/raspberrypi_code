import cv2
import subprocess
import time

# Configuration
IVS_RTMPS_URL = "rtmps://2376ef63e32c.global-contribute.live-video.net:443/app/sk_eu-central-1_t5DRKo1B2j1k_a51pvib2DpVcAiIz7VF3L9Z3qd3A2h"
FFMPEG_EXE_PATH = r'C:\ProgramData\chocolatey\lib\ffmpeg\tools\ffmpeg\bin\ffmpeg.exe'

def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Cannot open camera")
        return

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30

    print(f"Camera opened: {width}x{height} @ {fps} FPS")

    ffmpeg_cmd = [
        FFMPEG_EXE_PATH,
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
        IVS_RTMPS_URL
    ]

    print(f"Running FFmpeg: {' '.join(ffmpeg_cmd)}")

    process = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Failed to read frame")
                break
            process.stdin.write(frame.tobytes())
    except KeyboardInterrupt:
        print("Stream interrupted by user")
    finally:
        cap.release()
        if process.stdin:
            process.stdin.close()
        process.terminate()
        print("Streaming stopped")

if __name__ == "__main__":
    main()
