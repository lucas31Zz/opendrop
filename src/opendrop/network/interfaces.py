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
    raise RuntimeError(f"Aucun port disponible entre {preferred} et {preferred + max_attempts - 1}")


def _port_is_free(port: int) -> bool:
    # Bind SANS SO_REUSEADDR. Sur Windows, un bind avec SO_REUSEADDR
    # reussit meme si un serveur ecoute deja (c'est ce qui permettait le
    # double bind), alors qu'un bind simple echoue des que quelqu'un tient
    # le port. Test local, aucune connexion : ni delai, ni faux negatif
    # quand le systeme avale les paquets de bouclage local.
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("", port))
        finally:
            s.close()
        return True
    except OSError:
        return False
