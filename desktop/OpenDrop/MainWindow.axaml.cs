using System.Text.Json;
using Avalonia.Controls;
using Avalonia.Interactivity;
using Avalonia.Media;
using Avalonia.Media.Imaging;
using Avalonia.Threading;
using QRCoder;

namespace OpenDrop;

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

    public MainWindow()
    {
        InitializeComponent();
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

        Closed += (_, _) =>
        {
            _pollTimer.Stop();
            _tokenTimer.Stop();
            _quotaTimer.Stop();
            _serverManager.Stop();
            _http.Dispose();
        };

        Opened += async (_, _) =>
        {
            _quotaTimer.Start();
            await RefreshQuotaAsync();

            var started = await _serverManager.StartAsync();
            if (started)
            {
                _pollTimer.Start();
            }
            else
            {
                UpdateUI("error", Lang.T("Err.CannotStart"));
            }
        };
    }

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
                StatusDot.Fill = new SolidColorBrush(Color.FromRgb(76, 175, 80));
                StatusText.Text = Lang.T("Status.Running");
                StatusText.Foreground = new SolidColorBrush(Color.FromRgb(76, 175, 80));
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
                StatusDot.Fill = new SolidColorBrush(Color.FromRgb(136, 136, 136));
                StatusText.Text = Lang.T("Status.Stopped");
                StatusText.Foreground = new SolidColorBrush(Color.FromRgb(170, 170, 170));
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
                break;
            case "error":
                StatusDot.Fill = new SolidColorBrush(Color.FromRgb(244, 67, 54));
                StatusText.Text = message ?? Lang.T("Status.Error");
                StatusText.Foreground = new SolidColorBrush(Color.FromRgb(244, 67, 54));
                _isRunning = false;
                break;
        }
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
                QuotaStatusText.Foreground = new SolidColorBrush(Color.FromRgb(136, 136, 136));
            }
            else
            {
                QuotaStatusText.Text = QuotaUsage.Format(usage) + " / " + QuotaUsage.Format(limit);
                QuotaStatusText.Foreground = usage >= limit
                    ? new SolidColorBrush(Color.FromRgb(244, 67, 54))
                    : new SolidColorBrush(Color.FromRgb(76, 175, 80));
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
        }
        else
        {
            UpdateUI("error", Lang.T("Err.CannotRestart"));
        }
    }
}
