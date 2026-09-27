using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text.Json;

namespace OpenDrop;

public class ServerManager
{
    private Process? _process;
    private readonly ManualResetEventSlim _infoReceived = new(false);

    public string? Port { get; private set; }
    public string? Token { get; private set; }
    public string? SessionCode { get; private set; }
    public string? UrlUpload { get; private set; }
    public string? Ip { get; private set; }
    public string? DownloadDir { get; private set; }
    public string? ShareDir { get; private set; }
    public bool IsRunning => _process != null && !_process.HasExited;

    public event EventHandler<ServerStatus>? OnStatusChanged;

    public class ServerStatus
    {
        public string State { get; set; } = "stopped";
        public string? Address { get; set; }
        public string? QrUrl { get; set; }
        public string? Message { get; set; }
        public string? Token { get; set; }
        public string? SessionCode { get; set; }
    }

    public Task<bool> StartAsync(bool rotateToken = false)
    {
        return Task.Run(() => StartSync(rotateToken));
    }

    public Task<bool> RestartAsync(bool rotateToken = false)
    {
        return Task.Run(() =>
        {
            Stop();
            Thread.Sleep(200);
            return StartSync(rotateToken);
        });
    }

    private bool StartSync(bool rotateToken = false)
    {
        if (IsRunning) return true;

        // An older server can survive an app close (crash, forced stop):
        // without this it keeps the port and serves a token and code
        // different from the ones shown here.
        KillStaleServer();

        _infoReceived.Reset();

        try
        {
            var projectDir = FindProjectRoot();
            if (projectDir == null)
            {
                OnStatusChanged?.Invoke(this, new ServerStatus
                {
                    State = "error",
                    Message = Lang.T("Sm.ProjectNotFound")
                });
                return false;
            }

            var startInfo = new ProcessStartInfo
            {
                Arguments = rotateToken
                    ? "-m opendrop.main --headless --rotate-token"
                    : "-m opendrop.main --headless",
                WorkingDirectory = projectDir,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true
            };

            var srcDir = Path.Combine(projectDir, "src");
            if (Directory.Exists(srcDir))
            {
                var pythonPath = srcDir;
                var existing = Environment.GetEnvironmentVariable("PYTHONPATH");
                if (!string.IsNullOrEmpty(existing))
                    pythonPath = srcDir + Path.PathSeparator + existing;
                startInfo.EnvironmentVariables["PYTHONPATH"] = pythonPath;
            }

            // Python: first the venv created by the installer (repo installed
            // with its wheels, dependencies guaranteed), otherwise
            // python3/python from PATH. On Linux the command is
            // python3 (Debian/Kali have no "python" alias).
            var pythons = new List<string>();
            var venvWin = Path.Combine(projectDir, "venv", "Scripts", "python.exe");
            var venvUnix3 = Path.Combine(projectDir, "venv", "bin", "python3");
            var venvUnix = Path.Combine(projectDir, "venv", "bin", "python");
            if (File.Exists(venvWin)) pythons.Add(venvWin);
            if (File.Exists(venvUnix3)) pythons.Add(venvUnix3);
            if (File.Exists(venvUnix)) pythons.Add(venvUnix);
            if (OperatingSystem.IsWindows())
                pythons.Add("python");
            else
            {
                pythons.Add("python3");
                pythons.Add("python");
            }

            foreach (var py in pythons)
            {
                startInfo.FileName = py;
                try
                {
                    _process = Process.Start(startInfo);
                }
                catch
                {
                    // Executable not found (Win32Exception): try the next one.
                    _process = null;
                }
                if (_process != null)
                    break;
            }

            if (_process == null)
            {
                OnStatusChanged?.Invoke(this, new ServerStatus
                {
                    State = "error",
                    Message = Lang.T("Sm.NoPython")
                });
                return false;
            }

            WritePidFile(_process);

            _process.OutputDataReceived += (_, e) =>
            {
                if (string.IsNullOrEmpty(e.Data)) return;

                if (e.Data.Contains("__opendrop_info__"))
                {
                    try
                    {
                        var jsonStart = e.Data.IndexOf('{');
                        if (jsonStart >= 0)
                        {
                            var jsonStr = e.Data.Substring(jsonStart);
                            var info = JsonSerializer.Deserialize<JsonElement>(jsonStr);

                            Ip = info.GetProperty("ip").GetString();
                            Port = info.GetProperty("port").GetInt32().ToString();
                            Token = info.GetProperty("token").GetString();
                            SessionCode = info.TryGetProperty("session_code", out var scProp)
                                ? scProp.GetString()
                                : null;
                            UrlUpload = info.GetProperty("url_upload").GetString();
                            DownloadDir = info.TryGetProperty("download_dir", out var ddProp) ? ddProp.GetString() : null;
                            ShareDir = info.TryGetProperty("share_dir", out var sdProp) ? sdProp.GetString() : null;

                            _infoReceived.Set();

                            OnStatusChanged?.Invoke(this, new ServerStatus
                            {
                                State = "starting",
                                Address = $"{Ip}:{Port}",
                                Token = Token,
                                SessionCode = SessionCode
                            });
                        }
                    }
                    catch (Exception ex)
                    {
                        Debug.WriteLine($"[OpenDrop] Parse error: {ex.Message}");
                    }
                }
            };
            _process.BeginOutputReadLine();

            _process.ErrorDataReceived += (_, e) =>
            {
                if (e.Data != null)
                {
                    Debug.WriteLine($"[Python STDERR] {e.Data}");
                }
            };
            _process.BeginErrorReadLine();

            if (!_infoReceived.Wait(5000))
            {
                OnStatusChanged?.Invoke(this, new ServerStatus
                {
                    State = "error",
                    Message = Lang.T("Sm.Timeout")
                });
                return false;
            }

            if (_process.HasExited)
            {
                OnStatusChanged?.Invoke(this, new ServerStatus
                {
                    State = "error",
                    Message = Lang.T("Sm.Exited")
                });
                return false;
            }

            return !string.IsNullOrEmpty(Port);
        }
        catch (Exception ex)
        {
            OnStatusChanged?.Invoke(this, new ServerStatus
            {
                State = "error",
                Message = $"{Lang.T("Err.Prefix")} {ex.Message}"
            });
            return false;
        }
    }

    public void Stop()
    {
        if (_process != null && !_process.HasExited)
        {
            try
            {
                _process.Kill(entireProcessTree: true);
                _process.WaitForExit(3000);
            }
            catch { }
        }
        _process?.Dispose();
        _process = null;
        Port = null;
        Token = null;
        SessionCode = null;
        UrlUpload = null;
        Ip = null;
        DownloadDir = null;
        ShareDir = null;
        DeletePidFile();
    }

    private static string PidFilePath => Path.Combine(QuotaUsage.ConfigDir, "server.pid");

    private static void WritePidFile(Process process)
    {
        try
        {
            // The config folder may not exist on first start (the Python
            // server has not created it yet): without this the write
            // fails silently and KillStaleServer does not find the server
            // on the next launch (port already taken).
            Directory.CreateDirectory(QuotaUsage.ConfigDir);
            File.WriteAllText(PidFilePath,
                $"{process.Id}|{process.StartTime.ToString("O", CultureInfo.InvariantCulture)}");
        }
        catch { }
    }

    private static void DeletePidFile()
    {
        try
        {
            if (File.Exists(PidFilePath)) File.Delete(PidFilePath);
        }
        catch { }
    }

    private static void KillStaleServer()
    {
        try
        {
            if (!File.Exists(PidFilePath)) return;

            var parts = File.ReadAllText(PidFilePath).Split('|');
            DeletePidFile();
            if (!int.TryParse(parts[0], out var pid)) return;

            var recorded = DateTime.MinValue;
            if (parts.Length > 1)
            {
                DateTime.TryParse(parts[1], CultureInfo.InvariantCulture,
                    DateTimeStyles.RoundtripKind, out recorded);
            }

            using var stale = Process.GetProcessById(pid);
            // Anti-PID-recycling checks: only kill python (the command is
            // python3 on Linux), and only when its start time matches
            // the recorded one.
            if (!stale.ProcessName.StartsWith("python", StringComparison.OrdinalIgnoreCase))
                return;
            if (recorded != DateTime.MinValue &&
                (stale.StartTime - recorded).Duration() > TimeSpan.FromMinutes(5))
                return;

            stale.Kill(entireProcessTree: true);
            stale.WaitForExit(3000);
        }
        catch (ArgumentException) { /* PID already dead */ }
        catch (InvalidOperationException) { }
        catch (IOException) { }
        catch { }
    }

    private static string? FindProjectRoot()
    {
        // Prefer the real executable folder: with a single-file binary
        // (dotnet publish -p:PublishSingleFile), the temporary extraction
        // folder has no pyproject.toml. The delivered folder must contain
        // pyproject.toml + src/ + web/.
        var dir = Path.GetDirectoryName(Environment.ProcessPath)
                  ?? AppContext.BaseDirectory;

        for (var i = 0; i < 10; i++)
        {
            if (File.Exists(Path.Combine(dir, "pyproject.toml")))
                return dir;
            dir = Path.GetDirectoryName(dir);
            if (dir == null) break;
        }

        return null;
    }
}
