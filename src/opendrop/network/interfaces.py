import os
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
    # Local test, no connection: no delay, and no false negative when the
    # system swallows local loopback packets.
    #
    # Windows: bind WITHOUT SO_REUSEADDR. There the option lets a socket
    # bind while another server is already listening (that is what allowed
    # the double bind), whereas a plain bind fails as soon as someone else
    # holds the port. A plain bind also succeeds over leftovers in
    # TIME_WAIT, so nothing has to be skipped on that platform.
    #
    # POSIX: bind WITH SO_REUSEADDR. The server closes every response, so
    # its own connections stay in TIME_WAIT on this port for ~60 s after a
    # restart; a plain bind then fails, find_available_port walks to
    # port+1, and the server silently changes port on every reset (the
    # desktop shows 8081, 8082, ... while config.json still says 8080).
    # The option only lets the bind ignore those leftovers: a socket that
    # is actually listening still refuses it, which is the case this
    # function has to detect. The real server binds with the same option
    # (allow_reuse_address), so probe and server finally agree.
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if os.name != "nt":
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("", port))
        finally:
            s.close()
        return True
    except OSError:
        return False
