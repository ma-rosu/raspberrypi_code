import subprocess
import time

TARGET_MAC = "2B:6F:26:39:46:DB"

def run_bluetoothctl_command(command_list):
    try:
        result = subprocess.run(['bluetoothctl'] + command_list, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command '{' '.join(command_list)}': {e}")
        print(f"Stderr: {e.stderr}")
        return ""
    except FileNotFoundError:
        print("Error: bluetoothctl not found. Is BlueZ installed?")
        return ""

def connect_bluetooth_device(mac_address):
    print(f"Attempting to connect to {mac_address}...")
    output = run_bluetoothctl_command(["connect", mac_address])
    if "Connection successful" in output or "already connected" in output:
        print(f"Successfully connected to {mac_address}.")
    else:
        print(f"Failed to connect to {mac_address}. Output:\n{output}")

if __name__ == "__main__":
    connect_bluetooth_device(TARGET_MAC)