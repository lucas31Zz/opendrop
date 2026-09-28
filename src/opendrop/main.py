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
from opendrop.i18n import t, normalize_lang
from opendrop.server.server import create_server, PortInUseError


def main():
    parser = argparse.ArgumentParser(description="OpenDrop")
    parser.add_argument("--headless", action="store_true",
                        help="Run without opening QR code or browser (for desktop GUI)")
    parser.add_argument("--port", type=int, default=None,
                        help="Force a specific port")
    parser.add_argument("--rotate-token", action="store_true",
                        help="Generate a new token and session code")
    args = parser.parse_args()

    config = load_config()
    lang = normalize_lang(config.get("language", "en"))
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
    # Global receive-folder quota in bytes (0 or missing = unlimited).
    # A negative value (config edited by hand) makes no sense: clamp it
    # to 0 (unlimited) rather than let the server interpret a quota that
    # can never be satisfied.
    try:
        global_quota_bytes = max(0, int(config.get("global_quota_bytes", 0) or 0))
    except (TypeError, ValueError):
        global_quota_bytes = 0

    # Token and session code:
    #  - manual reset (--rotate-token, desktop Reset button) -> change
    #  - "new token on start" checked in the config           -> change
    #  - otherwise reuse the previous state -> stable QR and code
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
                               global_quota_bytes=global_quota_bytes,
                               language=lang)
    except PortInUseError as e:
        print(f"\n  {t('Error:', lang)} {e}", flush=True)
        print(f"  {t('An older server is probably still running: stop it,', lang)}",
              flush=True)
        print(f"  {t('then start OpenDrop again.', lang)}", flush=True)
        sys.exit(1)
    session_code = server.sessions.code
    save_session_state(token, session_code)
    print(flush=True)
    print("  OpenDrop v0.1.6", flush=True)
    print(flush=True)
    print(f"  {t('Server:', lang):<18}{ip}:{port}", flush=True)
    print(f"  {t('Web interface:', lang):<18}{url_upload}", flush=True)
    print(f"  {t('Session code:', lang):<18}{session_code}", flush=True)
    print(f"  {t('Received in:', lang):<18}{download_dir}", flush=True)
    print(f"  {t('Shared from:', lang):<18}{share_dir}", flush=True)
    print(flush=True)
    print(f"  {t('Drop files into the Share folder to share them.', lang)}", flush=True)
    print(f"  {t('Scan the QR code with your device.', lang)}", flush=True)
    print(f"  {t('HTTPS: self-signed certificate; accept the browser warning on first access.', lang)}", flush=True)
    print(f"  {t('Press Ctrl+C to stop.', lang)}", flush=True)
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
            "lang": lang,
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
                    # Opening the PNG: os.startfile only exists on Windows.
                    # On Linux we go through xdg-open, on macOS through
                    # open; without a desktop (VM/headless) the command
                    # fails or does not exist, the server starts anyway.
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
        print(f"\n  {t('Server stopped.', lang)}", flush=True)
        server.sessions.stop_cleanup()
        server.server_close()
        sys.exit(0)


if __name__ == "__main__":
    main()
