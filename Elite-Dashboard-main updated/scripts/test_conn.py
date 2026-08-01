import socket
import sys

def main():
    # Replace host if your Neon host differs
    host = "ep-delicate-truth-ayh2bgqy-pooler.c-5.us-east-2.aws.neon.tech"
    port = 5432
    print("Host:", host)
    try:
        info = socket.getaddrinfo(host, port)
        print("getaddrinfo ok; sample:", info[:2])
    except Exception as e:
        print("getaddrinfo error:", repr(e))
        sys.exit(1)

    try:
        s = socket.create_connection((host, port), timeout=5)
        print("TCP connect: ok")
        s.close()
    except Exception as e:
        print("TCP connect error:", repr(e))
        sys.exit(1)

    print("Network checks passed")

if __name__ == '__main__':
    main()
