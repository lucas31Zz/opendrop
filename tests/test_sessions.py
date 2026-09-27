"""Tests for session lifecycle: create, validate, expire, cleanup."""
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import urllib.error
import urllib.parse

from opendrop.network.interfaces import find_available_port
from tests.conftest import _start_server, _url, TestResult, dd, urlopen
from opendrop.server.session import SESSION_CODE_ALPHABET, SessionManager
from opendrop.server.rate_limit import limiter_session
from opendrop.security.session_state import load_session_state, save_session_state

r = TestResult()

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")


def _spawn_main(args, config_dir, timeout=30):
    """Lance `python -m opendrop.main` isole dans un LOCALAPPDATA temporaire.

    Retourne (processus, info JSON, file des lignes de sortie).
    """
    env = dict(os.environ)
    env["LOCALAPPDATA"] = config_dir
    # load_config() construit ses valeurs par defaut en appelant Path.home() :
    # sans ce repli, le sous-processus creerait ~/Downloads/OpenDrop dans le
    # profil reel. Tout doit rester dans le dossier temporaire du test.
    env["USERPROFILE"] = config_dir
    env["PYTHONUNBUFFERED"] = "1"
    chemins = [p for p in sys.path if p]
    if _SRC not in chemins:
        chemins.insert(0, _SRC)
    env["PYTHONPATH"] = os.pathsep.join(chemins)

    proc = subprocess.Popen(
        [sys.executable, "-u", "-m", "opendrop.main", *args],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
        cwd=os.path.dirname(_SRC))
    lignes = queue.Queue()

    def _lire():
        for line in proc.stdout:
            lignes.put(line)

    threading.Thread(target=_lire, daemon=True).start()

    info = None
    fin = time.time() + timeout
    while time.time() < fin and info is None:
        try:
            brut = lignes.get(timeout=1)
        except queue.Empty:
            if proc.poll() is not None:
                break
            continue
        texte = brut.decode("utf-8", "replace").strip()
        if texte.startswith("{") and "__opendrop_info__" in texte:
            info = json.loads(texte)
    return proc, info


def _stop(proc):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)


def test_sessions():
    print("--- Session lifecycle tests ---\n")

    # Token works initially
    server, port, token = _start_server(session_expires_in=3600)
    try:
        resp = urlopen(_url(port, "/api/files", token))
        r.check("Token works initially", resp.status == 200)
    except Exception as e:
        r.check("Token works initially", False, str(e))

    # Invalid token rejected
    try:
        urlopen(_url(port, "/api/files", "badtoken"))
        r.check("Invalid token rejected", False, "should be 403")
    except urllib.error.HTTPError as e:
        r.check("Invalid token rejected", e.code == 403)

    # Session info (le bloc session ne sort que pour un porteur de token)
    try:
        resp = urlopen(_url(port, "/api/info", token))
        data = json.loads(resp.read())
        r.check("Session info present", "session" in data and data["session"]["active_sessions"] >= 1)
    except Exception as e:
        r.check("Session info present", False, str(e))

    server.shutdown()

    # Expiration
    server2, port2, token2 = _start_server(session_expires_in=2)
    try:
        urlopen(_url(port2, "/api/files", token2))
        r.check("Token active before expiry", True)
    except Exception as e:
        r.check("Token active before expiry", False, str(e))

    print("\n  Waiting 3s for session expiration...")
    time.sleep(3)

    try:
        urlopen(_url(port2, "/api/files", token2))
        r.check("Expired token rejected", False, "should be 403")
    except urllib.error.HTTPError as e:
        body = json.loads(e.read())
        r.check("Expired token rejected", e.code == 403 and "expire" in body.get("error", "").lower(), f"{e.code} {body}")

    # Expired token blocks upload
    boundary = "----BSess"
    body = (b"--" + boundary.encode() + b"\r\n"
            b'Content-Disposition: form-data; name="file"; filename="sess.txt"\r\n'
            b"Content-Type: text/plain\r\n\r\nsession test\r\n--" + boundary.encode() + b"--\r\n")
    try:
        req = urllib.request.Request(
            _url(port2, "/api/upload", token2),
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Content-Length": str(len(body))},
            method="POST",
        )
        urlopen(req)
        r.check("Expired token blocks upload", False, "should be 403")
    except urllib.error.HTTPError as e:
        r.check("Expired token blocks upload", e.code == 403)

    server2.shutdown()

    # Cleanup thread
    server3, port3, token3 = _start_server(session_expires_in=2)
    server3.sessions._cleanup_interval = 2

    try:
        urlopen(_url(port3, "/api/files", token3))
        r.check("Token active for cleanup test", True)
    except Exception as e:
        r.check("Token active for cleanup test", False, str(e))

    resp = urlopen(_url(port3, "/api/info", token3))
    info = json.loads(resp.read())
    r.check("1 active session", info.get("session", {}).get("active_sessions", 0) >= 1, info)

    print("\n  Waiting 10s for expiry + cleanup...")
    time.sleep(10)

    try:
        urlopen(_url(port3, "/api/files", token3))
        r.check("Token expired for cleanup", False, "should be 403")
    except urllib.error.HTTPError as e:
        r.check("Token expired for cleanup", e.code == 403)

    try:
        urlopen(_url(port3, "/api/info", token3))
        r.check("Session cleaned up", False, "expired token should be rejected")
    except urllib.error.HTTPError as e:
        r.check("Session cleaned up",
                e.code == 403 and len(server3.sessions._sessions) == 0,
                f"{e.code} sessions={dict(server3.sessions._sessions)}")

    server3.shutdown()

    # --- Code de session (deverrouillage sans QR) ---
    print("\n  Session code tests...")
    server4, port4, token4 = _start_server()
    code = server4.sessions.code

    r.check("Session code format",
            len(code) == 6 and all(c in SESSION_CODE_ALPHABET for c in code),
            repr(code))

    def _unlock(port, value):
        url = f"https://127.0.0.1:{port}/api/session/unlock?code={urllib.parse.quote(value)}"
        return urlopen(urllib.request.Request(url, method="POST"))

    try:
        _unlock(port4, "")
        r.check("Missing code rejected", False, "should be 403")
    except urllib.error.HTTPError as e:
        body = json.loads(e.read())
        r.check("Missing code rejected", e.code == 403, f"{e.code} {body}")

    try:
        _unlock(port4, "XXXXXX")
        r.check("Wrong code rejected", False, "should be 403")
    except urllib.error.HTTPError as e:
        body = json.loads(e.read())
        r.check("Wrong code rejected",
                e.code == 403 and body.get("error") == "Code de session invalide",
                f"{e.code} {body}")

    try:
        resp = _unlock(port4, code)
        data = json.loads(resp.read())
        new_token = data.get("token")
        r.check("Good code unlocks", data.get("success") and bool(new_token), data)
    except Exception as e:
        new_token = None
        r.check("Good code unlocks", False, str(e))

    if new_token:
        try:
            resp = urlopen(_url(port4, "/api/files", new_token))
            r.check("Unlocked token works", resp.status == 200)
        except Exception as e:
            r.check("Unlocked token works", False, str(e))

    # Le code est insensible a la casse et aux separateurs
    messy = code[:3].lower() + "-" + code[3:].lower()
    try:
        resp = _unlock(port4, messy)
        r.check("Code case/separator insensitive", json.loads(resp.read()).get("success"), messy)
    except Exception as e:
        r.check("Code case/separator insensitive", False, str(e))

    # --- Persistance : ni le token ni le code ne changent sans reset ---
    print("\n  Session persistence tests...")
    state_dir = os.path.join(dd, "state")
    save_session_state("TOKENPERSISTANT", "ABC234", directory=state_dir)
    state = load_session_state(directory=state_dir)
    r.check("Session state round-trip",
            state == {"token": "TOKENPERSISTANT", "code": "ABC234"}, state)

    with open(os.path.join(state_dir, "session.json"), "w") as f:
        f.write("{corrompu")
    r.check("Corrupt state ignored", load_session_state(directory=state_dir) is None)
    r.check("Missing state ignored",
            load_session_state(directory=os.path.join(dd, "no_such_dir")) is None)

    r.check("Provided code reused", SessionManager(code="ABC234").code == "ABC234")
    r.check("Invalid code regenerated", len(SessionManager(code="!!").code) == 6)

    server5, port5, token5 = _start_server(session_code="ABC234")
    r.check("Server reuses persisted code", server5.sessions.code == "ABC234",
            server5.sessions.code)
    try:
        data = json.loads(_unlock(port5, "ABC234").read())
        r.check("Persisted code unlocks", data.get("success"), data)
    except Exception as e:
        r.check("Persisted code unlocks", False, str(e))
    server5.shutdown()

    # --- Le code reste utilisable une fois le jeton expire ----------------
    # C'est la fonction de secours : l'utilisateur retrouve l'acces en
    # tapant le code meme apres l'expiration de la session.
    print("\n  Code apres expiration du jeton...")
    limiter_session.reset()
    server6, port6, token6 = _start_server(session_expires_in=1)
    code6 = server6.sessions.code
    time.sleep(2)
    try:
        urlopen(_url(port6, "/api/files", token6))
        r.check("Jeton expire avant le deverrouillage", False, "toujours actif")
    except urllib.error.HTTPError as e:
        r.check("Jeton expire avant le deverrouillage", e.code == 403, e.code)
    try:
        data = json.loads(_unlock(port6, code6).read())
        token_secours = data.get("token")
        r.check("Code valide apres expiration du jeton",
                data.get("success") and bool(token_secours), data)
        resp = urlopen(_url(port6, "/api/files", token_secours))
        r.check("Jeton obtenu par le code fonctionne", resp.status == 200)
    except Exception as e:
        r.check("Code valide apres expiration du jeton", False, str(e))
    server6.shutdown()

    # --- Rotation du code via `python -m opendrop.main` -------------------
    # Deux demarrages sans reset doivent conserver le token ET le code ;
    # --rotate-token doit changer les deux et invalider l'ancien code.
    print("\n  Rotation du code (sous-processus opendrop.main)...")
    limiter_session.reset()
    work = tempfile.mkdtemp(prefix="opendrop_rotation_")
    proc1 = proc2 = proc3 = None
    try:
        cfg = os.path.join(work, "OpenDrop")
        recus = os.path.join(work, "recus")
        partage = os.path.join(work, "partage")
        os.makedirs(cfg, exist_ok=True)
        os.makedirs(recus, exist_ok=True)
        os.makedirs(partage, exist_ok=True)
        with open(os.path.join(cfg, "config.json"), "w", encoding="utf-8") as fh:
            json.dump({"download_directory": recus, "share_directory": partage,
                       "generate_new_token": False, "global_quota_bytes": 0}, fh)

        def _lance(*extra):
            port = find_available_port(20000 + int(time.time() * 1000) % 10000)
            proc, info = _spawn_main(["--headless", "--port", str(port), *extra], work)
            return proc, info, port

        proc1, info1, _ = _lance()
        r.check("opendrop.main headless publie token et code",
                info1 is not None and bool(info1.get("token"))
                and bool(info1.get("session_code")),
                info1 and {k: info1.get(k) for k in ("token", "session_code")})
        _stop(proc1)

        if info1:
            proc2, info2, _ = _lance()
            r.check("Sans rotation, token et code conserves",
                    info2 is not None
                    and info2.get("token") == info1.get("token")
                    and info2.get("session_code") == info1.get("session_code"),
                    info2 and {"token": info2.get("token"),
                               "code": info2.get("session_code")})
            _stop(proc2)

            proc3, info3, port3 = _lance("--rotate-token")
            if info3:
                r.check("--rotate-token change le token",
                        info3.get("token") != info1.get("token"))
                r.check("--rotate-token change le code de session",
                        info3.get("session_code") != info1.get("session_code"),
                        f"{info1.get('session_code')} -> {info3.get('session_code')}")

                try:
                    _unlock(port3, info1["session_code"])
                    r.check("Ancien code rejete apres rotation", False, "accepte")
                except urllib.error.HTTPError as e:
                    r.check("Ancien code rejete apres rotation", e.code == 403, e.code)

                try:
                    data = json.loads(_unlock(port3, info3["session_code"]).read())
                    r.check("Nouveau code accepte apres rotation",
                            data.get("success"), data)
                except Exception as e:
                    r.check("Nouveau code accepte apres rotation", False, str(e))

                etat = load_session_state(directory=cfg)
                r.check("session.json mis a jour par la rotation",
                        etat == {"token": info3.get("token"),
                                 "code": info3.get("session_code")}, etat)
            else:
                r.check("--rotate-token change le token", False,
                        "pas d'info du sous-processus")
                r.check("--rotate-token change le code de session", False, "")
            _stop(proc3)
        else:
            r.check("Sans rotation, token et code conserves", False, "pas de demarrage")
            r.check("--rotate-token change le token", False, "pas de demarrage")
    except Exception as e:
        r.check("Rotation du code (sous-processus)", False, repr(e))
    finally:
        for proc in (proc1, proc2, proc3):
            if proc is not None:
                _stop(proc)
        shutil.rmtree(work, ignore_errors=True)

    # Force brute : 5 tentatives/min/IP (doit passer en dernier)
    limiter_session.reset()
    blocked = False
    for _ in range(6):
        try:
            _unlock(port4, "ZZZZZZ")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                blocked = True
                break
    r.check("Code brute force limited", blocked, "should get 429")

    server4.shutdown()
    return r.summary()


if __name__ == "__main__":
    sys.exit(0 if test_sessions() else 1)
