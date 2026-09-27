import socket


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def find_available_port(preferred: int = 8080, max_attempts: int = 20) -> int:
    for port in range(preferred, preferred + max_attempts):
        if _port_is_free(port):
            return port
    raise RuntimeError(f"No free port between {preferred} and {preferred + max_attempts - 1}")


def _port_is_free(port: int) -> bool:
    # Bind WITHOUT SO_REUSEADDR. On Windows, a bind with SO_REUSEADDR
    # succeeds even if a server is already listening (that is what allowed
    # the double bind), whereas a plain bind fails as soon as someone else
    # holds the port. Local test, no connection: no delay, and no false
    # negative when the system swallows local loopback packets.
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("", port))
        finally:
            s.close()
        return True
    except OSError:
        return False
