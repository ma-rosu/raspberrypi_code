import subprocess
import time
import sys
import os

def run_livestream_with_retry():
    
    if not os.path.exists("/usr/bin/libcamera-vid"):
        print("Error: 'libcamera-vid' not found at /usr/bin/libcamera-vid.")
        print("Please ensure 'libcamera-apps' package is installed (sudo apt install libcamera-apps).")
        sys.exit(1)
    if not os.path.exists("/usr/bin/ffmpeg"):
        print("Error: 'ffmpeg' not found at /usr/bin/ffmpeg.")
        print("Please ensure 'ffmpeg' is installed (sudo apt install ffmpeg).")
        sys.exit(1)
    

    
    
    
    
    streaming_command = (
        "libcamera-vid -t 0 --width 1280 --height 720 --codec yuv420 --framerate 25 --output - | "
        "ffmpeg -f rawvideo -pix_fmt yuv420p -s:v 1280x720 -r 25 -i - "
        "-vcodec libx264 -preset veryfast -tune zerolatency " 
        "-acodec aac -b:a 128k -ar 44100 -ac 2 -maxrate 1500k -bufsize 3000k -g 50 -r 25 -pix_fmt yuv420p -f flv "
        "\"rtmps://2376ef63e32c.global-contribute.live-video.net:443/app/sk_eu-central-1_t5DRKo1B2j1k_a51pvib2DpVcAiIz7VF3L9Z3qd3A2h\""
    )

    print("Live streaming script started. Press Ctrl+C to stop.")

    while True: 
        print("\nAttempting to start the stream...")
        try:
            
            
            
            
            process = subprocess.run(
                streaming_command,
                shell=True,
                check=True,
                text=True,
                stderr=subprocess.PIPE,
                timeout=None 
            )
            
            
            print("Stream exited normally.")
            break 

        except subprocess.CalledProcessError as e:
            
            print(f"Error running the stream (exit code: {e.returncode}):")
            print(f"Stderr: {e.stderr.strip()}")
            print(f"Retrying in 5 seconds...")
        except FileNotFoundError as e:
            
            print(f"Error: Program '{e.filename}' not found.")
            print("Please ensure 'libcamera-vid' and 'ffmpeg' are installed and in your PATH.")
            print(f"Retrying in 5 seconds...")
        except KeyboardInterrupt:
            
            print("\nCtrl+C detected. Stopping script.")
            break 
        except Exception as e:
            
            print(f"An unexpected error occurred: {e}")
            print(f"Retrying in 5 seconds...")

        time.sleep(5) 

    print("Script has been stopped.")

if __name__ == "__main__":
    run_livestream_with_retry()