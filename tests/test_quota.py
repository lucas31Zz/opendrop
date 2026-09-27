"""Tests du quota global du dossier de reception.

Couvre : le scan du dossier, les reservations (y compris simultanees), le
refus en 507, la liberation de la reservation apres un envoi echoue, et le
quota desactive (illimite).
"""
import http.client
import json
import os
import shutil
import sys
import threading
import time
import urllib.error

from opendrop.network.interfaces import find_available_port
from opendrop.server.errors import QuotaExceededError
from opendrop.server.quota import QuotaTracker, directory_usage, format_size
from opendrop.server.rate_limit import limiter_general, limiter_upload
from opendrop.server.server import create_server
from tests.conftest import (SSL_CONTEXT, _raw_upload, _upload, TestResult,
                            cert_dir, dd, ip, sd)

r = TestResult()

QUOTA_BASE = os.path.join(dd, "quota")


def _start_quota(limit, name):
    """Serveur isole avec son propre dossier de reception (scan exact)."""
    dl = os.path.join(QUOTA_BASE, name)
    shutil.rmtree(dl, ignore_errors=True)
    os.makedirs(dl, exist_ok=True)
    port = find_available_port(15000 + int(time.time() * 1000) % 10000)
    token = "quotatoken_" + str(port)
    server = create_server(ip, port, token, dl, sd,
                           tls_cert_dir=cert_dir, global_quota_bytes=limit)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    time.sleep(0.3)
    limiter_upload.reset()
    limiter_general.reset()
    return server, port, token, dl


def _garbage_upload(port, token, size):
    """Corps de la longueur annoncee mais sans frontiere multipart valide.

    Le serveur lit tout le corps (la reservation est donc consommee),
    echoue au decoupage puis doit rendre la reservation.
    """
    garbage = b"\x00\xffOPENDROP" * (size // 10 + 1)
    garbage = garbage[:size]
    conn = http.client.HTTPSConnection("127.0.0.1", port, context=SSL_CONTEXT, timeout=20)
    try:
        conn.request("POST", f"/api/upload?token={token}", body=garbage,
                     headers={"Content-Type": "multipart/form-data; boundary=----GARBAGE"})
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


def _post_body(port, token, body):
    """POST /api/upload avec un corps deja construit (longueur exacte)."""
    conn = http.client.HTTPSConnection("127.0.0.1", port, context=SSL_CONTEXT, timeout=20)
    try:
        conn.request("POST", f"/api/upload?token={token}", body=body,
                     headers={"Content-Type": "multipart/form-data; boundary=----TEST",
                              "Content-Length": str(len(body))})
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


def _check_upload(port, token, name, size, label):
    try:
        data = json.loads(_upload(port, token, name, b"x" * size).read())
        r.check(label, bool(data.get("success")), data)
    except Exception as e:
        r.check(label, False, str(e))


def _check_refused(port, token, declared, label):
    status, body = _raw_upload(port, token, declared)
    try:
        payload = json.loads(body)
    except ValueError:
        payload = {}
    r.check(label,
            status == 507 and "Quota global" in payload.get("error", ""),
            f"{status} {payload}")


def _get(port, path):
    conn = http.client.HTTPSConnection("127.0.0.1", port, context=SSL_CONTEXT, timeout=10)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


def _get_json(port, path):
    status, body = _get(port, path)
    if status != 200:
        raise AssertionError(f"GET {path} -> {status} {body[:120]}")
    return json.loads(body)


def _unit_tests():
    print("--- Quota unit tests ---\n")

    unit_dir = os.path.join(QUOTA_BASE, "unit")
    shutil.rmtree(unit_dir, ignore_errors=True)
    os.makedirs(os.path.join(unit_dir, "sub"))
    with open(os.path.join(unit_dir, "a.bin"), "wb") as fh:
        fh.write(b"x" * 1000)
    with open(os.path.join(unit_dir, "sub", "b.bin"), "wb") as fh:
        fh.write(b"y" * 2500)

    r.check("directory_usage somme les fichiers (recursif)",
            directory_usage(unit_dir) == 3500, directory_usage(unit_dir))
    r.check("directory_usage dossier absent = 0",
            directory_usage(os.path.join(QUOTA_BASE, "inexistant")) == 0)
    r.check("format_size en Ko", format_size(3500).endswith("Ko"), format_size(3500))
    r.check("format_size en Go", format_size(2 ** 31).endswith("Go"), format_size(2 ** 31))

    tr = QuotaTracker(unit_dir, 4000)
    r.check("Quota actif", tr.enabled)
    r.check("Usage initial = taille du dossier", tr.usage() == 3500, tr.usage())

    tr.reserve(400)
    r.check("Reservation prise en compte", tr.usage() == 3900, tr.usage())
    try:
        tr.reserve(200)
        r.check("Reservation au dela du quota refusee", False, "aucune exception")
    except QuotaExceededError as e:
        r.check("Reservation au dela du quota refusee", "Quota global" in str(e), str(e))

    tr.release(400)
    r.check("Release rend la place", tr.usage() == 3500, tr.usage())
    try:
        tr.reserve(500)
        r.check("Quota exactement atteint accepte", True)
    except QuotaExceededError as e:
        r.check("Quota exactement atteint accepte", False, str(e))
    tr.release(500)

    illimite = QuotaTracker(unit_dir, 0)
    r.check("Quota 0 = desactive", not illimite.enabled)
    try:
        illimite.reserve(10 ** 12)
        r.check("Sans quota, aucune limite", True)
    except QuotaExceededError as e:
        r.check("Sans quota, aucune limite", False, str(e))
    r.check("remaining sans quota = -1", illimite.remaining() == -1, illimite.remaining())

    # Quota negatif (config editee a la main) : traite comme desactive, pas
    # comme une limite impossible a satisfaire.
    negatif = QuotaTracker(unit_dir, -5)
    r.check("Quota negatif = desactive", not negatif.enabled, negatif.limit_bytes)
    try:
        negatif.reserve(10 ** 9)
        r.check("Quota negatif: aucun refus", True)
    except QuotaExceededError as e:
        r.check("Quota negatif: aucun refus", False, str(e))

    # Deux envois simultanes ne peuvent pas passer la main sous la limite
    vide = os.path.join(QUOTA_BASE, "vide")
    os.makedirs(vide, exist_ok=True)
    conc = QuotaTracker(vide, 30000)
    pris = threading.Event()
    libere = threading.Event()

    def _hold():
        conc.reserve(20000)
        pris.set()
        libere.wait(5)
        conc.release(20000)

    t = threading.Thread(target=_hold)
    t.start()
    pris.wait(5)
    try:
        conc.reserve(20000)
        r.check("Reservation simultanee refusee", False, "les deux reservations sont passees")
    except QuotaExceededError:
        r.check("Reservation simultanee refusee", True)
    finally:
        libere.set()
        t.join(timeout=5)


def _server_tests():
    print("\n--- Quota server tests ---\n")

    # Quota a 50 000 octets
    server, port, token, dl = _start_quota(50000, "srv1")
    try:
        _check_upload(port, token, "dedans.bin", 10000, "Upload dans le quota accepte")

        _check_refused(port, token, 60000, "Upload au dela du quota refuse (507)")
        r.check("Aucun fichier cree par l'envoi refuse",
                sorted(os.listdir(dl)) == ["dedans.bin"], os.listdir(dl))

        # 10 000 deja presents + 35 000 = 45 000 <= 50 000 : le scan compte
        _check_upload(port, token, "encore.bin", 35000, "Upload calculant l'usage du dossier")

        # 45 000 + 10 000 > 50 000 : refuse sur l'usage scanne
        _check_refused(port, token, 10000, "Refus base sur l'usage du dossier")

        # Emission complete au dela du quota : le client doit pouvoir lire le
        # 507 (la connexion n'est pas coupee pendant qu'il ecrit encore).
        try:
            _upload(port, token, "reel_trop.bin", b"x" * 20000)
            r.check("Envoi reel au dela du quota : 507 lisible", False, "accepte")
        except urllib.error.HTTPError as e:
            payload = json.loads(e.read())
            r.check("Envoi reel au dela du quota : 507 lisible",
                    e.code == 507 and "Quota global" in payload.get("error", ""),
                    f"{e.code} {payload}")
        except Exception as e:
            r.check("Envoi reel au dela du quota : 507 lisible", False, repr(e))

        for name in os.listdir(dl):
            os.remove(os.path.join(dl, name))
        _check_upload(port, token, "apres_liberation.bin", 40000,
                      "Upload apres liberation d'espace")
    finally:
        server.shutdown()
        server.server_close()

    # Reservation liberee meme si l'envoi echoue
    server, port, token, dl = _start_quota(20000, "srv2")
    try:
        status, body = _garbage_upload(port, token, 15000)
        r.check("Corps invalide rejete", status == 400, f"{status} {body[:120]}")
        r.check("Aucun fichier cree par l'envoi invalide",
                os.listdir(dl) == [], os.listdir(dl))
        # Sans liberation, les 15 000 annonces resteraient reserves et ce
        # dernier envoi (15 000 <= 20 000) serait refuse.
        _check_upload(port, token, "apres_echec.bin", 15000,
                      "Reservation liberee apres un envoi echoue")
    finally:
        server.shutdown()
        server.server_close()

    # Quota desactive (0) : malgre 60 000 deja presents, tout passe
    server, port, token, dl = _start_quota(0, "srv3")
    try:
        with open(os.path.join(dl, "existant.bin"), "wb") as fh:
            fh.write(b"w" * 60000)
        r.check("Quota 0 = desactive cote serveur", not server.quota.enabled)
        _check_upload(port, token, "sans_quota.bin", 60000,
                      "Upload au dela de tout quota precedemment refuse")
    finally:
        server.shutdown()
        server.server_close()

    # Remplissage exact : le quota est reserve sur le Content-Length, donc
    # on envoie un corps de longueur pile egale au quota. Ce dernier octet
    # doit passer, l'envoi suivant etre refuse.
    server, port, token, dl = _start_quota(50000, "srv_exact")
    try:
        entete = (b"--" + b"----TEST" + b"\r\n"
                  b'Content-Disposition: form-data; name="file"; filename="plein.bin"\r\n'
                  b"Content-Type: text/plain\r\n\r\n")
        pied = b"\r\n--" + b"----TEST" + b"--\r\n"
        corps = entete + b"x" * (50000 - len(entete) - len(pied)) + pied
        statut, corps_reponse = _post_body(port, token, corps)
        r.check("Remplissage exact du quota (50 000 octets)",
                statut == 200 and len(corps) == 50000,
                f"{statut} len={len(corps)} {corps_reponse[:120]}")
        # Le dossier ne contient que le contenu du fichier (les entetes
        # multipart ne sont pas ecrites) : il reste "framing" octets de quota.
        r.check("Usage apres remplissage exact = taille du fichier",
                server.quota.usage() == 50000 - len(entete) - len(pied),
                server.quota.usage())

        # Le quota restant ne couvre meme plus l'entete d'un envoi
        try:
            _upload(port, token, "apres_plein.bin", b"y")
            r.check("Octet apres remplissage exact refuse", False, "accepte")
        except urllib.error.HTTPError as e:
            payload = json.loads(e.read())
            r.check("Octet apres remplissage exact refuse",
                    e.code == 507 and "Quota global" in payload.get("error", ""),
                    f"{e.code} {payload}")
        except Exception as e:
            r.check("Octet apres remplissage exact refuse", False, repr(e))
        r.check("Aucun fichier cree apres remplissage exact",
                sorted(os.listdir(dl)) == ["plein.bin"], os.listdir(dl))
    finally:
        server.shutdown()
        server.server_close()

    # Deux envois reels simultanes : la reservation atomique garantit que
    # l'un des deux est refuse en 507 et que le total reste <= quota.
    server, port, token, dl = _start_quota(30000, "srv_conc")
    try:
        resultats = [None, None]

        def _lance(index):
            try:
                resp = _upload(port, token, f"sim_{index}.bin", b"c" * 20000)
                resultats[index] = ("ok", resp.status)
            except urllib.error.HTTPError as e:
                resultats[index] = ("err", e.code)
            except Exception as e:
                resultats[index] = ("exc", repr(e))

        threads = [threading.Thread(target=_lance, args=(i,)) for i in (0, 1)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        codes = sorted(x[1] for x in resultats)
        r.check("Envois simultanes : un 200 et un 507", codes == [200, 507],
                resultats)
        r.check("Envois simultanes : total <= quota",
                directory_usage(dl) <= 30000, directory_usage(dl))
        r.check("Envois simultanes : aucun fichier partiel",
                sorted(os.listdir(dl)) == ["sim_0.bin"] or
                sorted(os.listdir(dl)) == ["sim_1.bin"], os.listdir(dl))
    finally:
        server.shutdown()
        server.server_close()


def _api_tests():
    print("--- Quota API (interface web) ---\n")

    server, port, token, dl = _start_quota(50000, "api")
    try:
        status, body = _get(port, "/api/quota")
        r.check("GET /api/quota sans token refuse",
                status == 403, f"{status} {body[:80]}")

        with open(os.path.join(dl, "existant.bin"), "wb") as fh:
            fh.write(b"q" * 12345)
        data = _get_json(port, f"/api/quota?token={token}")
        r.check("GET /api/quota renvoie usage et quota",
                data.get("usage_bytes") >= 12345 and data.get("limit_bytes") == 50000,
                data)

        _check_upload(port, token, "api.bin", 4000, "Envoi accepte avant la lecture du quota")
        data = _get_json(port, f"/api/quota?token={token}")
        r.check("Usage mis a jour apres un envoi",
                data.get("usage_bytes") >= 16345, data.get("usage_bytes"))
    finally:
        server.shutdown()
        server.server_close()

    server, port, token, dl = _start_quota(0, "api_off")
    try:
        data = _get_json(port, f"/api/quota?token={token}")
        r.check("Quota desactive renvoie limit_bytes 0",
                data.get("limit_bytes") == 0, data)
    finally:
        server.shutdown()
        server.server_close()


def test_quota():
    print("--- Quota tests ---\n")
    _unit_tests()
    _server_tests()
    _api_tests()
    return r.summary()


if __name__ == "__main__":
    sys.exit(0 if test_quota() else 1)
