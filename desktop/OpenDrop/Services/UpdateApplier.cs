using System;
using System.Diagnostics;
using System.IO;

namespace OpenDrop;

// The second half of an update, started from the freshly downloaded payload
// (never from the installed copy, which is the file being replaced):
//
//   1. wait until the running instance is gone,
//   2. copy the payload over the application folder (retries, then best
//      effort for the secondary files),
//   3. reinstall the Python dependencies only when requirements.txt changed,
//   4. start the application again and drop the staging folder.
//
// Nothing outside the application folder is written: configuration,
// session, certificates, the moved-files registry and the receive / share
// folders all stay where they are.
internal static class UpdateApplier
{
    private const int Retries = 3;

    public static int Run(string payload, string appDir, string work, string ownerPidText)
    {
        // The application is gone either way after this point: every failure
        // path still starts it again, an update must never leave the machine
        // without a running application.
        if (!int.TryParse(ownerPidText, out var ownerPid)) return 2;
        if (!WaitForExit(ownerPid)) { CleanupLater(work); return 3; }

        var code = 0;
        try
        {
            var requirements = Path.Combine(appDir, "requirements.txt");
            var before = Hash(requirements);

            if (!CopyPayload(payload, appDir)) code = 4;

            var after = Hash(requirements);
            if (code == 0 && before.Length > 0 && after.Length > 0 && !string.Equals(before, after, StringComparison.OrdinalIgnoreCase))
                RefreshDependencies(appDir);
        }
        catch
        {
            code = 1;
        }

        try
        {
            Relaunch(appDir);
        }
        catch { }

        CleanupLater(work);
        return code;
    }

    // An elevated worker (Program Files) must not pass its rights on: the
    // application itself runs without administrator rights, so it is started
    // through the shell of the logged-in user when this process is elevated.
    private static void Relaunch(string appDir)
    {
        var exe = Path.Combine(appDir, "OpenDrop.exe");
        if (!File.Exists(exe)) return;

        if (IsElevated())
        {
            try
            {
                Process.Start(new ProcessStartInfo("explorer.exe", $"\"{exe}\"") { UseShellExecute = true });
                return;
            }
            catch { }
        }

        Process.Start(new ProcessStartInfo(exe) { UseShellExecute = true });
    }

    private static bool IsElevated()
    {
        try
        {
            using var identity = System.Security.Principal.WindowsIdentity.GetCurrent();
            return new System.Security.Principal.WindowsPrincipal(identity)
                .IsInRole(System.Security.Principal.WindowsBuiltInRole.Administrator);
        }
        catch { return false; }
    }

    // The staging folder holds this very binary: it can only be deleted once
    // the process is gone, hence the detached helper with a delay.
    private static void CleanupLater(string work)
    {
        if (string.IsNullOrWhiteSpace(work) || !Directory.Exists(work)) return;
        try
        {
            var psi = new ProcessStartInfo("powershell.exe")
            {
                UseShellExecute = false,
                CreateNoWindow = true
            };
            psi.ArgumentList.Add("-NoProfile");
            psi.ArgumentList.Add("-Command");
            psi.ArgumentList.Add(
                "Start-Sleep -Seconds 5; " +
                $"Remove-Item -Recurse -Force -LiteralPath '{work.Replace("'", "''")}' " +
                "-ErrorAction SilentlyContinue");
            Process.Start(psi);
        }
        catch { }
    }

    private static bool WaitForExit(int pid)
    {
        for (var attempt = 0; attempt < 120; attempt++)
        {
            try
            {
                using var process = Process.GetProcessById(pid);
                // A recycled pid belongs to another program: gone.
                if (!string.Equals(process.ProcessName, "OpenDrop", StringComparison.OrdinalIgnoreCase))
                    return true;
                if (process.HasExited) return true;
            }
            catch (ArgumentException) { return true; }

            System.Threading.Thread.Sleep(500);
        }
        return false;
    }

    // Returns false only when the application itself could not be written:
    // the update must not be applied halfway.
    private static bool CopyPayload(string payload, string appDir)
    {
        foreach (var source in Directory.EnumerateFiles(payload, "*", SearchOption.AllDirectories))
        {
            var relative = Path.GetRelativePath(payload, source);
            var target = Path.Combine(appDir, relative);
            var essential = string.Equals(relative, "OpenDrop.exe", StringComparison.OrdinalIgnoreCase);

            if (!WriteFile(source, target, essential))
                return false;
        }
        return true;
    }

    private static bool WriteFile(string source, string target, bool essential)
    {
        var directory = Path.GetDirectoryName(target);
        if (!string.IsNullOrEmpty(directory)) Directory.CreateDirectory(directory);

        for (var attempt = 1; attempt <= Retries; attempt++)
        {
            try
            {
                File.Copy(source, target, overwrite: true);
                return true;
            }
            catch when (attempt < Retries)
            {
                // A leftover child process or the antivirus can hold a file
                // for a moment: give it a chance to let go.
                System.Threading.Thread.Sleep(500);
            }
            catch
            {
                if (essential) return false;
                return true;   // keep going, the file may not be in use
            }
        }
        return !essential;
    }

    // Offline, from the wheels shipped with the application (same script the
    // installer uses). Only reached when requirements.txt changed.
    private static void RefreshDependencies(string appDir)
    {
        var script = Path.Combine(appDir, "install-deps.ps1");
        var wheels = Path.Combine(appDir, "wheels");
        var requirements = Path.Combine(appDir, "requirements.txt");
        if (!File.Exists(script) || !Directory.Exists(wheels) || !File.Exists(requirements)) return;

        try
        {
            var psi = new ProcessStartInfo("powershell.exe")
            {
                UseShellExecute = false,
                CreateNoWindow = true,
                WorkingDirectory = appDir
            };
            psi.ArgumentList.Add("-NoProfile");
            psi.ArgumentList.Add("-ExecutionPolicy");
            psi.ArgumentList.Add("Bypass");
            psi.ArgumentList.Add("-File");
            psi.ArgumentList.Add(script);
            psi.ArgumentList.Add("-WheelDir");
            psi.ArgumentList.Add(wheels);
            psi.ArgumentList.Add("-VenvDir");
            psi.ArgumentList.Add(Path.Combine(appDir, "venv"));
            psi.ArgumentList.Add("-Requirements");
            psi.ArgumentList.Add(requirements);

            using var process = Process.Start(psi);
            process?.WaitForExit(120_000);
        }
        catch { }
    }

    private static string Hash(string path)
    {
        try { return File.Exists(path) ? Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(File.ReadAllBytes(path))) : ""; }
        catch { return ""; }
    }
}
