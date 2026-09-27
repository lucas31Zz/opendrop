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

        // Un ancien serveur peut survivre a la fermeture de l'app (crash,
        // arret force) : sans cela, il garde le port et sert un token et un
        // code differents de ceux affiches ici.
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
                    Message = "Impossible de trouver le projet OpenDrop."
                });
                return false;
            }

            var startInfo = new ProcessStartInfo
            {
                FileName = "python",
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

            _process = Process.Start(startInfo);
            if (_process == null)
            {
                OnStatusChanged?.Invoke(this, new ServerStatus
                {
                    State = "error",
                    Message = "Echec du lancement de Python."
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
                    Message = "Timeout: le serveur n'a pas repondu."
                });
                return false;
            }

            if (_process.HasExited)
            {
                OnStatusChanged?.Invoke(this, new ServerStatus
                {
                    State = "error",
                    Message = "Le serveur Python s'est arrete immediatement."
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
                Message = $"Erreur: {ex.Message}"
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

    private static string PidFilePath => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "OpenDrop", "server.pid");

    private static void WritePidFile(Process process)
    {
        try
        {
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
            // Verifications anti-recyclage de PID : on ne tue que python, et
            // seulement si son heure de demarrage correspond a celle notee.
            if (!stale.ProcessName.Equals("python", StringComparison.OrdinalIgnoreCase))
                return;
            if (recorded != DateTime.MinValue &&
                (stale.StartTime - recorded).Duration() > TimeSpan.FromMinutes(5))
                return;

            stale.Kill(entireProcessTree: true);
            stale.WaitForExit(3000);
        }
        catch (ArgumentException) { /* PID deja mort */ }
        catch (InvalidOperationException) { }
        catch (IOException) { }
        catch { }
    }

    private static string? FindProjectRoot()
    {
        var dir = AppDomain.CurrentDomain.BaseDirectory;

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
