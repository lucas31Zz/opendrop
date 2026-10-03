import sys
import os
import webbrowser
import threading
import subprocess
import argparse

from opendrop.network.interfaces import get_local_ip, find_available_port
from opendrop.security.tokens import generate_token
from opendrop.security.session_state import load_session_state, save_session_state
from opendrop.config.config import load_config
from opendrop.server.server import create_server, PortInUseError


def main():
    parser = argparse.ArgumentParser(description="OpenDrop")
    parser.add_argument("--headless", action="store_true",
                        help="Run without opening QR code or browser (for desktop GUI)")
    parser.add_argument("--port", type=int, default=None,
                        help="Force a specific port")
    parser.add_argument("--rotate-token", action="store_true",
                        help="Generer un nouveau token et un nouveau code de session")
    args = parser.parse_args()

    config = load_config()
    ip = get_local_ip()
    if args.port:
        port = args.port
    else:
        port = find_available_port(config.get("preferred_port", 8080))
    download_dir = config.get("download_directory")
    share_dir = config.get("share_directory")

    os.makedirs(download_dir, exist_ok=True)
    os.makedirs(share_dir, exist_ok=True)
    session_expires_in = config.get("session_expires_in", 3600)
    # Quota global du dossier de reception, en octets (0 ou absent = illimite).
    # Une valeur negative (config editee a la main) n'a pas de sens : on la
    # ramene a 0 (illimite) plutot que de laisser le serveur interpreter un
    # quota impossible a satisfaire.
    try:
        global_quota_bytes = max(0, int(config.get("global_quota_bytes", 0) or 0))
    except (TypeError, ValueError):
        global_quota_bytes = 0

    # Token et code de session :
    #  - reset manuel (--rotate-token, bouton Reset du desktop)  -> on change
    #  - "nouveau token au demarrage" coche dans la config       -> on change
    #  - sinon on reprend l'etat precedent -> QR et code stables
    must_rotate = args.rotate_token or bool(config.get("generate_new_token", False))
    previous = None if must_rotate else load_session_state()
    if previous:
        token = previous["token"]
        previous_code = previous.get("code")
    else:
        token = generate_token()
        previous_code = None

    url_upload = f"https://{ip}:{port}/?token={token}"
    url_download = f"https://{ip}:{port}/?token={token}"

    try:
        server = create_server(ip, port, token, download_dir, share_dir,
                               session_expires_in,
                               trust_proxy=bool(config.get("trust_proxy", False)),
                               session_code=previous_code,
                               global_quota_bytes=global_quota_bytes)
    except PortInUseError as e:
        print(f"\n  Erreur : {e}", flush=True)
        print("  Un ancien serveur tourne probablement encore : arretez-le,",
              flush=True)
        print("  puis relancez OpenDrop.", flush=True)
        sys.exit(1)
    session_code = server.sessions.code
    save_session_state(token, session_code)
    print(flush=True)
    print("  OpenDrop v0.2.0", flush=True)
    print(flush=True)
    print(f"  Serveur:         {ip}:{port}", flush=True)
    print(f"  Interface web:   {url_upload}", flush=True)
    print(f"  Code session:    {session_code}", flush=True)
    print(f"  Recus dans:      {download_dir}", flush=True)
    print(f"  Partage depuis:  {share_dir}", flush=True)
    print(flush=True)
    print("  Mets des fichiers dans le dossier Partage pour les partager.", flush=True)
    print("  Scanner le QR code avec votre appareil.", flush=True)
    print("  HTTPS : certificat auto-signe, acceptez l'avertissement au 1er acces.", flush=True)
    print("  Ctrl+C pour arreter.", flush=True)
    print(flush=True)

    if args.headless:
        import json as _json
        info = {
            "__opendrop_info__": True,
            "ip": ip,
            "port": port,
            "token": token,
            "session_code": session_code,
            "url_upload": url_upload,
            "url_download": url_download,
            "download_dir": download_dir,
            "share_dir": share_dir,
        }
        print(_json.dumps(info), flush=True)
    else:
        try:
            from opendrop.qr.generator import HAS_QR
            if HAS_QR:
                from opendrop.qr.generator import generate_qr_png
                img = generate_qr_png(url_upload)
                if img:
                    import tempfile
                    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                    tmp.write(img)
                    tmp.close()
                    print(f"  QR code: {tmp.name}", flush=True)
                    print(flush=True)
                    # Ouverture du PNG : os.startfile existe uniquement sous
                    # Windows. Sur Linux on passe par xdg-open, sur macOS par
                    # open ; sans bureau (VM/headless) la commande echoue ou
                    # n'existe pas, le serveur demarre quand meme.
                    try:
                        if os.name == "nt":
                            os.startfile(tmp.name)
                        else:
                            cmd = "open" if os.name == "darwin" else "xdg-open"
                            subprocess.Popen(
                                [cmd, tmp.name],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                            )
                    except Exception:
                        pass
        except Exception:
            pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Serveur arrete.", flush=True)
        server.sessions.stop_cleanup()
        server.server_close()
        sys.exit(0)


if __name__ == "__main__":
    main()
