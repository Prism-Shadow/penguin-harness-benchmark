"""Offline dependency smoke; no solver modules or external services are used."""
import os
import subprocess
import tempfile
from pathlib import Path

from certauth.certauth import CertificateAuthority
from httpbin import app
from OpenSSL import crypto
from webtest import TestApp
from gevent.pywsgi import WSGIServer


def main():
    response = TestApp(app).get("/get?probe=recorder")
    assert response.json["args"]["probe"] == "recorder"
    response = TestApp(app).post("/post", {"probe": "recording"})
    assert response.json["form"]["probe"] == "recording"
    with tempfile.TemporaryDirectory(prefix="pywb-cert-smoke-", dir=os.environ.get("TMPDIR")) as directory:
        root = Path(directory)
        root_path = root / "root.pem"
        authority = CertificateAuthority(
            ca_name="pywb task smoke", ca_file_cache=str(root_path)
        )
        root_pem = root_path.read_bytes()
        root_certificate = crypto.load_certificate(crypto.FILETYPE_PEM, root_pem)
        root_key = crypto.load_privatekey(crypto.FILETYPE_PEM, root_pem)
        assert root_certificate.get_subject().CN == "pywb task smoke"
        assert crypto.dump_publickey(crypto.FILETYPE_PEM, root_certificate.get_pubkey()) == crypto.dump_publickey(
            crypto.FILETYPE_PEM, root_key
        )
        certificate, private_key = authority.load_cert("localhost")
        certificate = crypto.load_certificate(
            crypto.FILETYPE_PEM, crypto.dump_certificate(crypto.FILETYPE_PEM, certificate)
        )
        assert certificate.get_subject().CN == "localhost"
        assert certificate.get_extension_count() > 0
        assert crypto.dump_publickey(crypto.FILETYPE_PEM, certificate.get_pubkey()) == crypto.dump_publickey(
            crypto.FILETYPE_PEM, private_key
        )
        store = crypto.X509Store()
        store.add_cert(root_certificate)
        crypto.X509StoreContext(store, certificate).verify_certificate()
        reloaded_authority = CertificateAuthority(
            ca_name="pywb task smoke", ca_file_cache=str(root_path)
        )
        reloaded_certificate, _private_key = reloaded_authority.load_cert("reloaded.localhost")
        assert reloaded_certificate.get_subject().CN == "reloaded.localhost"
        crypto.X509StoreContext(store, reloaded_certificate).verify_certificate()
        assert root_path.read_bytes() == root_pem
    subprocess.run(["node", "-e", "require('jsdom'); require('ws')"], check=True)
    with tempfile.TemporaryDirectory(prefix='pywb-browser-smoke-', dir=os.environ.get('TMPDIR')) as directory:
        result = subprocess.run([
            'chromium', '--headless', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
            '--disable-background-networking', '--no-first-run', '--user-data-dir=' + directory,
            '--dump-dom', 'data:text/html,<title>pywb-browser-smoke</title>',
        ], capture_output=True, text=True, check=True, timeout=30)
        assert '<title>pywb-browser-smoke</title>' in result.stdout
    print("httpbin GET/POST, certauth persisted CA/reload/leaf chain and keys, jsdom/ws, real Chromium: PASS")


if __name__ == "__main__":
    main()
