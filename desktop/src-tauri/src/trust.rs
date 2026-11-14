//! One-click trust of the local CA on Windows.
//!
//! The browser only drops the "Continue anyway" interstitial and the
//! "Not secure" badge once the local CA (the engine's `ca.crt`, see
//! `src/opendrop/security/tls_cert.py`) sits in a Windows trust store.
//! Doing that by hand is the cert import wizard - double-click, pick
//! "Trusted Root Certification Authorities", confirm the security
//! alert - and it is the step every user stalls on.
//!
//! This module detects the trust state of that file and installs it in
//! one click: `certutil -user -addstore -f Root` writes it to
//! `CurrentUser\Root` with no admin rights and no dialog, exactly what
//! mkcert does for its own CA.
//!
//! Security notes:
//! - The file path and the expected subject reach PowerShell through
//!   environment variables (`OPENDROP_CA_CERT`, `OPENDROP_CA_SUBJECT`),
//!   never through string concatenation: a path containing quotes,
//!   `$` or `;` cannot turn into code.
//! - Only a certificate whose subject IS the engine's CA is ever
//!   installed (`Foreign` stops the install): an old self-signed cert
//!   or a foreign file in `certs\` must never land in a trust store.
//! - `install()` re-runs the detection afterwards and only reports
//!   success on a fresh `Trusted` - a `certutil` exit code alone does
//!   not prove the store took the certificate.
//!
//! Detection is Windows-only (there is no store API to poll elsewhere);
//! on other platforms the commands report `unsupported` and the UI
//! hides the chip.

/// Where the engine keeps its CA: `get_config_dir() / "certs" /
/// "ca.crt"` (config.py) - the same `LOCALAPPDATA\OpenDrop` base the
/// Rust side already uses for `moves.json`.
#[cfg(windows)]
fn ca_path() -> std::path::PathBuf {
    crate::config_dir().join("certs").join("ca.crt")
}

/// The subject the engine's CA is generated with (tls_cert.py
/// `_generate_ca`: a single `CN` RDN). Anything else on disk is not our
/// anchor and must never be installed.
#[cfg(windows)]
const CA_SUBJECT: &str = "CN=OpenDrop Local CA";

/// One PowerShell pass over the Windows stores. Prints exactly one
/// token on stdout: TRUSTED / UNTRUSTED / MISSING / INVALID / FOREIGN.
#[cfg(windows)]
const DETECT: &str = r#"
$path = $env:OPENDROP_CA_CERT
if (-not $path -or -not (Test-Path -LiteralPath $path)) { Write-Output 'MISSING'; exit 0 }
try {
    $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2 -ArgumentList $path
} catch {
    Write-Output 'INVALID'; exit 0
}
if ($cert.Subject -ne $env:OPENDROP_CA_SUBJECT) { Write-Output 'FOREIGN'; exit 0 }
$hit = Get-ChildItem Cert:\CurrentUser\Root, Cert:\LocalMachine\Root -ErrorAction SilentlyContinue |
    Where-Object { $_.Thumbprint -eq $cert.Thumbprint }
if ($hit) { Write-Output 'TRUSTED' } else { Write-Output 'UNTRUSTED' }
"#;

/// Trust state of the local CA, as reported to the UI (serialized
/// lowercase: "untrusted", "trusted", ...).
#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize)]
#[serde(rename_all = "lowercase")]
// The variants are platform-split (Windows never builds `Unsupported`,
// other platforms never build the rest), hence the blanket allow.
#[allow(dead_code)]
pub enum TrustStatus {
    /// Not Windows: no store to check, no chip in the UI.
    Unsupported,
    /// No `ca.crt` yet (older engine, or the CA was deleted): the
    /// engine regenerates it on start, nothing to install.
    Missing,
    /// The file exists but is not a readable certificate.
    Invalid,
    /// A certificate, but not the engine's CA - never install it.
    Foreign,
    /// Our CA, in no store: the UI offers the one-click install.
    Untrusted,
    /// Our CA is in a store: nothing to do, badge gone for good.
    Trusted,
}

/// The token the detection script printed -> status. Anything else is
/// a script error (stderr, a PS banner, ...), never a status.
#[cfg(windows)]
fn parse(token: &str) -> Result<TrustStatus, String> {
    match token {
        "TRUSTED" => Ok(TrustStatus::Trusted),
        "UNTRUSTED" => Ok(TrustStatus::Untrusted),
        "MISSING" => Ok(TrustStatus::Missing),
        "INVALID" => Ok(TrustStatus::Invalid),
        "FOREIGN" => Ok(TrustStatus::Foreign),
        other => Err(format!("trust: unexpected token {other:?}")),
    }
}

/// Run the detection script against `ca` and return the first
/// non-empty stdout line (the token).
#[cfg(windows)]
fn run_detect(ca: &std::path::Path) -> Result<String, String> {
    let out = crate::service_command("powershell")
        .args(["-NoProfile", "-NonInteractive", "-Command", DETECT])
        .env("OPENDROP_CA_CERT", ca)
        .env("OPENDROP_CA_SUBJECT", CA_SUBJECT)
        .output()
        .map_err(|e| format!("trust detect: {e}"))?;
    if !out.status.success() {
        return Err(format!("trust detect: exit {}", out.status));
    }
    let stdout = String::from_utf8_lossy(&out.stdout);
    let token = stdout
        .lines()
        .map(str::trim)
        .find(|l| !l.is_empty())
        .unwrap_or("");
    Ok(token.to_string())
}

/// Detect the trust state of a specific CA file (the tests drive this
/// with fixtures; nothing here touches a store).
#[cfg(windows)]
fn status_at(ca: &std::path::Path) -> Result<TrustStatus, String> {
    parse(&run_detect(ca)?)
}

/// Trust state of the engine's CA. The UI only shows the install chip
/// on `Untrusted`; `Missing`/`Invalid`/`Foreign` are states the engine
/// itself repairs (it regenerates an unusable CA on start).
#[cfg(windows)]
pub fn status() -> Result<TrustStatus, String> {
    status_at(&ca_path())
}

#[cfg(not(windows))]
pub fn status() -> Result<TrustStatus, String> {
    Ok(TrustStatus::Unsupported)
}

/// Install the engine's CA into `CurrentUser\Root` and return the
/// fresh status (`Trusted` on success). No admin rights, no dialog:
/// `certutil -user -addstore -f Root` is the silent mkcert path.
#[cfg(windows)]
pub fn install() -> Result<TrustStatus, String> {
    let ca = ca_path();
    match status_at(&ca)? {
        // Already trusted: idempotent, report success without touching
        // the store again.
        TrustStatus::Trusted => return Ok(TrustStatus::Trusted),
        // Nothing safe to install: no file, an unreadable one, or a
        // certificate that is not our CA (see module docs).
        TrustStatus::Missing | TrustStatus::Invalid | TrustStatus::Foreign => {
            return Err(format!("trust install: not installable ({ca:?})"));
        }
        TrustStatus::Untrusted | TrustStatus::Unsupported => {}
    }

    let out = crate::service_command("certutil")
        .args(["-user", "-addstore", "-f", "Root"])
        .arg(&ca)
        .output()
        .map_err(|e| format!("trust install: {e}"))?;
    if !out.status.success() {
        let err = String::from_utf8_lossy(&out.stderr);
        let err = if err.trim().is_empty() {
            String::from_utf8_lossy(&out.stdout).to_string()
        } else {
            err.to_string()
        };
        return Err(format!("trust install: {}", err.trim()));
    }

    // certutil's exit code alone does not prove the store took it:
    // only a fresh detection may call this a success.
    let after = status_at(&ca)?;
    if after == TrustStatus::Trusted {
        Ok(after)
    } else {
        Err(format!("trust install: store still reports {after:?}"))
    }
}

#[cfg(not(windows))]
pub fn install() -> Result<TrustStatus, String> {
    Err("trust install: unsupported platform".into())
}

#[cfg(all(test, windows))]
mod tests {
    use super::*;

    /// Fixture PEMs, generated once with the engine's own recipe
    /// (EC P-256, self-signed): one shaped exactly like the engine's
    /// CA, one with a foreign CN. They are inert test material - the
    /// suite NEVER installs anything (a store write would be a
    /// machine-level side effect no unit test may have).
    const CA_PEM: &str = "-----BEGIN CERTIFICATE-----\n\
MIIBTzCB9qADAgECAhRdws1ceeeV6VLFzSXNG9YCu3t3JzAKBggqhkjOPQQDAjAc\n\
MRowGAYDVQQDDBFPcGVuRHJvcCBMb2NhbCBDQTAeFw0yNjExMTMyMTIwMzZaFw0y\n\
NzExMTQyMTIwMzZaMBwxGjAYBgNVBAMMEU9wZW5Ecm9wIExvY2FsIENBMFkwEwYH\n\
KoZIzj0CAQYIKoZIzj0DAQcDQgAElnCUHJLxtj26K8v1qGO4BqM2+u1jZlbqj0Zx\n\
AbHkw44oE80ZLGgVP3sb6FnKZzr3SFL+UfyuNCPJNn4unbfdjKMWMBQwEgYDVR0T\n\
AQH/BAgwBgEB/wIBADAKBggqhkjOPQQDAgNIADBFAiEAt509zUf+GyUZJyXggh5Y\n\
pUs9XrqQmLVJzyVhI6kzFoQCIHDlvj5acWZRGBmolBScW20yAO+qqQqmo39tR0Gk\n\
LbD3\n\
-----END CERTIFICATE-----\n";

    const FOREIGN_PEM: &str = "-----BEGIN CERTIFICATE-----\n\
MIIBNzCB3aADAgECAhRSumzSDI0fkzO7GXwNYH1kjI4x2jAKBggqhkjOPQQDAjAP\n\
MQ0wCwYDVQQDDARUZXN0MB4XDTI2MTExMzIxMjAzNloXDTI3MTExNDIxMjAzNlow\n\
DzENMAsGA1UEAwwEVGVzdDBZMBMGByqGSM49AgEGCCqGSM49AwEHA0IABMpuUImO\n\
lVVN73QNDCBLFXBbkmRCpg6Y1II903ZTcSgM3dpxrAyKJf7GN5ZXsE1T1K2PbN80\n\
VME2CNFJVijsRsyjFzAVMBMGA1UdJQQMMAoGCCsGAQUFBwMBMAoGCCqGSM49BAMC\n\
A0kAMEYCIQCRBIR/QWLg8IS8bbp3YmFVxc4HpCX+PUJXjedngn5I7QIhAKtrIyM3\n\
33W3MUGjjLZ+uSfvlt/XWvzicmeWCogDKJ99\n\
-----END CERTIFICATE-----\n";

    /// Write `content` under the temp dir, with a per-process name so
    /// parallel test runs never collide.
    fn fixture(name: &str, content: &str) -> std::path::PathBuf {
        let path =
            std::env::temp_dir().join(format!("opendrop-trust-{name}-{}.crt", std::process::id()));
        std::fs::write(&path, content).expect("write fixture");
        path
    }

    #[test]
    fn missing_file_reports_missing() {
        let path = std::env::temp_dir().join("opendrop-trust-no-such-file.crt");
        let _ = std::fs::remove_file(&path);
        assert_eq!(status_at(&path).expect("detect"), TrustStatus::Missing);
    }

    #[test]
    fn garbage_file_reports_invalid() {
        let path = fixture("invalid", "this is not a certificate");
        let got = status_at(&path).expect("detect");
        let _ = std::fs::remove_file(&path);
        assert_eq!(got, TrustStatus::Invalid);
    }

    #[test]
    fn foreign_cn_reports_foreign() {
        let path = fixture("foreign", FOREIGN_PEM);
        let got = status_at(&path).expect("detect");
        let _ = std::fs::remove_file(&path);
        assert_eq!(got, TrustStatus::Foreign);
    }

    #[test]
    fn our_ca_not_in_a_store_reports_untrusted() {
        // A freshly generated fixture can only be in a store if some
        // other run installed it - the suite never does.
        let path = fixture("ca", CA_PEM);
        let got = status_at(&path).expect("detect");
        let _ = std::fs::remove_file(&path);
        assert_eq!(got, TrustStatus::Untrusted);
    }
}
