import subprocess
import threading
import os 
from agents import bluetooth_agent

def connect_bluetooth():
    bluetooth_agent.connect_bluetooth_device()

def run_script(script_name):
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script_name)
    subprocess.run(['python', script_path])


def main():
    thread1 = threading.Thread(target=run_script, args=('stream_app.py',))
    thread2 = threading.Thread(target=run_script, args=('send_frames.py',))
    
    thread1.start()
    thread2.start()
    
    thread1.join()
    thread2.join()


if __name__ == "__main__":
    main()
