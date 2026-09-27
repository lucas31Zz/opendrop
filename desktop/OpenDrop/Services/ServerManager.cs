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

            // Python : d'abord le venv cree par l'installeur (depot
            // installe avec ses wheels, dependances garanties), sinon
            // python3/python du PATH. Sous Linux la commande s'appelle
            // python3 (Debian/Kali n'ont pas d'alias "python").
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
                    // Executable introuvable (Win32Exception) : on tente le suivant.
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
                    Message = "Python introuvable. Installez Python 3.10+ puis " +
                              "pip install qrcode cryptography."
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

    private static string PidFilePath => Path.Combine(QuotaUsage.ConfigDir, "server.pid");

    private static void WritePidFile(Process process)
    {
        try
        {
            // Le dossier de config peut ne pas exister au 1er lancement (le
            // serveur Python ne l'a pas encore cree) : sans cela, l'ecriture
            // echoue en silence et KillStaleServer ne retrouve pas le serveur
            // au lancement suivant (port deja pris).
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
            // Verifications anti-recyclage de PID : on ne tue que python (la
            // commande s'appelle python3 sous Linux), et seulement si son
            // heure de demarrage correspond a celle notee.
            if (!stale.ProcessName.StartsWith("python", StringComparison.OrdinalIgnoreCase))
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
        // Priorite au dossier reel de l'executable : avec un binaire livre en
        // fichier unique (dotnet publish -p:PublishSingleFile), le dossier
        // temporaire d'extraction ne contient pas pyproject.toml. Le dossier
        // livre doit contenir pyproject.toml + src/ + web/.
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
