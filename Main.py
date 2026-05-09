import sys
import os
import socket
import psutil
import time
from Server import Server
from Utils import data_path
from CertGen import generate_self_signed_cert

if not os.path.exists(data_path("cert.pem")):
    print("[*] Generating self-signed certificates...")
    generate_self_signed_cert()

def kill_previous_script_instances():
    """Identifies and terminates other Python processes running this specific script."""
    current_pid = os.getpid()
    script_name = os.path.basename(__file__)
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Check if the process is a python interpreter running our Main.py
            if proc.info['name'].lower().startswith("python") and proc.info['cmdline']:
                if any(script_name in arg for arg in proc.info['cmdline']) and proc.info['pid'] != current_pid:
                    print(f"[*] Found previous instance (PID: {proc.info['pid']}). Signaling shutdown...")
                    proc.terminate() 
                    try:
                        proc.wait(timeout=3)
                    except psutil.TimeoutExpired:
                        print("[!] Instance did not exit gracefully. Forcing kill...")
                        proc.kill() 
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

def is_port_in_use(port):
    """Verifies if a port is taken before the server tries to bind to it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(('127.0.0.1', port)) == 0

def main():
    # 1. Handle command line stop
    if "--stop" in sys.argv:
        kill_previous_script_instances()
        print("[*] BigIRCd script instances stopped.")
        sys.exit(0)

    # 2. Parse Port Argument
    # Default ports if no argument is provided
    requested_ports = [6667, 6697]
    
    if "--port" in sys.argv:
        try:
            port_index = sys.argv.index("--port") + 1
            custom_port = int(sys.argv[port_index])
            
            # Validation: Check against standard IRC ranges
            # Range 6660-6669 (Standard), 6697 (SSL), 7000 (Legacy SSL)
            is_valid = (6660 <= custom_port <= 6669) or (custom_port == 6697) or (custom_port == 7000)
            
            if not is_valid:
                print(f"[!] Error: {custom_port} is not a standard IRC port.")
                print("[*] Please use 6667, 6697, 7000, or the range 6660-6669.")
                sys.exit(1)
                
            requested_ports = [custom_port]
        except (IndexError, ValueError):
            print("[!] Invalid port provided. Usage: python Main.py --port <number>")
            sys.exit(1)

    # 3. Kill existing instances before starting (Protects the DB)
    kill_previous_script_instances()

    # 4. Port Check
    available_ports = []
    for p in requested_ports:
        if not is_port_in_use(p):
            available_ports.append(p)
        else:
            print(f"[!] Port {p} is currently occupied.")

    if not available_ports:
        print("[FATAL] No ports available. Exiting.")
        sys.exit(1)

    # 5. Start Server
    print(f"[*] Launching BigIRCd on: {', '.join(map(str, available_ports))}")
    try:
        irc_server = Server("BigIRCd")
        irc_server.run(available_ports)
    except KeyboardInterrupt:
        # This catches the CTRL+C and prevents the Traceback from showing
        print("\n[*] BigIRCd stopped by user.")
        sys.exit(0)
    except Exception as e:
        print(f"[FATAL] Runtime error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()