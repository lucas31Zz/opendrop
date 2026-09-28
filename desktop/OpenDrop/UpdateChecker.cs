using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text.Json;
using System.Xml.Linq;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Input;
using Avalonia.Layout;
using Avalonia.Media;
using Avalonia.Threading;

namespace OpenDrop;

// Update check for Windows: reads update.xml from the public repository and
// compares it with the assembly version. The manifest carries the payload zip
// (files + SHA-256), which is extracted and copied over the application
// folder by a worker started from the staged copy: the application restarts
// on the new files, nothing is installed again. %LOCALAPPDATA% (config,
// session, certs, moves) and the receive / share folders are never touched.
// When the manifest has no payload (older release) the full setup is
// downloaded and launched, as before.
internal static class UpdateChecker
{
    private static string ManifestUrl =>
        Environment.GetEnvironmentVariable("OPENDROP_UPDATE_URL")
        ?? "https://raw.githubusercontent.com/lucas31Zz/opendrop/main/update.xml";

    private const int BufferSize = 81920;

    private enum Result { Ok, Cancelled, Failed }

    // ResponseHeadersRead: the body is streamed to disk instead of being
    // buffered in memory, which also lets us report the progress.
    // Release assets are served with a 302 to release-assets.githubusercontent.com,
    // so redirects must be followed or every download would fail on the 302.
    private static readonly HttpClient _http = new(new HttpClientHandler
    {
        UseProxy = false,
        AllowAutoRedirect = true
    })
    { Timeout = Timeout.InfiniteTimeSpan };

    // The startup check runs once, even if the window is hidden to the tray
    // and shown again later.
    private static bool _startupChecked;

    // Called once at startup (Windows only), unless disabled in config.
    public static async void CheckAsync(object owner)
    {
        if (_startupChecked) return;
        _startupChecked = true;
        if (!UpdatesEnabled()) return;
        await RunAsync(owner, manual: false);
    }

    // Manual check from Settings: always reports the outcome.
    public static Task CheckManualAsync(object owner) => RunAsync(owner, manual: true);

    // "check_updates": false in config.json disables the startup check only;
    // the Settings button keeps working.
    private static bool UpdatesEnabled()
    {
        try
        {
            var path = QuotaUsage.ConfigPath;
            if (File.Exists(path))
            {
                using var doc = JsonDocument.Parse(File.ReadAllText(path));
                if (doc.RootElement.TryGetProperty("check_updates", out var value) &&
                    value.ValueKind == JsonValueKind.False)
                    return false;
            }
        }
        catch { }
        return true;
    }

    private static async Task RunAsync(object owner, bool manual)
    {
        if (owner is not Window w) return;

        Version current = new(0, 0, 0);
        string latest = "";
        string setupUrl = "";
        string? expectedHash = null;
        string? zipUrl = null;
        string? zipHash = null;

        try
        {
            using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(15));
            var xml = await _http.GetStringAsync(ManifestUrl, cts.Token);
            var root = XDocument.Parse(xml).Root;
            if (root == null) return;

            latest = root.Element("version")?.Value?.Trim() ?? "";
            setupUrl = root.Element("url")?.Value?.Trim() ?? "";
            expectedHash = root.Element("sha256")?.Value?.Trim();
            zipUrl = root.Element("zip")?.Value?.Trim();
            zipHash = root.Element("zip_sha256")?.Value?.Trim();
            if (latest.Length == 0 || setupUrl.Length == 0) return;

            var assembly = typeof(UpdateChecker).Assembly.GetName().Version;
            if (assembly == null) return;
            current = assembly;

            if (!Version.TryParse(latest, out var latestVer)) return;

            if (latestVer <= current)
            {
                if (manual)
                    await Msg.ShowAsync(w,
                        Lang.Format("Update.UpToDate", FormatVersion(current)),
                        Lang.T("Update.Title"));
                return;
            }
        }
        catch
        {
            if (manual)
                await Msg.ShowAsync(w, Lang.T("Update.Failed"), Lang.T("Update.Title"));
            return;
        }

        // Defer until the owner window is shown.
        if (w.IsVisible)
            Show();
        else
            w.Opened += (_, _) => Show();
        return;

        async void Show()
        {
            var answer = await Msg.ConfirmAsync(w,
                Lang.Format("Update.Available", FormatVersion(current), latest),
                Lang.T("Update.Title"));
            if (!answer) return;

            // A payload zip means a real update (files replaced in place, then
            // a restart). Without it the manifest only offers the setup, which
            // is what older releases do.
            var files = !string.IsNullOrEmpty(zipUrl);
            var work = Path.Combine(Path.GetTempPath(), "OpenDrop-update", latest);
            var dest = files
                ? Path.Combine(work, $"OpenDrop-{latest}-win-x64.zip")
                : SetupPath(latest);

            if (files)
            {
                try { Directory.CreateDirectory(work); }
                catch
                {
                    files = false;
                    dest = SetupPath(latest);
                }
            }

            var url = files ? zipUrl! : setupUrl;
            var hash = files ? zipHash : expectedHash;

            var dialog = new DownloadDialog(latest);
            dialog.Show();
            var result = await DownloadAndVerifyAsync(url, dest, hash, dialog, dialog.Token);

            if (result == Result.Cancelled)
            {
                SafeClose(dialog);
                return;
            }
            if (result != Result.Ok)
            {
                SafeClose(dialog);
                await Msg.ShowAsync(w, Lang.T("Update.Failed"), Lang.T("Update.Title"));
                return;
            }

            if (!files)
            {
                SafeClose(dialog);
                try
                {
                    // The installer detects the running app (CloseApplications=yes)
                    // and closes it itself.
                    Process.Start(new ProcessStartInfo(dest) { UseShellExecute = true });
                }
                catch
                {
                    Process.Start(new ProcessStartInfo(setupUrl) { UseShellExecute = true });
                }
                return;
            }

            // Real update: unpack next to this application, hand the copy work
            // over to the staged binary and leave. The dialog is closed right
            // before the quit: a window left open would keep this process
            // alive, and the worker waits for the process to disappear.
            dialog.ShowApplying();
            string payload;
            try
            {
                var stage = Path.Combine(work, "stage");
                await Task.Run(() =>
                {
                    if (Directory.Exists(stage)) Directory.Delete(stage, recursive: true);
                    ZipFile.ExtractToDirectory(dest, stage, overwriteFiles: true);
                });

                payload = FindPayloadRoot(stage)
                    ?? throw new FileNotFoundException("payload not found");
            }
            catch
            {
                SafeClose(dialog);
                await Msg.ShowAsync(w, Lang.T("Update.Failed"), Lang.T("Update.Title"));
                return;
            }

            try
            {
                StartWorker(payload, work, Environment.ProcessId);
            }
            catch
            {
                // The elevation prompt was declined (or the staged copy could
                // not run): this application is still the running one, so
                // only the update is lost.
                SafeClose(dialog);
                await Msg.ShowAsync(w, Lang.T("Update.NeedsPermission"), Lang.T("Update.Title"));
                return;
            }

            // The worker waits for this process, copies the files and starts
            // the application again. Every window has to go first: a progress
            // dialog left open would keep the process (and the worker) alive.
            SafeClose(dialog);
            if (owner is MainWindow main) main.QuitForUpdate();
            else if (Application.Current?.ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop)
                desktop.Shutdown();
        }
    }

    private static string SetupPath(string version)
        => Path.Combine(Path.GetTempPath(), $"OpenDrop-{version}-win-x64-setup.exe");

    // The staged copy runs the update: it is not the file being replaced,
    // so the running image can always be overwritten. Program Files needs
    // administrator rights, everything else runs without prompting.
    private static void StartWorker(string payload, string work, int ownerPid)
    {
        var worker = Path.Combine(payload, "OpenDrop.exe");
        if (!File.Exists(worker))
            throw new FileNotFoundException("worker not found");

        var appDir = AppContext.BaseDirectory.TrimEnd(
            Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);

        var psi = new ProcessStartInfo(worker) { UseShellExecute = true };
        psi.ArgumentList.Add("--apply-update");
        psi.ArgumentList.Add(payload);
        psi.ArgumentList.Add(appDir);
        psi.ArgumentList.Add(work);
        psi.ArgumentList.Add(ownerPid.ToString());
        if (!IsWritable(appDir)) psi.Verb = "RunAs";
        Process.Start(psi);
    }

    // First directory of the payload that actually holds the application.
    private static string? FindPayloadRoot(string stage)
    {
        if (File.Exists(Path.Combine(stage, "OpenDrop.exe"))) return stage;
        foreach (var dir in Directory.EnumerateDirectories(stage))
        {
            if (File.Exists(Path.Combine(dir, "OpenDrop.exe"))) return dir;
        }
        foreach (var dir in Directory.EnumerateDirectories(stage, "*", SearchOption.AllDirectories))
        {
            if (File.Exists(Path.Combine(dir, "OpenDrop.exe"))) return dir;
        }
        return null;
    }

    private static bool IsWritable(string dir)
    {
        try
        {
            var probe = Path.Combine(dir, ".update-probe-" + Guid.NewGuid().ToString("N"));
            File.WriteAllText(probe, "1");
            File.Delete(probe);
            return true;
        }
        catch { return false; }
    }

    private static string FormatVersion(Version version)
        => version.Build >= 0 ? $"{version.Major}.{version.Minor}.{version.Build}" : version.ToString();

    // Closing from the download task: the window may not be visible yet.
    private static void SafeClose(Window window)
    {
        if (window.IsVisible)
            window.Close();
        else
            window.Opened += (_, _) => window.Close();
    }

    private static async Task<Result> DownloadAndVerifyAsync(
        string setupUrl, string dest, string? expectedHash,
        DownloadDialog? dialog, CancellationToken ct)
    {
        try
        {
            using var response = await _http.GetAsync(
                setupUrl, HttpCompletionOption.ResponseHeadersRead, ct);
            response.EnsureSuccessStatusCode();

            var total = response.Content.Headers.ContentLength ?? -1;
            await using (var input = await response.Content.ReadAsStreamAsync(ct))
            await using (var output = new FileStream(dest, FileMode.Create, FileAccess.Write,
                               FileShare.None, BufferSize, useAsync: true))
            {
                var buffer = new byte[BufferSize];
                long received = 0;
                int read;
                while ((read = await input.ReadAsync(buffer.AsMemory(), ct)) > 0)
                {
                    await output.WriteAsync(buffer.AsMemory(0, read), ct);
                    received += read;
                    dialog?.Report(received, total);
                }
            }
        }
        catch (OperationCanceledException)
        {
            TryDelete(dest);
            return Result.Cancelled;
        }
        catch
        {
            TryDelete(dest);
            return Result.Failed;
        }

        if (string.IsNullOrEmpty(expectedHash))
            return Result.Ok;

        try
        {
            dialog?.ShowVerifying();
            var hash = await Task.Run(() =>
            {
                using var fs = File.OpenRead(dest);
                return Convert.ToHexString(SHA256.HashData(fs));
            }, ct);

            if (!string.Equals(hash, expectedHash, StringComparison.OrdinalIgnoreCase))
            {
                TryDelete(dest);
                return Result.Failed;
            }
        }
        catch (OperationCanceledException)
        {
            TryDelete(dest);
            return Result.Cancelled;
        }
        catch
        {
            TryDelete(dest);
            return Result.Failed;
        }

        return Result.Ok;
    }

    private static void TryDelete(string path)
    {
        try { if (File.Exists(path)) File.Delete(path); } catch { }
    }

    // Download progress window (no XAML: built like Msg, same dark style).
    private sealed class DownloadDialog : Window
    {
        private readonly CancellationTokenSource _cts = new();
        private readonly TextBlock _status = new()
        {
            FontSize = 13,
            Foreground = new SolidColorBrush(Color.FromRgb(0xcc, 0xcc, 0xcc)),
            TextWrapping = TextWrapping.Wrap
        };
        private readonly ProgressBar _bar = new()
        {
            Minimum = 0,
            Maximum = 100,
            Height = 8,
            Margin = new Thickness(0, 8, 0, 0)
        };

        public CancellationToken Token => _cts.Token;

        public DownloadDialog(string version)
        {
            Title = Lang.T("Update.Title");
            SizeToContent = SizeToContent.WidthAndHeight;
            CanResize = false;
            Width = 420;
            MinWidth = 320;
            WindowStartupLocation = WindowStartupLocation.CenterScreen;
            Background = new SolidColorBrush(Color.FromRgb(0x0f, 0x0f, 0x0f));

            _status.Text = Lang.Format("Update.Downloading", version);

            var cancel = new Button
            {
                Content = Lang.T("Msg.Cancel"),
                MinWidth = 90,
                HorizontalAlignment = HorizontalAlignment.Right,
                Background = new SolidColorBrush(Color.FromRgb(0x2a, 0x2a, 0x2a)),
                Foreground = new SolidColorBrush(Color.FromRgb(0xe0, 0xe0, 0xe0)),
                FontSize = 13,
                Padding = new Thickness(14, 8),
                BorderThickness = new Thickness(0),
                CornerRadius = new CornerRadius(6),
                Margin = new Thickness(8, 8, 0, 0),
                Cursor = new Cursor(StandardCursorType.Hand)
            };
            cancel.Click += (_, _) => _cts.Cancel();

            var buttons = new StackPanel
            {
                Orientation = Orientation.Horizontal,
                HorizontalAlignment = HorizontalAlignment.Right,
                Children = { cancel }
            };

            Content = new StackPanel
            {
                Margin = new Thickness(20),
                Width = 380,
                Children = { _status, _bar, buttons }
            };
        }

        // The download loop resumes on the UI thread, but never assume it:
        // touching a control from another thread would throw.
        public void Report(long received, long total)
        {
            if (!Dispatcher.UIThread.CheckAccess())
            {
                Dispatcher.UIThread.Post(() => Report(received, total));
                return;
            }

            if (total > 0)
            {
                _bar.IsIndeterminate = false;
                _bar.Value = received * 100.0 / total;
                _status.Text = $"{_bar.Value:0} %  {QuotaUsage.Format(received)} / {QuotaUsage.Format(total)}";
            }
            else
            {
                _bar.IsIndeterminate = true;
                _status.Text = QuotaUsage.Format(received);
            }
        }

        public void ShowVerifying()
        {
            if (!Dispatcher.UIThread.CheckAccess())
            {
                Dispatcher.UIThread.Post(ShowVerifying);
                return;
            }

            _bar.IsIndeterminate = true;
            _status.Text = Lang.T("Update.Verifying");
        }

        public void ShowApplying()
        {
            if (!Dispatcher.UIThread.CheckAccess())
            {
                Dispatcher.UIThread.Post(ShowApplying);
                return;
            }

            _bar.IsIndeterminate = true;
            _status.Text = Lang.T("Update.Applying");
        }
    }
}
