import sys
from Server import Server

def main():
    print("--- BigIRCd Windows Edition (Refactored) ---")
    server = Server(name="big.irc.local")
    try:
        server.run(ports=[6667])
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == "__main__":
    main()