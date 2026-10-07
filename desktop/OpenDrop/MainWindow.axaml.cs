using System.Diagnostics;
using System.Text.Json;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Interactivity;
using Avalonia.Media;
using Avalonia.Media.Imaging;
using Avalonia.Platform;
using Avalonia.Platform.Storage;
using Avalonia.Threading;
using QRCoder;

namespace OpenDrop;

// One row of the shared-files list.
internal sealed class ShareFile
{
    public string Name { get; }
    public string Size { get; }
    public string FullPath { get; }

    // Where the file came from when the user moved it here; null when the
    // file was added by copy or by another tool.
    public string? Origin { get; }

    public bool CanPutBack => !string.IsNullOrEmpty(Origin);

    public ShareFile(string name, string size, string fullPath, string? origin = null)
    {
        Name = name;
        Size = size;
        FullPath = fullPath;
        Origin = origin;
    }
}

public partial class MainWindow : Window
{
    private readonly ServerManager _serverManager;
    private readonly DispatcherTimer _pollTimer;
    private readonly DispatcherTimer _tokenTimer;
    private readonly DispatcherTimer _quotaTimer;
    private bool _quotaBusy;
    private readonly HttpClient _http;
    private bool _isRunning;
    private int _tokenSecondsLeft;
    private int _tokenIntervalSeconds;

    private const string DiscordInviteUrl = "https://discord.gg/vREBPZuvhV";

    // Tray (Windows): closing the window hides it, the server keeps running.
    private TrayIcon? _trayIcon;
    private NativeMenuItem? _trayShow;
    private NativeMenuItem? _trayQuit;
    private bool _forceClose;

    private List<ShareFile> _shareFiles = new();

    public MainWindow()
    {
        InitializeComponent();
        // The service keeps itself alive through the window events.
        _ = GlowService.Attach(this, GlowLayer);
        var handler = new HttpClientHandler();
        // OpenDrop self-signed certificate: accepted only on the local
        // loopback (info poll), never for LAN traffic.
        handler.ServerCertificateCustomValidationCallback = (message, _, _, _) =>
        {
            var host = message?.RequestUri?.Host;
            return host == "127.0.0.1" || host == "::1" || host == "localhost";
        };
        _http = new HttpClient(handler) { Timeout = TimeSpan.FromSeconds(3) };
        _serverManager = new ServerManager();

        _serverManager.OnStatusChanged += (_, status) =>
        {
            Dispatcher.UIThread.Invoke(() => OnServerStatusChanged(status));
        };

        _pollTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(2) };
        _pollTimer.Tick += async (_, _) => await PollServerAsync();

        _tokenTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(1) };
        _tokenTimer.Tick += (_, _) => OnTokenTick();

        _quotaTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(3) };
        _quotaTimer.Tick += async (_, _) => await RefreshQuotaAsync();

        TokenIntervalCombo.SelectionChanged += (_, _) => OnTokenIntervalChanged();

        SetupTray();
        Lang.Changed += ApplyTrayStrings;

        // With a tray icon the close button hides the window instead of
        // stopping the server; the server only stops when really quitting.
        Closing += (_, e) =>
        {
            if (_forceClose || _trayIcon == null) return;
            e.Cancel = true;
            Hide();
        };

        Closed += (_, _) =>
        {
            _pollTimer.Stop();
            _tokenTimer.Stop();
            _quotaTimer.Stop();
            _serverManager.Stop();
            _http.Dispose();
            Lang.Changed -= ApplyTrayStrings;
            if (_trayIcon != null)
            {
                RemoveTrayIcon(_trayIcon);
                _trayIcon.Dispose();
                _trayIcon = null;
            }
        };

        // The share folder can change outside the app (another tool): a
        // refresh when the window regains focus is enough and keeps the
        // current selection untouched while working.
        Activated += (_, _) => RefreshFiles();

        Opened += async (_, _) =>
        {
            _quotaTimer.Start();
            await RefreshQuotaAsync();
            RefreshFiles();

            var started = await _serverManager.StartAsync();
            if (started)
            {
                _pollTimer.Start();
                RefreshFiles();
            }
            else
            {
                UpdateUI("error", Lang.T("Err.CannotStart"));
            }

            _ = CheckForUpdatesOnStartupAsync();
        };
    }

    // Update check, started once the window and the server have settled:
    // a dialog popping up over a half-started application is worse than
    // waiting three seconds. Anything unexpected (offline, API change,
    // rate limit) stays silent here - Settings gives the feedback.
    private async Task CheckForUpdatesOnStartupAsync()
    {
        await Task.Delay(TimeSpan.FromSeconds(3));
        try
        {
            // A silent install runs after this process is gone, so its
            // outcome can only be reported here. The update itself is not
            // offered again right away: the message says where to retry.
            var failure = UpdateService.ConsumeInstallStatus();
            if (failure != null)
            {
                await Msg.ShowAsync(this, failure, Lang.T("Update.Title"));
                return;
            }

            await UpdateRunner.RunAsync(this, interactive: false);
        }
        catch (Exception)
        {
            // The updater never gets in the way of the transfer itself.
        }
    }

    // Used by the updater: quit for real, even with a tray icon where the
    // close button would otherwise only hide the window.
    public void ForceCloseForUpdate()
    {
        _forceClose = true;
        Close();
    }

    #region Tray

    private void SetupTray()
    {
        if (!OperatingSystem.IsWindows()) return;

        try
        {
            _trayShow = new NativeMenuItem(Lang.T("Tray.Show"));
            _trayShow.Click += (_, _) => ShowFromTray();

            _trayQuit = new NativeMenuItem(Lang.T("Tray.Quit"));
            _trayQuit.Click += (_, _) => Quit();

            var menu = new NativeMenu();
            menu.Items.Add(_trayShow);
            menu.Items.Add(new NativeMenuItemSeparator());
            menu.Items.Add(_trayQuit);

            using var stream = AssetLoader.Open(new Uri("avares://OpenDrop/app.ico"));
            _trayIcon = new TrayIcon
            {
                Icon = new WindowIcon(stream),
                ToolTipText = "OpenDrop",
                Menu = menu
            };
            _trayIcon.Clicked += (_, _) => ShowFromTray();
            AddTrayIcon(_trayIcon);
        }
        catch
        {
            _trayIcon = null;
        }
    }

    private void ApplyTrayStrings()
    {
        if (_trayShow != null) _trayShow.Header = Lang.T("Tray.Show");
        if (_trayQuit != null) _trayQuit.Header = Lang.T("Tray.Quit");
    }

    internal void ShowFromTray()
    {
        Show();
        if (WindowState == WindowState.Minimized)
            WindowState = WindowState.Normal;
        Activate();
    }

    private void Quit()
    {
        _forceClose = true;
        Close();
    }

    // TrayIcon.TrayIcons is an attached property on the application.
    private static void AddTrayIcon(TrayIcon icon)
    {
        var app = Application.Current;
        if (app == null) return;

        var icons = TrayIcon.GetIcons(app);
        if (icons == null)
        {
            icons = new TrayIcons();
            TrayIcon.SetIcons(app, icons);
        }
        icons.Add(icon);
    }

    private static void RemoveTrayIcon(TrayIcon icon)
    {
        var app = Application.Current;
        if (app == null) return;
        TrayIcon.GetIcons(app)?.Remove(icon);
    }

    #endregion

    #region Shared files

    private string? ResolveShareDir()
    {
        // The running server knows the path it actually serves; fall back
        // on config.json when it is stopped.
        var dir = _serverManager.ShareDir;
        if (string.IsNullOrWhiteSpace(dir))
            dir = QuotaUsage.ReadShareDir(null);
        return string.IsNullOrWhiteSpace(dir) ? null : dir;
    }

    private void RefreshFiles()
    {
        try
        {
            var dir = ResolveShareDir();
            FilesPathText.Text = dir ?? "---";
            FilesHint.IsVisible = false;

            var files = new List<ShareFile>();
            if (dir != null && Directory.Exists(dir))
            {
                var origins = MoveRegistry.Load();
                foreach (var path in Directory.EnumerateFiles(dir))
                {
                    try
                    {
                        var info = new FileInfo(path);
                        origins.TryGetValue(info.FullName, out var origin);
                        files.Add(new ShareFile(info.Name, QuotaUsage.Format(info.Length),
                            info.FullName, origin));
                    }
                    catch { }
                }
                files.Sort((a, b) =>
                    string.Compare(a.Name, b.Name, StringComparison.OrdinalIgnoreCase));
            }
            else if (dir != null)
            {
                FilesHint.Text = Lang.T("Files.MissingFolder");
                FilesHint.IsVisible = true;
            }

            _shareFiles = files;
            FileList.ItemsSource = _shareFiles;
            FilesEmpty.IsVisible = files.Count == 0;
        }
        catch { }
    }

    private List<ShareFile> SelectedFiles()
    {
        var picked = new List<ShareFile>();
        var selection = FileList.SelectedItems;
        if (selection == null) return picked;
        foreach (var item in selection)
        {
            if (item is ShareFile file)
                picked.Add(file);
        }
        return picked;
    }

    private async void BtnRefreshFiles_Click(object? sender, RoutedEventArgs e)
    {
        RefreshFiles();
        await Task.CompletedTask;
    }

    private async void BtnRename_Click(object? sender, RoutedEventArgs e)
        => await RenameSelectedAsync();

    // Double click opens the file with the system default application;
    // renaming stays on the Rename button.
    private async void FileList_DoubleTapped(object? sender, RoutedEventArgs e)
    {
        if (FileList.SelectedItem is not ShareFile file) return;

        if (!File.Exists(file.FullPath))
        {
            await Msg.ShowAsync(this, Lang.T("Files.NotFound"), Lang.T("Label.SharedFiles"));
            RefreshFiles();
            return;
        }

        try
        {
            Process.Start(new ProcessStartInfo(file.FullPath) { UseShellExecute = true });
        }
        catch (Exception ex)
        {
            await Msg.ShowAsync(this,
                $"{Lang.T("Err.Prefix")} {ex.Message}", Lang.T("Label.SharedFiles"));
        }
    }

    // Returns a file that was moved into the share folder to where it came
    // from; the entry is dropped so the button disappears with the file.
    private async void BtnPutBack_Click(object? sender, RoutedEventArgs e)
    {
        if (sender is not Control { Tag: ShareFile file } || !file.CanPutBack) return;

        var origin = file.Origin!;
        var answer = await Msg.ConfirmAsync(this,
            Lang.Format("Files.PutBackConfirm", file.Name, origin),
            Lang.T("Files.PutBackTitle"));
        if (!answer) return;

        try
        {
            var target = origin;
            var parent = Path.GetDirectoryName(target);
            if (!string.IsNullOrEmpty(parent) && !Directory.Exists(parent))
                Directory.CreateDirectory(parent);

            // Never overwrite a file that came back in the meantime.
            target = UniquePath(target);
            File.Move(file.FullPath, target);
            MoveRegistry.Forget(file.FullPath);
        }
        catch (Exception ex)
        {
            await Msg.ShowAsync(this,
                $"{Lang.T("Err.Prefix")} {ex.Message}", Lang.T("Files.PutBackTitle"));
        }

        RefreshFiles();
    }

    private async void BtnOpenReceived_Click(object? sender, RoutedEventArgs e)
        => await OpenFolderAsync(QuotaUsage.ReadDownloadDir(_serverManager.DownloadDir));

    private async void BtnOpenShared_Click(object? sender, RoutedEventArgs e)
        => await OpenFolderAsync(ResolveShareDir());

    private async Task OpenFolderAsync(string? dir)
    {
        if (string.IsNullOrWhiteSpace(dir) || !Directory.Exists(dir))
        {
            await Msg.ShowAsync(this,
                Lang.Format("Folders.Missing", dir ?? "---"), Lang.T("Label.Folders"));
            return;
        }

        try
        {
            Process.Start(new ProcessStartInfo(dir) { UseShellExecute = true });
        }
        catch (Exception ex)
        {
            await Msg.ShowAsync(this,
                $"{Lang.T("Err.Prefix")} {ex.Message}", Lang.T("Label.Folders"));
        }
    }

    private async void BtnDiscord_Click(object? sender, RoutedEventArgs e)
    {
        try
        {
            Process.Start(new ProcessStartInfo(DiscordInviteUrl) { UseShellExecute = true });
        }
        catch (Exception ex)
        {
            await Msg.ShowAsync(this,
                $"{Lang.T("Err.Prefix")} {ex.Message}", Lang.T("Btn.Discord"));
        }
    }

    private async Task RenameSelectedAsync()
    {
        var selection = SelectedFiles();
        if (selection.Count != 1)
        {
            await Msg.ShowAsync(this, Lang.T("Files.SelectOne"), Lang.T("Label.SharedFiles"));
            return;
        }

        var file = selection[0];
        var name = await Msg.InputAsync(this, Lang.T("Files.RenameTitle"),
            Lang.T("Files.RenamePrompt"), file.Name);
        if (name == null) return;

        name = name.Trim();
        if (name.Length == 0 || name == file.Name) return;

        if (name.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0)
        {
            await Msg.ShowAsync(this, Lang.T("Files.RenameInvalid"), Lang.T("Files.RenameTitle"));
            return;
        }

        var dir = ResolveShareDir();
        if (dir == null) return;

        var target = Path.Combine(dir, name);
        if (File.Exists(target))
        {
            await Msg.ShowAsync(this, Lang.T("Files.RenameExists"), Lang.T("Files.RenameTitle"));
            return;
        }

        try
        {
            // Renames the real file in the share folder, not a copy.
            File.Move(file.FullPath, target);
        }
        catch (Exception ex)
        {
            await Msg.ShowAsync(this,
                $"{Lang.T("Err.Prefix")} {ex.Message}", Lang.T("Files.RenameTitle"));
            return;
        }

        MoveRegistry.Rename(file.FullPath, target);

        RefreshFiles();
        SelectByName(name);
    }

    private void SelectByName(string name)
    {
        foreach (var file in _shareFiles)
        {
            if (!string.Equals(file.Name, name, StringComparison.OrdinalIgnoreCase)) continue;
            FileList.SelectedItem = file;
            FileList.ScrollIntoView(file);
            break;
        }
    }

    private async void BtnDelete_Click(object? sender, RoutedEventArgs e)
    {
        var selection = SelectedFiles();
        if (selection.Count == 0)
        {
            await Msg.ShowAsync(this, Lang.T("Files.SelectAny"), Lang.T("Label.SharedFiles"));
            return;
        }

        var answer = await Msg.ConfirmAsync(this,
            Lang.Format("Files.DeleteConfirm", selection.Count, NamePreview(selection)),
            Lang.T("Files.DeleteTitle"));
        if (!answer) return;

        var failed = 0;
        foreach (var file in selection)
        {
            try
            {
                File.Delete(file.FullPath);
                MoveRegistry.Forget(file.FullPath);
            }
            catch { failed++; }
        }

        RefreshFiles();

        if (failed > 0)
            await Msg.ShowAsync(this, Lang.Format("Files.DeleteFailed", failed),
                Lang.T("Files.DeleteTitle"));
    }

    private static string NamePreview(List<ShareFile> files)
    {
        const int max = 5;
        var names = files.Take(max).Select(f => f.Name);
        var text = string.Join(", ", names);
        if (files.Count > max)
            text += $" (+{files.Count - max})";
        return text;
    }

    private async void BtnAddFiles_Click(object? sender, RoutedEventArgs e)
    {
        var dir = ResolveShareDir();
        if (dir == null)
        {
            await Msg.ShowAsync(this, Lang.T("Files.MissingFolder"), Lang.T("Label.SharedFiles"));
            return;
        }

        var picked = await StorageProvider.OpenFilePickerAsync(new FilePickerOpenOptions
        {
            Title = Lang.T("Files.AddTitle"),
            AllowMultiple = true
        });
        if (picked.Count == 0) return;

        var choice = await Msg.ChoiceAsync(this, Lang.T("Files.CopyOrMove"),
            Lang.T("Files.AddTitle"),
            Lang.T("Files.Copy"), Lang.T("Files.Move"), Lang.T("Msg.Cancel"));
        if (choice != 0 && choice != 1) return;
        var move = choice == 1;

        var sources = new List<string>();
        foreach (var item in picked)
        {
            var local = item.TryGetLocalPath();
            if (!string.IsNullOrEmpty(local))
                sources.Add(local);
        }
        if (sources.Count == 0) return;

        FilesHint.Text = Lang.T("Files.Adding");
        SetHint(FilesHint, "hint-muted");
        FilesHint.IsVisible = true;
        BtnAddFiles.IsEnabled = false;

        int added, skipped = 0, failed = 0;
        var moved = new List<(string Target, string Origin)>();
        try
        {
            (added, skipped, failed, moved) = await Task.Run(() => ImportFiles(sources, dir, move));
        }
        finally
        {
            BtnAddFiles.IsEnabled = true;
            FilesHint.IsVisible = false;
            SetHint(FilesHint, "hint-danger");
        }

        // Remember where each moved file came from so it can be put back.
        foreach (var (target, origin) in moved)
            MoveRegistry.Record(target, origin);

        RefreshFiles();

        if (failed > 0)
            await Msg.ShowAsync(this,
                Lang.Format("Files.AddFailed", added, failed), Lang.T("Files.AddTitle"));
        else if (skipped > 0)
            await Msg.ShowAsync(this,
                Lang.Format("Files.AddSkipped", added, skipped), Lang.T("Files.AddTitle"));
    }

    // Copies (or moves) the chosen files into the share folder. The
    // original stays where it is unless the user asked for a move; every
    // move is returned so the caller can remember its origin.
    private static (int Added, int Skipped, int Failed, List<(string Target, string Origin)> Moved)
        ImportFiles(List<string> sources, string dir, bool move)
    {
        var added = 0;
        var skipped = 0;
        var failed = 0;
        var moved = new List<(string Target, string Origin)>();

        try
        {
            if (!Directory.Exists(dir))
                Directory.CreateDirectory(dir);
        }
        catch
        {
            return (0, 0, sources.Count, moved);
        }

        foreach (var source in sources)
        {
            try
            {
                var full = Path.GetFullPath(source);
                if (!File.Exists(full))
                {
                    failed++;
                    continue;
                }

                var target = Path.Combine(dir, Path.GetFileName(full));

                // Already in the share folder: nothing to do.
                if (string.Equals(Path.GetFullPath(target), full,
                        StringComparison.OrdinalIgnoreCase))
                {
                    skipped++;
                    continue;
                }

                target = UniquePath(target);

                if (move)
                {
                    File.Move(full, target);
                    moved.Add((target, full));
                }
                else
                {
                    File.Copy(full, target, overwrite: false);
                }

                added++;
            }
            catch
            {
                failed++;
            }
        }

        return (added, skipped, failed, moved);
    }

    // "report.pdf" then "report (2).pdf": never overwrites an existing file.
    private static string UniquePath(string target)
    {
        if (!File.Exists(target)) return target;

        var dir = Path.GetDirectoryName(target) ?? "";
        var name = Path.GetFileNameWithoutExtension(target);
        var ext = Path.GetExtension(target);

        for (var i = 2; i < 1000; i++)
        {
            var candidate = Path.Combine(dir, $"{name} ({i}){ext}");
            if (!File.Exists(candidate))
                return candidate;
        }

        return Path.Combine(dir, $"{name} ({Guid.NewGuid():N}){ext}");
    }

    #endregion

    private void OnServerStatusChanged(ServerManager.ServerStatus status)
    {
        if (status.State == "starting" && !string.IsNullOrEmpty(status.Address))
        {
            AddressText.Text = status.Address;
            SessionCodeText.Text = string.IsNullOrEmpty(status.SessionCode)
                ? "---"
                : status.SessionCode;
        }
    }

    private void UpdateUI(string state, string? message = null,
                          string? address = null, string? uploadUrl = null,
                          string? downloadDir = null, string? shareDir = null)
    {
        switch (state)
        {
            case "running":
                SetState(StatusDot, "running");
                StatusText.Text = Lang.T("Status.Running");
                SetState(StatusText, "running");
                AddressText.Text = address ?? "---";
                DownloadDirText.Text = downloadDir ?? "---";
                ShareDirText.Text = shareDir ?? "---";
                BtnToggleServer.Content = Lang.T("Btn.StopServer");
                BtnToggleServer.Classes.Remove("accent");
                BtnToggleServer.Classes.Add("danger");
                _isRunning = true;
                GenerateQrCode(uploadUrl);
                QrHint.IsVisible = false;
                break;
            case "stopped":
                SetState(StatusDot, "stopped");
                StatusText.Text = Lang.T("Status.Stopped");
                SetState(StatusText, "stopped");
                AddressText.Text = "---";
                SessionCodeText.Text = "---";
                BtnToggleServer.Content = Lang.T("Btn.StartServer");
                BtnToggleServer.Classes.Remove("danger");
                BtnToggleServer.Classes.Add("accent");
                QrBorder.IsVisible = false;
                QrHint.IsVisible = true;
                QrHint.Text = Lang.T("Qr.HintStart");
                _isRunning = false;
                _tokenTimer.Stop();
                TokenCountdownText.Text = "";
                DownloadDirText.Text = "---";
                ShareDirText.Text = "---";
                RefreshFiles();
                break;
            case "error":
                SetState(StatusDot, "error");
                StatusText.Text = message ?? Lang.T("Status.Error");
                SetState(StatusText, "error");
                _isRunning = false;
                break;
        }
    }

    // The colours live in MainWindow.axaml so they follow the light/dark
    // variant: only the class changes here, never a brush.
    private static readonly string[] StateClasses =
        { "state-starting", "state-running", "state-stopped", "state-error" };

    private static void SetState(Control control, string state)
    {
        foreach (var name in StateClasses) control.Classes.Remove(name);
        control.Classes.Add("state-" + state);
    }

    private static readonly string[] HintClasses =
        { "hint-muted", "hint-danger", "hint-error", "hint-success" };

    private static void SetHint(TextBlock control, string hint)
    {
        foreach (var name in HintClasses) control.Classes.Remove(name);
        control.Classes.Add(hint);
    }

    private void GenerateQrCode(string? url)
    {
        if (string.IsNullOrEmpty(url))
        {
            QrBorder.IsVisible = false;
            QrHint.IsVisible = true;
            QrHint.Text = Lang.T("Qr.Unavailable");
            return;
        }

        try
        {
            using var qrGenerator = new QRCodeGenerator();
            var qrData = qrGenerator.CreateQrCode(url, QRCodeGenerator.ECCLevel.M);
            using var qrImage = new PngByteQRCode(qrData);
            var qrBytes = qrImage.GetGraphic(8);

            using var stream = new System.IO.MemoryStream(qrBytes);
            stream.Position = 0;
            QrImage.Source = new Bitmap(stream);
            QrBorder.IsVisible = true;
            QrHint.IsVisible = false;
        }
        catch
        {
            QrBorder.IsVisible = false;
        }
    }

    private async Task PollServerAsync()
    {
        if (_serverManager.Port == null) return;

        try
        {
            var url = $"https://127.0.0.1:{_serverManager.Port}/api/info";
            var response = await _http.GetAsync(url);
            if (response.IsSuccessStatusCode)
            {
                var json = await response.Content.ReadAsStringAsync();
                var info = JsonSerializer.Deserialize<JsonElement>(json);

                var ip = info.TryGetProperty("ip", out var ipProp) ? ipProp.GetString() : _serverManager.Ip;
                var port = info.TryGetProperty("port", out var portProp) ? portProp.GetInt32() : int.Parse(_serverManager.Port);

                var address = $"{ip}:{port}";
                var uploadUrl = _serverManager.UrlUpload;

                Dispatcher.UIThread.Invoke(() => UpdateUI("running", null, address, uploadUrl,
                    _serverManager.DownloadDir, _serverManager.ShareDir));
            }
        }
        catch
        {
        }
    }

    private async Task RefreshQuotaAsync()
    {
        if (_quotaBusy) return;
        _quotaBusy = true;
        try
        {
            var limit = QuotaUsage.ReadLimit();
            var dir = QuotaUsage.ReadDownloadDir(_serverManager.DownloadDir);
            var usage = await Task.Run(() => QuotaUsage.ScanDirectory(dir));

            if (limit <= 0)
            {
                QuotaStatusText.Text = Lang.Format("Quota.Unlimited", QuotaUsage.Format(usage));
                SetHint(QuotaStatusText, "hint-muted");
            }
            else
            {
                QuotaStatusText.Text = QuotaUsage.Format(usage) + " / " + QuotaUsage.Format(limit);
                SetHint(QuotaStatusText, usage >= limit ? "hint-error" : "hint-success");
            }
        }
        catch
        {
        }
        finally
        {
            _quotaBusy = false;
        }
    }

    private void OnTokenIntervalChanged()
    {
        var intervals = new[] { 0, 300, 900, 1800, 3600 };
        var selectedIndex = TokenIntervalCombo.SelectedIndex;
        if (selectedIndex < 0 || selectedIndex >= intervals.Length) return;

        _tokenIntervalSeconds = intervals[selectedIndex];

        _tokenTimer.Stop();
        TokenCountdownText.Text = "";

        if (_tokenIntervalSeconds > 0 && _isRunning)
        {
            _tokenSecondsLeft = _tokenIntervalSeconds;
            _tokenTimer.Start();
        }
    }

    private void OnTokenTick()
    {
        if (!_isRunning || _tokenIntervalSeconds <= 0) return;

        _tokenSecondsLeft--;
        if (_tokenSecondsLeft <= 0)
        {
            _ = RefreshTokenAsync();
            _tokenSecondsLeft = _tokenIntervalSeconds;
        }

        var ts = TimeSpan.FromSeconds(_tokenSecondsLeft);
        if (ts.TotalHours >= 1)
            TokenCountdownText.Text = Lang.T("Token.NextRefresh") + $" {ts.Hours}h{ts.Minutes:D2}min";
        else
            TokenCountdownText.Text = Lang.T("Token.NextRefresh") + $" {ts.Minutes}min{ts.Seconds:D2}s";
    }

    private async Task RefreshTokenAsync()
    {
        if (!_isRunning) return;

        QrHint.IsVisible = true;
        QrHint.Text = Lang.T("Qr.Generating");

        // Explicit reset (button or timer): the only case that changes
        // the token, the QR code and the session code.
        var started = await _serverManager.RestartAsync(rotateToken: true);
        if (started)
        {
            await PollServerAsync();
            RefreshFiles();
        }
    }

    private async void BtnToggleServer_Click(object? sender, RoutedEventArgs e)
    {
        if (_isRunning)
        {
            _pollTimer.Stop();
            _tokenTimer.Stop();
            _serverManager.Stop();
            UpdateUI("stopped");
        }
        else
        {
            var started = await _serverManager.StartAsync();
            if (started)
            {
                _pollTimer.Start();
                OnTokenIntervalChanged();
                RefreshFiles();
            }
            else
            {
                UpdateUI("error", Lang.T("Err.CannotStart"));
            }
        }
    }

    private void BtnRefreshToken_Click(object? sender, RoutedEventArgs e)
    {
        if (_isRunning)
        {
            _ = RefreshTokenAsync();
            _tokenSecondsLeft = _tokenIntervalSeconds;
        }
    }

    private async void BtnSettings_Click(object? sender, RoutedEventArgs e)
    {
        try
        {
            var settingsWindow = new SettingsWindow();
            await settingsWindow.ShowDialog(this);

            if (settingsWindow.SettingsChanged)
            {
                _ = RefreshQuotaAsync();
                RefreshFiles();
                if (_isRunning)
                {
                    _ = RestartServerAsync();
                }
            }
        }
        catch (Exception ex)
        {
            await Msg.ShowAsync(this,
                $"{Lang.T("Err.Settings")}\n{ex.Message}\n\n{ex.InnerException?.Message}",
                "OpenDrop");
        }
    }

    private async Task RestartServerAsync()
    {
        _pollTimer.Stop();
        _tokenTimer.Stop();
        QrHint.IsVisible = true;
        QrHint.Text = Lang.T("Qr.Restarting");

        var started = await _serverManager.RestartAsync();
        if (started)
        {
            _pollTimer.Start();
            OnTokenIntervalChanged();
            RefreshFiles();
        }
        else
        {
            UpdateUI("error", Lang.T("Err.CannotRestart"));
        }
    }
}
