//! Update release validation: tag format, per-OS asset pick, SHA-256 check.
//!
//! The pre-1.0 desktop app (`UpdateService.cs`) only offered GitHub
//! releases whose tag was `vX.Y.Z`, picked the setup matching the OS and
//! verified the downloaded file against the release's digest before
//! running it as an installer. The Tauri port skipped all three: any tag
//! was accepted, the first asset was taken blindly and a tampered or
//! truncated download would still be executed. This module ports the
//! checks.
//!
//! Pure functions: tag parsing, asset selection and digest comparison are
//! all decided without touching the network, so the tests can drive them.

use std::path::Path;

#[cfg(test)]
use std::path::PathBuf;

/// A release tag is `v` + three dot-separated all-numeric parts
/// (`v1.0.0`, `v0.16.1`); anything else (`1.0.0`, `v1.0`, `v1.0.0-rc1`,
/// `latest`) is not an installable release.
pub fn is_release_tag(raw: &str) -> bool {
    let Some(rest) = raw.strip_prefix('v') else {
        return false;
    };
    let parts: Vec<&str> = rest.split('.').collect();
    parts.len() == 3
        && parts
            .iter()
            .all(|p| !p.is_empty() && p.chars().all(|c| c.is_ascii_digit()))
}

/// Pick the release asset to download for `linux`, returning
/// `(download_url, extension)`. `assets_json` is the release's `assets`
/// array as JSON (what `v["assets"].to_string()` yields). Windows prefers
/// the setup `.exe` and falls back to the `.msi`; Linux only updates from
/// the `.tar.gz` (the pkexec installer path). No fitting asset is an
/// error - never "first one wins".
pub fn pick_asset(assets_json: &str, linux: bool) -> Result<(String, String), String> {
    let list: Vec<serde_json::Value> = serde_json::from_str(assets_json)
        .map_err(|e| format!("assets json: {e}"))?;
    if list.is_empty() {
        return Err("assets json: no assets array".into());
    }

    let entry = |ext: &str| -> Option<(String, String)> {
        list.iter().find_map(|a| {
            let name = a.get("name")?.as_str()?;
            if name.to_ascii_lowercase().ends_with(ext) {
                let url = a.get("browser_download_url")?.as_str()?.to_string();
                Some((url, ext.to_string()))
            } else {
                None
            }
        })
    };

    if linux {
        return entry(".tar.gz").ok_or_else(|| "no .tar.gz asset".into());
    }
    entry(".exe")
        .or_else(|| entry(".msi"))
        .ok_or_else(|| "no .exe/.msi asset".into())
}

/// Why [`verify_sha256`] refused a file. The two outcomes are NOT
/// interchangeable for the caller: only a `Mismatch` may delete, an
/// `Unverified` digest never compared the bytes at all (so a perfectly
/// good installer left by a previous session must survive it).
pub enum VerifyErr {
    /// The digest field is unusable (empty, other algorithm, non-hex) or
    /// the file could not be hashed: nothing was compared, the file on
    /// disk is left alone.
    Unverified(String),
    /// The bytes hashed to a different value: the file has been deleted.
    Mismatch(String),
}

impl VerifyErr {
    /// True only for a completed hash that disagreed - the sole case in
    /// which the file was removed.
    pub fn is_mismatch(&self) -> bool {
        matches!(self, VerifyErr::Mismatch(_))
    }
}

impl std::fmt::Display for VerifyErr {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            VerifyErr::Unverified(m) | VerifyErr::Mismatch(m) => f.write_str(m),
        }
    }
}

/// Check a downloaded file against GitHub's `"sha256:<hex>"` digest.
/// A wrong or unreadable digest is refused WITHOUT deleting anything (the
/// format alone is wrong); only a digest that does not match the bytes
/// deletes the file, so a tampered or truncated download can never become
/// an installer.
pub fn verify_sha256(path: &Path, digest_field: &str) -> Result<(), VerifyErr> {
    let hex = digest_field
        .strip_prefix("sha256:")
        .filter(|h| h.len() == 64 && h.chars().all(|c| c.is_ascii_hexdigit()))
        .ok_or_else(|| {
            VerifyErr::Unverified("unsupported digest (expected sha256:<64 hex>)".into())
        })?;

    // Hashed STREAMING, 8 KiB at a time: the installer is ~110 MB, and
    // reading it whole would hold the bytes AND the digest buffer in RAM
    // at once for no reason.
    use sha2::{Digest, Sha256};
    use std::io::Read;
    let mut file = std::fs::File::open(path).map_err(|e| {
        VerifyErr::Unverified(format!("read {}: {e}", path.display()))
    })?;
    let mut hasher = Sha256::new();
    let mut buf = vec![0u8; 8 * 1024];
    loop {
        let n = file.read(&mut buf).map_err(|e| {
            VerifyErr::Unverified(format!("read {}: {e}", path.display()))
        })?;
        if n == 0 {
            break;
        }
        hasher.update(&buf[..n]);
    }
    let got = format!("{:x}", hasher.finalize());

    if got.eq_ignore_ascii_case(hex) {
        Ok(())
    } else {
        let _ = std::fs::remove_file(path);
        Err(VerifyErr::Mismatch(format!(
            "digest mismatch for {} (expected sha256:{hex}, got sha256:{got})",
            path.display()
        )))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::time::{SystemTime, UNIX_EPOCH};

    /// Fresh temp dir (unique per test invocation).
    fn fresh(label: &str) -> PathBuf {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let dir = std::env::temp_dir().join(format!(
            "opendrop-updater-{}-{}-{}",
            std::process::id(),
            label,
            nanos
        ));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    // ---- is_release_tag -------------------------------------------------

    #[test]
    fn accepts_only_v_semver_tags() {
        // the three forms a release tag must have
        assert!(is_release_tag("v1.0.0"));
        assert!(is_release_tag("v0.16.1"));
        assert!(is_release_tag("v10.20.30"));

        // everything else is refused
        assert!(!is_release_tag("1.0.0")); // no leading v
        assert!(!is_release_tag("v1.0")); // two parts
        assert!(!is_release_tag("v1.0.0-rc1")); // pre-release suffix
        assert!(!is_release_tag("v1.0.0.1")); // four parts
        assert!(!is_release_tag("vv1.0.0")); // doubled v
        assert!(!is_release_tag("v1.0.x")); // non-numeric part
        assert!(!is_release_tag(""));
        assert!(!is_release_tag("latest"));
    }

    // ---- pick_asset -----------------------------------------------------

    /// GitHub release asset list as `v["assets"].to_string()` yields it,
    /// keeping the assets in declaration order.
    fn assets(names: &[&str]) -> String {
        let list: Vec<String> = names
            .iter()
            .map(|n| format!(
                r#"{{"name":"{n}","browser_download_url":"https://dl/{n}"}}"#
            ))
            .collect();
        format!("[{}]", list.join(","))
    }

    #[test]
    fn picks_exe_then_msi_on_windows() {
        // .exe wins even when the .msi is declared first
        let j = assets(&["OpenDrop_1.0.0_x64_en-US.msi", "OpenDrop_1.0.0_x64-setup.exe"]);
        let (url, ext) = pick_asset(&j, false).unwrap();
        assert_eq!(url, "https://dl/OpenDrop_1.0.0_x64-setup.exe");
        assert_eq!(ext, ".exe");

        // no .exe at all: the .msi is the Windows fallback
        let j = assets(&["OpenDrop_1.0.0_x64_en-US.msi", "checksums.txt"]);
        let (url, ext) = pick_asset(&j, false).unwrap();
        assert_eq!(url, "https://dl/OpenDrop_1.0.0_x64_en-US.msi");
        assert_eq!(ext, ".msi");

        // neither: refuse rather than run a random file
        assert!(pick_asset(&assets(&["checksums.txt"]), false).is_err());
        assert!(pick_asset(&assets(&[]), false).is_err());
        // malformed JSON is an error, not a panic
        assert!(pick_asset("not json", false).is_err());
    }

    #[test]
    fn picks_tarball_on_linux() {
        // Linux updates install from the tarball (never the Windows setup)
        let j = assets(&[
            "OpenDrop_1.0.0_amd64.deb",
            "OpenDrop-1.0.0-x86_64.tar.gz",
            "OpenDrop_1.0.0_x64-setup.exe",
        ]);
        let (url, ext) = pick_asset(&j, true).unwrap();
        assert_eq!(url, "https://dl/OpenDrop-1.0.0-x86_64.tar.gz");
        assert_eq!(ext, ".tar.gz");

        // no tarball: refuse (a .deb has no pkexec install path here)
        assert!(pick_asset(&assets(&["OpenDrop_1.0.0_amd64.deb"]), true).is_err());
        assert!(pick_asset(&assets(&[]), true).is_err());
        assert!(pick_asset("not json", true).is_err());
    }

    // ---- verify_sha256 --------------------------------------------------

    /// SHA-256 of the exact bytes, formatted the way GitHub writes digests.
    fn gh_digest(bytes: &[u8]) -> String {
        use sha2::{Digest, Sha256};
        format!("sha256:{:x}", Sha256::digest(bytes))
    }

    #[test]
    fn sha256_matches_known_vector() {
        // RFC 6234 / NIST test vector: SHA-256("abc")
        let d = gh_digest(b"abc");
        assert_eq!(
            d,
            "sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );

        // a matching digest on a real file passes
        let dir = fresh("ok");
        let f = dir.join("setup.exe");
        fs::write(&f, b"abc").unwrap();
        assert!(verify_sha256(&f, &d).is_ok());
    }

    #[test]
    fn digest_mismatch_deletes_the_file() {
        let dir = fresh("mismatch");
        let f = dir.join("setup.exe");
        fs::write(&f, b"tampered bytes").unwrap();

        let other = gh_digest(b"other bytes");
        let err = verify_sha256(&f, &other).unwrap_err();
        // a COMPLETED hash that disagreed is the deleting variant
        assert!(err.is_mismatch(), "expected a mismatch, got: {err}");
        assert!(err.to_string().contains("mismatch"), "unexpected error: {err}");
        // the wrong download must NOT survive to become an installer
        assert!(!f.exists(), "mismatched file must be deleted");

        // a file that cannot be read at all is an error too
        let missing = dir.join("absent.exe");
        assert!(verify_sha256(&missing, &other).is_err());
    }

    #[test]
    fn missing_digest_is_refused() {
        let dir = fresh("nodigest");
        let f = dir.join("setup.exe");
        fs::write(&f, b"abc").unwrap();

        // empty digest: no silent pass (an absent field must not unlock
        // the install button)
        let err = verify_sha256(&f, "").unwrap_err();
        assert!(!err.is_mismatch(), "nothing was hashed: {err}");
        // another algorithm or a bare hex string is not accepted either
        for d in ["sha512:deadbeef", "ba7816bf", "sha256:not-hex"] {
            let e = verify_sha256(&f, d).unwrap_err();
            assert!(!e.is_mismatch(), "{d} must be refused by format alone");
        }
        // refused by format alone: the file is left alone, not deleted
        assert!(f.exists());
    }
}
