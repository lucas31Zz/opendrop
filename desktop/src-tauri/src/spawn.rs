//! Engine interpreter resolution.
//!
//! The pre-1.0 desktop app (`ServerManager.cs`) resolved the project root,
//! preferred the bundle's own venv over PATH `python` and prepended
//! `<root>/src` to `PYTHONPATH`. Without that, an installed build (bundle
//! with `src/` + a venv built from the bundled wheels, no editable install)
//! cannot `import opendrop`, so the engine would never start on a clean
//! machine. This module ports that resolution.

use std::path::{Path, PathBuf};
use std::process::Command;

/// Walk up from `start` (max 8 parents) looking for the `pyproject.toml`
/// that marks the project root; fall back to `start` itself.
pub fn project_root_from(start: &Path) -> PathBuf {
    let mut dir = start.to_path_buf();
    for _ in 0..8 {
        if dir.join("pyproject.toml").is_file() {
            return dir;
        }
        match dir.parent() {
            Some(p) => dir = p.to_path_buf(),
            None => break,
        }
    }
    start.to_path_buf()
}

/// The project root for a running build: the folder of the current exe,
/// walked up (installed bundle: `pyproject.toml` sits next to the exe;
/// dev build: the repo root above `target/debug`).
pub fn project_root() -> PathBuf {
    let start = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.to_path_buf()))
        .unwrap_or_else(|| std::env::current_dir().unwrap_or_else(|_| PathBuf::from(".")));
    project_root_from(&start)
}

/// Interpreter candidates, in order: the bundle's own venv first, then the
/// bare PATH names the OS may provide (`python` on Windows; `python3`,
/// `python` elsewhere - Debian/Kali have no `python` alias).
pub fn python_candidates(root: &Path) -> Vec<PathBuf> {
    let win = root.join("venv").join("Scripts").join("python.exe");
    let bin3 = root.join("venv").join("bin").join("python3");
    let bin = root.join("venv").join("bin").join("python");
    // The venv has ONE shape per platform (`Scripts\python.exe` on
    // Windows, `bin/python3` on Unix), so the native guess comes FIRST:
    // listing the Windows exe first made a Unix venv lose to a stray
    // `venv/bin/python` (or to PATH `python` when no venv exists).
    // The other guesses stay: a root can be shared across systems.
    let mut v = if cfg!(windows) {
        vec![win, bin3, bin]
    } else {
        vec![bin3, bin, win]
    };
    if cfg!(windows) {
        v.push(PathBuf::from("python"));
    } else {
        v.push(PathBuf::from("python3"));
        v.push(PathBuf::from("python"));
    }
    v
}

/// `PYTHONPATH` = `<root>/src` prepended to `existing` with the OS's PATH
/// separator (`;` on Windows, `:` on Unix - the same separator .NET's
/// `Path.PathSeparator` used, NOT `MAIN_SEPARATOR`).
pub fn pythonpath(root: &Path, existing: Option<&str>) -> String {
    let src = root.join("src").to_string_lossy().into_owned();
    match existing {
        Some(e) if !e.is_empty() => {
            let sep = if cfg!(windows) { ';' } else { ':' };
            format!("{src}{sep}{e}")
        }
        _ => src,
    }
}

/// Build the engine's `Command`: interpreter resolved as above, cwd =
/// project root, `PYTHONPATH` pointing at the project's `src/`, and
/// exactly the arguments `try_spawn` used to build inline.
pub fn engine_command(root: &Path, port: u16, rotate_token: bool) -> Command {
    let candidates = python_candidates(root);
    // First interpreter that exists on disk wins (venv), else the first
    // bare PATH name (a single component, never an absolute path).
    let program = candidates
        .iter()
        .find(|c| c.is_file())
        .or_else(|| candidates.iter().find(|c| c.components().count() == 1))
        .cloned()
        .unwrap_or_else(|| PathBuf::from(if cfg!(windows) { "python" } else { "python3" }));

    let mut args: Vec<String> = vec![
        "-m".into(),
        "opendrop.main".into(),
        "--headless".into(),
        "--port".into(),
        port.to_string(),
    ];
    // The desktop's Reset button: the only case that changes the token,
    // the QR code and the session code.
    if rotate_token {
        args.push("--rotate-token".into());
    }

    let existing = std::env::var("PYTHONPATH").ok();
    let mut cmd = Command::new(program);
    cmd.args(&args)
        .current_dir(root)
        .env("PYTHONPATH", pythonpath(root, existing.as_deref()));
    #[cfg(windows)]
    {
        // The app is a GUI binary (subsystem windows): on Windows a
        // console child gets its OWN console window - the empty window
        // seen at engine boot. CREATE_NO_WINDOW keeps the stdout/stderr
        // pipes working and only suppresses that window.
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
    }
    cmd
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::time::{SystemTime, UNIX_EPOCH};

    /// Fresh, empty temp dir (unique per test invocation).
    fn fresh(label: &str) -> PathBuf {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let dir = std::env::temp_dir().join(format!(
            "opendrop-spawn-{}-{}-{}",
            std::process::id(),
            label,
            nanos
        ));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn root_found_by_walking_up_for_pyproject() {
        let a = fresh("walk");
        let c = a.join("a").join("b").join("c");
        fs::create_dir_all(&c).unwrap();
        fs::write(a.join("pyproject.toml"), "[project]\nname = \"opendrop\"\n").unwrap();
        assert_eq!(project_root_from(&c), a);
    }

    #[test]
    fn root_falls_back_to_start_when_no_pyproject() {
        let start = fresh("noroot");
        assert_eq!(project_root_from(&start), start);
    }

    #[cfg(windows)]
    #[test]
    fn candidates_prefer_installed_venv_windows() {
        let root = fresh("venvwin");
        let venv_py = root.join("venv").join("Scripts").join("python.exe");
        fs::create_dir_all(venv_py.parent().unwrap()).unwrap();
        fs::write(&venv_py, b"fake interpreter").unwrap();

        let c = python_candidates(&root);
        assert_eq!(c[0], venv_py);
        // and the resolution really picks it over PATH `python`
        assert_eq!(
            engine_command(&root, 9090, false).get_program(),
            venv_py.as_os_str()
        );
    }

    #[cfg(unix)]
    #[test]
    fn candidates_prefer_venv_python3_on_unix() {
        let root = fresh("venvunix");
        let venv_py = root.join("venv").join("bin").join("python3");
        fs::create_dir_all(venv_py.parent().unwrap()).unwrap();
        fs::write(&venv_py, b"#!/bin/sh\n").unwrap();

        assert_eq!(python_candidates(&root)[0], venv_py);
        assert_eq!(
            engine_command(&root, 8080, false).get_program(),
            venv_py.as_os_str()
        );
    }

    #[test]
    fn candidates_fall_back_to_path_names() {
        let root = fresh("pathnames");
        let c = python_candidates(&root);
        // three venv guesses first, bare PATH names at the tail
        assert_eq!(c.len(), if cfg!(windows) { 4 } else { 5 });
        let tail = &c[3..];
        assert!(tail.iter().all(|p| p.components().count() == 1));
        if cfg!(windows) {
            assert_eq!(tail, [PathBuf::from("python")]);
        } else {
            assert_eq!(tail, [PathBuf::from("python3"), PathBuf::from("python")]);
        }
        // empty root: nothing on disk, so the bare name is used
        assert_eq!(
            engine_command(&root, 8080, false).get_program(),
            PathBuf::from(if cfg!(windows) { "python" } else { "python3" }).as_os_str()
        );
    }

    #[test]
    fn pypath_prepends_project_src() {
        let root = fresh("pypath");
        let src = root.join("src");

        // with an existing value: `<src>` + PATH separator + `X`
        let got = pythonpath(&root, Some("X"));
        let expected = std::env::join_paths([src.as_os_str(), std::ffi::OsStr::new("X")]).unwrap();
        assert_eq!(got, expected.to_string_lossy());

        // without (or with an empty) value: just the project's src
        assert_eq!(pythonpath(&root, None), src.to_string_lossy());
        assert_eq!(pythonpath(&root, Some("")), src.to_string_lossy());
    }

    #[test]
    fn engine_command_carries_args_and_cwd() {
        let root = fresh("args");
        let cmd = engine_command(&root, 9090, true);

        let args: Vec<String> = cmd
            .get_args()
            .map(|a| a.to_string_lossy().into_owned())
            .collect();
        assert_eq!(
            args,
            [
                "-m",
                "opendrop.main",
                "--headless",
                "--port",
                "9090",
                "--rotate-token"
            ]
        );

        assert_eq!(cmd.get_current_dir(), Some(root.as_path()));

        // PYTHONPATH is set explicitly and leads with the project's src
        let pp = cmd
            .get_envs()
            .find(|(k, _)| *k == std::ffi::OsStr::new("PYTHONPATH"))
            .and_then(|(_, v)| v)
            .map(|v| v.to_string_lossy().into_owned())
            .expect("PYTHONPATH must be set");
        assert!(pp.starts_with(&*root.join("src").to_string_lossy()));

        // without rotation the flag must be absent
        let no_rotate: Vec<String> = engine_command(&root, 9090, false)
            .get_args()
            .map(|a| a.to_string_lossy().into_owned())
            .collect();
        assert!(!no_rotate.iter().any(|a| a == "--rotate-token"));
    }
}
