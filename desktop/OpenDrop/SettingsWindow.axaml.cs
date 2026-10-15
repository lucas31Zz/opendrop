using System.Diagnostics;
using System.Globalization;
using System.Text.Json;
using Avalonia;
using Avalonia.Animation;
using Avalonia.Animation.Easings;
using Avalonia.Controls;
using Avalonia.Input;
using Avalonia.Interactivity;
using Avalonia.Layout;
using Avalonia.Media;
using Avalonia.Media.Imaging;
using Avalonia.Platform.Storage;
using Avalonia.Styling;
using Avalonia.Threading;
using QRCoder;

namespace OpenDrop;

public partial class SettingsWindow : Window
{
    public bool SettingsChanged { get; private set; }

    // Guards the theme combo while the saved value is being restored:
    // SelectionChanged would otherwise rewrite config.json on open.
    private bool _loadingTheme;

    // The highlight that springs between the tabs: one run at a time.
    private CancellationTokenSource? _pillCts;

    // The Appareils tab talks to the local server through these: the same
    // ServerManager and loopback-bypassing HttpClient as the main window
    // (passed in rather than rebuilt, so the certificate handling stays
    // in one place). _serverRunning is the state at the time the window
    // opened; the pairing client keeps it fresh from there.
    private readonly ServerManager _serverManager;
    private readonly HttpClient _http;
    private bool _serverRunning;

    // The full device token: the label shows a truncated form, but the
    // copy button needs the whole value.
    private string DeviceTokenValue = "";

    // The Appareils tab keeps itself fresh while it is shown: one 3 s
    // tick at a time, and never two loads in flight at once - a tick
    // landing on a running load queues exactly one more run instead of
    // stacking a second request on it.
    private readonly DispatcherTimer _devicesTimer = new()
    {
        Interval = TimeSpan.FromSeconds(3)
    };
    private bool _devicesBusy;
    private bool _devicesReloadQueued;

    // What the pair card currently shows: the QR is only re-rendered
    // when the link itself changes (the tab reloads every 3 s).
    private string _lastPairLink = "";

    // Signature of the last rendered device set (count + ip + share
    // flag): an unchanged set keeps its rows, so a pointer resting on a
    // Dissocier button never has the row rebuilt underneath it.
    private string? _lastRowsSignature;

    public SettingsWindow(ServerManager serverManager, HttpClient http, bool serverRunning)
    {
        _serverManager = serverManager;
        _http = http;
        _serverRunning = serverRunning;
        InitializeComponent();
        // Same reduced-motion guard as the main window.
        Motion.Apply(this);
        LoadSettings();

        // The Appareils buttons are wired here rather than in the XAML
        // (task 10 shipped the shell inert). The constructor snapshot
        // only seeds the enabled state: LoadDevicesAsync re-asks
        // ServerManager on every load, since the server may have been
        // stopped or restarted since this window opened.
        BtnCopyToken.Click += BtnCopyToken_Click;
        BtnRefreshDevices.Click += BtnRefreshDevices_Click;
        BtnCopyLink.Click += BtnCopyLink_Click;
        BtnOpenLink.Click += BtnOpenLink_Click;
        BtnReset.Click += BtnReset_Click;
        if (!_serverRunning)
        {
            BtnCopyToken.IsEnabled = false;
            BtnCopyLink.IsEnabled = false;
            BtnOpenLink.IsEnabled = false;
            BtnReset.IsEnabled = false;
        }

        // The list only refreshes itself while its own tab is shown;
        // the Closed hook leaves no timer ticking behind the window.
        _devicesTimer.Tick += (_, _) => _ = LoadDevicesAsync();
        Closed += (_, _) => _devicesTimer.Stop();

        // The pill needs a real layout pass before its position is known.
        Opened += (_, _) => MoveTabPill(animate: false);
    }

    private void LoadSettings()
    {
        try
        {
            var configPath = GetConfigPath();
            if (File.Exists(configPath))
            {
                var json = File.ReadAllText(configPath);
                var config = JsonSerializer.Deserialize<JsonElement>(json);

                if (config.TryGetProperty("download_directory", out var dd))
                    DownloadDirText.Text = dd.GetString() ?? "Downloads/OpenDrop";

                if (config.TryGetProperty("share_directory", out var sd))
                    ShareDirText.Text = sd.GetString() ?? "Downloads/OpenDrop/Partage";

                if (config.TryGetProperty("preferred_port", out var port))
                    PortBox.Text = port.GetInt32().ToString();

                if (config.TryGetProperty("generate_new_token", out var token))
                    ToggleNewToken.IsChecked = token.GetBoolean();

                if (config.TryGetProperty("global_quota_bytes", out var quota))
                    QuotaBox.Text = QuotaToText(quota.GetInt64());
            }
        }
        catch { }

        LanguageCombo.SelectedIndex = Lang.Current == "fr" ? 1 : 0;

        // Theme combo: items come from ThemeManager, index = list order.
        PopulateThemeCombo();

        VersionText.Text = UpdateService.CurrentVersion;

        UpdateQuotaUsage();
    }

    // One page at a time: the RadioButtons share a group, so exactly one
    // of them is checked and this only mirrors its Tag on the panels.
    // Pages are null while the XAML is still being parsed (the first
    // IsChecked="True" can fire before the later panels exist).
    private void Tab_Click(object? sender, RoutedEventArgs e)
    {
        if (sender is not RadioButton tab || tab.Tag is not string id)
            return;
        ShowPage(TabGeneral, id, "general");
        ShowPage(TabStorage, id, "storage");
        ShowPage(TabSecurity, id, "security");
        ShowPage(TabNetwork, id, "network");
        ShowPage(TabDevices, id, "devices");
        ShowPage(TabAppearance, id, "appearance");
        ShowPage(TabUpdates, id, "updates");
        MoveTabPill(animate: true);

        // The devices tab is the only one with live data behind it: it
        // reloads on every visit (a device may have paired, the server
        // may have been stopped or restarted since the last look) and
        // then keeps itself fresh every 3 s until another tab - or the
        // window itself - goes away.
        if (id == "devices")
        {
            // LoadDevicesAsync swallows its own failures into the hint.
            try { _ = LoadDevicesAsync(); } catch { }
            _devicesTimer.Start();
        }
        else
        {
            _devicesTimer.Stop();
        }
    }

    // Puts the highlight over the checked tab; on a switch it is driven
    // by a spring, so the pill overshoots a little and settles (the
    // reactbits "Tabs" behaviour, translated to Avalonia).
    private void MoveTabPill(bool animate)
    {
        var checkedTab = TabList.Children.OfType<RadioButton>()
            .FirstOrDefault(button => button.IsChecked == true);
        if (checkedTab == null || checkedTab.Bounds.Height <= 0) return;

        var top = checkedTab.Bounds.Top;
        var height = checkedTab.Bounds.Height;

        if (!animate)
        {
            TabPill.Margin = new Thickness(0, top, 0, 0);
            TabPill.Height = height;
            return;
        }

        // Start from wherever the pill actually is right now, which may
        // be in the middle of the previous spring.
        var fromTop = TabPill.Margin.Top;
        var fromHeight = TabPill.Height;
        if (Math.Abs(top - fromTop) < 0.5 && Math.Abs(height - fromHeight) < 0.5)
            return;

        _pillCts?.Cancel();
        _pillCts = new CancellationTokenSource();
        _ = AnimateTabPillAsync(fromTop, fromHeight, top, height, _pillCts.Token);
    }

    private async Task AnimateTabPillAsync(double fromTop, double fromHeight,
        double toTop, double toHeight, CancellationToken token)
    {
        var animation = new Animation
        {
            Duration = TimeSpan.FromMilliseconds(520),
            Easing = new SpringEasing { Mass = 1, Stiffness = 170, Damping = 17 },
            FillMode = FillMode.Forward,
            Children =
            {
                new KeyFrame
                {
                    Cue = new Cue(0.0),
                    Setters =
                    {
                        new Setter(Border.MarginProperty, new Thickness(0, fromTop, 0, 0)),
                        new Setter(Border.HeightProperty, fromHeight),
                    },
                },
                new KeyFrame
                {
                    Cue = new Cue(1.0),
                    Setters =
                    {
                        new Setter(Border.MarginProperty, new Thickness(0, toTop, 0, 0)),
                        new Setter(Border.HeightProperty, toHeight),
                    },
                },
            },
        };

        try
        {
            await animation.RunAsync(TabPill, token);
        }
        catch (OperationCanceledException)
        {
            // Another click took over: the new spring carries on from the
            // interrupted position, nothing else to do.
        }
    }

    private static void ShowPage(Control? page, string id, string pageId)
    {
        if (page != null)
            page.IsVisible = id == pageId;
    }

    // Fills the theme ComboBox from ThemeManager: the list of themes is
    // defined once there (and mirrored by src/opendrop/themes.py), never
    // written by hand in the XAML. Rebuilt on language switch too, since
    // the names are translated.
    private void PopulateThemeCombo()
    {
        _loadingTheme = true;
        ThemeCombo.Items.Clear();
        var selected = ThemeManager.Current;
        var index = 0;
        for (var i = 0; i < ThemeManager.Themes.Count; i++)
        {
            var id = ThemeManager.Themes[i].Id;
            ThemeCombo.Items.Add(new ComboBoxItem { Content = ThemeManager.NameOf(id) });
            if (id == selected)
                index = i;
        }
        ThemeCombo.SelectedIndex = index;
        _loadingTheme = false;
    }

    private async void BtnBrowseDownload_Click(object? sender, RoutedEventArgs e)
    {
        try
        {
            var folder = await PickFolderAsync(Lang.T("Browse.ReceiveTitle"));
            if (folder != null)
            {
                DownloadDirText.Text = folder;
                UpdateQuotaUsage();
            }
        }
        catch { }
    }

    // The theme is applied live: RequestedThemeVariant is the only thing
    // that changes, so there is nothing to confirm and nothing to roll back.
    private void ThemeCombo_SelectionChanged(object? sender, SelectionChangedEventArgs e)
    {
        if (_loadingTheme) return;
        var index = ThemeCombo.SelectedIndex;
        if (index < 0 || index >= ThemeManager.Themes.Count) return;
        ThemeManager.Set(ThemeManager.Themes[index].Id);
        // Device rows are code-built with brushes resolved at build
        // time: drop the skip signature so the next load repaints them.
        _lastRowsSignature = null;
    }

    private async void BtnBrowseShare_Click(object? sender, RoutedEventArgs e)
    {
        try
        {
            var folder = await PickFolderAsync(Lang.T("Browse.ShareTitle"));
            if (folder != null)
            {
                ShareDirText.Text = folder;
            }
        }
        catch { }
    }

    // Native folder picker (GTK on Linux, Windows on Windows).
    private async Task<string?> PickFolderAsync(string title)
    {
        var folders = await StorageProvider.OpenFolderPickerAsync(new FolderPickerOpenOptions
        {
            Title = title,
            AllowMultiple = false
        });
        return folders.Count > 0 ? folders[0].TryGetLocalPath() : null;
    }

    private async void BtnSave_Click(object? sender, RoutedEventArgs e)
    {
        try
        {
            var configPath = GetConfigPath();

            // Start from the existing file: overwriting it entirely would
            // drop the keys this window does not manage (session_expires_in,
            // trust_proxy, ...).
            var config = new Dictionary<string, object>();
            if (File.Exists(configPath))
            {
                try
                {
                    var existing = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(
                        File.ReadAllText(configPath));
                    if (existing != null)
                    {
                        foreach (var kv in existing)
                            config[kv.Key] = kv.Value;
                    }
                }
                catch { }
            }

            config["language"] = LanguageCombo.SelectedIndex == 1 ? "fr" : "en";
            config["download_directory"] = DownloadDirText.Text ?? "";
            config["share_directory"] = ShareDirText.Text ?? "";
            config["preferred_port"] = int.TryParse(PortBox.Text, out var p) ? p : 8080;
            config["generate_new_token"] = ToggleNewToken.IsChecked == true;
            // The theme is written by ThemeManager.Set as soon as it
            // changes; stored here too so a save never drops it.
            config["theme"] = ThemeManager.Current;

            // Warn when the requested quota exceeds 20% of the disk's free
            // space: the user may still choose it, but knowingly.
            var quotaBytes = 0L;
            if (!TryParseQuota(QuotaBox.Text ?? "", out quotaBytes))
            {
                await Msg.ShowAsync(this,
                    Lang.Format("Quota.Invalid", QuotaBox.Text),
                    Lang.T("Field.GlobalQuota"));
                return;
            }
            var freeBytes = GetFreeSpace(DownloadDirText.Text ?? "");
            if (ExceedsFreeSpaceWarning(quotaBytes, freeBytes))
            {
                var answer = await Msg.ConfirmAsync(this,
                    Lang.Format("Quota.BigBody",
                                FormatSize(quotaBytes), FormatSize(freeBytes)),
                    Lang.T("Quota.BigTitle"));
                if (!answer)
                    return;
            }
            config["global_quota_bytes"] = quotaBytes;

            var json = JsonSerializer.Serialize(config, new JsonSerializerOptions
            {
                WriteIndented = true
            });

            var dir = Path.GetDirectoryName(configPath);
            if (dir != null && !Directory.Exists(dir))
                Directory.CreateDirectory(dir);

            File.WriteAllText(configPath, json);

            // Apply the language live; the main window restarts the server
            // afterwards, so the console banner follows the choice too.
            var newLang = LanguageCombo.SelectedIndex == 1 ? "fr" : "en";
            if (newLang != Lang.Current)
            {
                Lang.Set(newLang);
                // The theme names are translated: refresh the combo so it
                // does not keep the previous language until the next open.
                PopulateThemeCombo();
                // Rows are code-built (button label, brushes): drop the
                // skip signature so the next load rebuilds them in the
                // new language.
                _lastRowsSignature = null;
            }

            SettingsChanged = true;

            // The accent behind the button is the one the theme currently
            // gives it: captured before turning green so the reset lands on
            // the right colour in light and dark alike.
            var accent = BtnSave.Background;
            BtnSave.Content = Lang.T("Btn.Saved");
            BtnSave.Background = new SolidColorBrush(Color.FromRgb(76, 175, 80));

            var timer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(2) };
            timer.Tick += (_, _) =>
            {
                BtnSave.Content = Lang.T("Btn.Save");
                BtnSave.Background = accent;
                timer.Stop();
            };
            timer.Start();
        }
        catch { }
    }

    // Same path as the check at startup, but interactive: the answer is
    // always spelled out here, even when there is nothing to update.
    private async void BtnCheckUpdates_Click(object? sender, RoutedEventArgs e)
    {
        BtnCheckUpdates.IsEnabled = false;
        UpdateStatusText.Text = Lang.T("Up.Checking");
        try
        {
            var message = await UpdateRunner.RunAsync(this, interactive: true);
            UpdateStatusText.Text = message ?? "";
        }
        catch (Exception ex)
        {
            UpdateStatusText.Text = Lang.Format("Up.Error", ex.Message);
        }
        finally
        {
            BtnCheckUpdates.IsEnabled = true;
        }
    }

    private void UpdateQuotaUsage()
    {
        var dir = DownloadDirText.Text;
        QuotaUsageText.Text = Lang.T("Quota.Scanning");
        Task.Run(() =>
        {
            var used = QuotaUsage.ScanDirectory(dir);
            Dispatcher.UIThread.Invoke(() =>
            {
                QuotaUsageText.Text = used > 0
                    ? Lang.Format("Quota.Usage", QuotaUsage.Format(used))
                    : Lang.T("Quota.NoFiles");
            });
        });
    }

    // Units: "0,5 gb" or "0.5" (no unit = GB), "500 mb", "512000 kb".
    // Returns false when the text is not understood: refusing the save is
    // better than silently disabling the quota.
    private static readonly (string Suffix, double Factor)[] QuotaUnits =
    {
        ("tib", 1024d * 1024 * 1024 * 1024), ("tb", 1024d * 1024 * 1024 * 1024),
        ("gib", 1024d * 1024 * 1024), ("gb", 1024d * 1024 * 1024),
        ("go", 1024d * 1024 * 1024), ("g", 1024d * 1024 * 1024),
        ("mib", 1024d * 1024), ("mb", 1024d * 1024), ("mo", 1024d * 1024),
        ("m", 1024d * 1024),
        ("kib", 1024d), ("kb", 1024d), ("ko", 1024d), ("k", 1024d),
        ("b", 1d),
    };

    internal static bool TryParseQuota(string text, out long bytes)
    {
        bytes = 0;
        if (string.IsNullOrWhiteSpace(text))
            return true;                       // empty = unlimited

        var t = text.Trim().ToLowerInvariant().Replace(',', '.').Replace(" ", "");
        var factor = 1024d * 1024d * 1024d;    // bare number = GB

        foreach (var (suffix, f) in QuotaUnits)
        {
            if (t.Length > suffix.Length && t.EndsWith(suffix, StringComparison.Ordinal))
            {
                t = t.Substring(0, t.Length - suffix.Length);
                factor = f;
                break;
            }
        }

        if (!double.TryParse(t, NumberStyles.Float, CultureInfo.InvariantCulture, out var value)
            || double.IsNaN(value) || value < 0)
            return false;

        bytes = (long)Math.Round(value * factor);
        return true;
    }

    private static string BytesToGo(long bytes)
    {
        if (bytes <= 0)
            return "0";
        var text = (bytes / (1024d * 1024d * 1024d))
            .ToString("0.###", CultureInfo.InvariantCulture);
        // Decimal comma in French, decimal point in English.
        return Lang.Current == "fr" ? text.Replace('.', ',') : text;
    }

    // Quota round-trip display: "500 mb" stays "500 mb" when re-read,
    // otherwise the user would see "0.488" for what they typed in MB.
    private static string QuotaToText(long bytes)
    {
        if (bytes <= 0)
            return "0";
        var fr = Lang.Current == "fr";
        if (bytes % (1024L * 1024) == 0 && bytes / (1024L * 1024) < 1024)
            return bytes / (1024L * 1024) + (fr ? " mo" : " mb");
        return BytesToGo(bytes) + (fr ? " go" : " gb");
    }

    private static string FormatSize(long bytes)
    {
        return QuotaUsage.Format(bytes);
    }

    // Warn when the quota exceeds 20% of the free space (0 = quota
    // disabled, unknown free space = no warning, to avoid false alarms).
    internal static bool ExceedsFreeSpaceWarning(long quotaBytes, long freeBytes)
    {
        if (quotaBytes <= 0 || freeBytes <= 0)
            return false;
        return (double)quotaBytes > freeBytes * 0.2d;
    }

    private static long GetFreeSpace(string path)
    {
        try
        {
            if (string.IsNullOrWhiteSpace(path))
                return 0;
            var root = Path.GetPathRoot(Path.GetFullPath(path));
            if (string.IsNullOrEmpty(root))
                return 0;
            return new DriveInfo(root).AvailableFreeSpace;
        }
        catch { return 0; }
    }

    // ------------------------------------------------------------------------
    // Appareils tab: the device-pairing API behind the task 10 shell.
    // Everything goes through the loopback HttpClient (_http already
    // accepts the self-signed certificate) and the main token from
    // ServerManager; failures are muted into the hint line rather than
    // raised as popups.

    private string DevicesUrl(string path) =>
        $"https://127.0.0.1:{_serverManager.Port}{path}?token={Uri.EscapeDataString(_serverManager.Token ?? "")}";

    // One load at a time: the 3 s tick must never stack a second
    // request on one already in flight. A reload asked for while a load
    // runs (a reset, a dissociation) is queued and runs once more
    // afterwards, so it is never dropped behind a concurrent tick.
    private async Task LoadDevicesAsync()
    {
        if (_devicesBusy)
        {
            _devicesReloadQueued = true;
            return;
        }

        _devicesBusy = true;
        try
        {
            do
            {
                _devicesReloadQueued = false;
                await LoadDevicesOnceAsync();
            } while (_devicesReloadQueued);
        }
        finally
        {
            _devicesBusy = false;
        }
    }

    // One load of the tab: the token label, the pair card it feeds, and
    // one card per paired device. The stopped state is re-checked here
    // on every call (the ctor snapshot would go stale as soon as the
    // server restarts).
    private async Task LoadDevicesOnceAsync()
    {
        if (!_serverManager.IsRunning || _serverManager.Port == null)
        {
            DeviceTokenValue = "";
            DevicesToken.IsVisible = false;
            BtnCopyToken.IsVisible = false;
            BtnCopyToken.IsEnabled = false;
            // Nothing can be paired, copied or reset without a server:
            // the whole section goes away and the hint says why.
            PairCard.IsVisible = false;
            BtnCopyLink.IsEnabled = false;
            BtnOpenLink.IsEnabled = false;
            BtnReset.IsEnabled = false;
            PairHintText.Text = Lang.T("Devices.Stopped");
            DevicesList.Children.Clear();
            _lastRowsSignature = null;
            DevicesEmptyText.IsVisible = true;
            return;
        }

        try
        {
            var response = await _http.GetAsync(DevicesUrl("/api/devices"));
            if (!response.IsSuccessStatusCode)
            {
                PairHintText.Text = Lang.T("Err.Prefix");
                return;
            }

            var json = await response.Content.ReadAsStringAsync();
            using var doc = JsonDocument.Parse(json);
            var root = doc.RootElement;

            // Token: truncated in the label, the full value kept in the
            // field the copy button reads. Both appear together.
            DeviceTokenValue = root.TryGetProperty("device_token", out var tokenProp)
                ? tokenProp.GetString() ?? ""
                : "";
            if (DeviceTokenValue.Length > 0)
            {
                DevicesToken.Text = DeviceTokenValue[..8] + "…";
                DevicesToken.IsVisible = true;
                BtnCopyToken.IsVisible = true;
                BtnCopyToken.IsEnabled = true;
            }
            else
            {
                DevicesToken.IsVisible = false;
                BtnCopyToken.IsVisible = false;
            }

            // The pair card follows the token (and reappears after a
            // restart); UpdatePairSection is a no-op while the link is
            // the one already rendered.
            BtnCopyLink.IsEnabled = true;
            BtnOpenLink.IsEnabled = true;
            BtnReset.IsEnabled = true;
            UpdatePairSection();

            // Rows are only rebuilt when the set they render changed:
            // the 3 s auto-refresh would otherwise tear every row down
            // under a pointer resting on its Dissocier button.
            var rows = new List<(string Ip, string Details)>();
            var marks = new List<string>();
            if (root.TryGetProperty("devices", out var devices))
            {
                foreach (var device in devices.EnumerateArray())
                {
                    var ip = device.TryGetProperty("ip", out var ipProp)
                        ? ipProp.GetString() ?? "" : "";
                    var ua = device.TryGetProperty("ua", out var uaProp)
                        ? uaProp.GetString() ?? "" : "";
                    var shareInfo = device.TryGetProperty("share_info", out var shareProp)
                        && shareProp.GetBoolean();
                    var addedAt = device.TryGetProperty("added_at", out var addedProp)
                        ? addedProp.GetString() ?? "" : "";

                    var parts = new List<string>();
                    // The user agent is personal data: its summary is
                    // only shown when the device opted into sharing it.
                    if (shareInfo)
                    {
                        var summary = UaSummary(ua);
                        if (summary.Length > 0)
                            parts.Add(summary);
                    }
                    var date = FormatAddedAt(addedAt);
                    if (date.Length > 0)
                        parts.Add(date);

                    marks.Add($"{ip.Length}:{ip}:{(shareInfo ? '1' : '0')}");
                    rows.Add((ip, string.Join(" · ", parts)));
                }
            }

            var signature = rows.Count + "|" + string.Join("|", marks);
            if (signature != _lastRowsSignature)
            {
                _lastRowsSignature = signature;
                DevicesList.Children.Clear();
                foreach (var (ip, details) in rows)
                    DevicesList.Children.Add(BuildDeviceRow(ip, details));
                DevicesEmptyText.IsVisible = DevicesList.Children.Count == 0;
            }
            PairHintText.Text = "";
        }
        catch
        {
            PairHintText.Text = Lang.T("Err.Prefix");
        }
    }

    // One card per paired device: IP and details on the left, the way
    // to remove it on the right. The button carries its IP in Tag; the
    // click thunk below just unwraps it.
    private Border BuildDeviceRow(string ip, string details)
    {
        var lines = new StackPanel();
        lines.Children.Add(new TextBlock
        {
            Text = ip,
            FontSize = 13,
            Foreground = ResolveBrush("Brush.TextSecondary",
                Color.FromRgb(0xcc, 0xcc, 0xcc))
        });
        if (details.Length > 0)
        {
            lines.Children.Add(new TextBlock
            {
                Text = details,
                FontSize = 11,
                Foreground = ResolveBrush("Brush.TextFaint",
                    Color.FromRgb(0x8a, 0x8a, 0x8a)),
                TextWrapping = TextWrapping.Wrap
            });
        }

        var remove = new Button
        {
            Content = Lang.T("Devices.Dissociate"),
            Tag = ip,
            VerticalAlignment = VerticalAlignment.Center,
            Margin = new Thickness(8, 0, 0, 0)
        };
        remove.Classes.Add("browse");
        remove.Click += (s, _) =>
        {
            if (s is Button { Tag: string target })
                BtnDissociate_Click(s, target);
        };

        var grid = new Grid();
        grid.ColumnDefinitions.Add(new ColumnDefinition(GridLength.Star));
        grid.ColumnDefinitions.Add(new ColumnDefinition(GridLength.Auto));
        Grid.SetColumn(lines, 0);
        Grid.SetColumn(remove, 1);
        grid.Children.Add(lines);
        grid.Children.Add(remove);

        return new Border
        {
            Classes = { "card" },
            Margin = new Thickness(0, 0, 0, 8),
            Padding = new Thickness(12, 8),
            Child = grid
        };
    }

    // Theme brushes resolved once at build time, same approach as Msg
    // for its dialogs: a theme switch drops the row signature (see
    // ThemeCombo_SelectionChanged), so the next load rebuilds the rows
    // with the brushes of the new variant.
    private static IBrush ResolveBrush(string key, Color fallback)
    {
        var app = Application.Current;
        if (app != null &&
            app.TryGetResource(key, app.ActualThemeVariant, out var value) &&
            value is IBrush brush)
            return brush;
        return new SolidColorBrush(fallback);
    }

    // Best-effort browser/OS breakdown, mirroring the ordered keyword
    // scan of src/opendrop/security/devices.py (parse_user_agent) —
    // never a User-Agent library.
    private static string UaSummary(string ua)
    {
        if (string.IsNullOrWhiteSpace(ua)) return "";

        var device = ua.Contains("iPhone") ? "iPhone"
            : ua.Contains("iPad") ? "iPad"
            : ua.Contains("Android") ? "Android" : "";

        var os = ua.Contains("Windows") ? "Windows"
            : ua.Contains("Android") ? "Android"
            : ua.Contains("Mac OS X") ? "macOS"
            : ua.Contains("Linux") ? "Linux" : "";

        var browser = ua.Contains("Edg/") ? "Edge"
            : ua.Contains("OPR/") ? "Opera"
            : ua.Contains("Chrome/") ? "Chrome"
            : ua.Contains("Firefox") ? "Firefox"
            : ua.Contains("Safari") ? "Safari" : "";

        // Distinct: an Android UA would otherwise say it twice.
        return string.Join(" · ",
            new[] { device, os, browser }.Where(p => p.Length > 0).Distinct());
    }

    // added_at is an ISO-8601 UTC stamp from the server; shown as the
    // local short date. Unparseable = no date line at all.
    private static string FormatAddedAt(string addedAt)
    {
        return DateTimeOffset.TryParse(addedAt, CultureInfo.InvariantCulture,
            DateTimeStyles.AssumeUniversal, out var moment)
            ? moment.ToLocalTime().ToString("d", CultureInfo.CurrentCulture)
            : "";
    }

    // The link behind the QR: the web UI opens with this hash and
    // pre-fills its pairing overlay (see web/app.js, #pair=). The clean
    // origin WITHOUT "?token=" is deliberate (amendment 2026-10-15):
    // the pairing page must open locked, so validating stays the access
    // gate and the master token never sits in a QR on a settings screen.
    private string PairLink =>
        (_serverManager.Ip != null && _serverManager.Port != null)
            ? $"https://{_serverManager.Ip}:{_serverManager.Port}/#pair={DeviceTokenValue}"
            : "";

    // Renders the pair card from PairLink: the text (with the same
    // string as its tooltip, the link can wrap) plus the QR drawn from
    // it. Nothing is re-rendered while the link is the one already on
    // screen, and any failure (no link, QRCoder refusing the input)
    // just hides the card instead of raising a popup.
    private void UpdatePairSection()
    {
        var link = PairLink;
        PairLinkText.Text = link;
        // Attached property: the tooltip repeats the link in full, the
        // TextBlock only wraps it.
        ToolTip.SetTip(PairLinkText, link);

        if (link == _lastPairLink && PairCard.IsVisible)
            return;

        if (link.Length == 0 || DeviceTokenValue.Length == 0 ||
            _serverManager.Ip == null || _serverManager.Port == null)
        {
            PairCard.IsVisible = false;
            return;
        }

        try
        {
            // Same QRCoder pattern as MainWindow.GenerateQrCode: ECC M,
            // 8 px per module, PNG straight into an Avalonia bitmap.
            using var qrGenerator = new QRCodeGenerator();
            var qrData = qrGenerator.CreateQrCode(link, QRCodeGenerator.ECCLevel.M);
            using var qrImage = new PngByteQRCode(qrData);
            var qrBytes = qrImage.GetGraphic(8);

            using var stream = new MemoryStream(qrBytes);
            stream.Position = 0;
            PairQrImage.Source = new Bitmap(stream);
            _lastPairLink = link;
            PairCard.IsVisible = true;
        }
        catch
        {
            PairCard.IsVisible = false;
        }
    }

    // Rotates the device token server-side and drops every registered
    // device with it (their sessions die too), so every phone paired
    // through the old QR has to be paired again. Confirm only when that
    // is about to cost something: with no device on the list the reset
    // is a plain rotation behind the scenes.
    private async void BtnReset_Click(object? sender, RoutedEventArgs e)
    {
        if (!_serverManager.IsRunning || _serverManager.Port == null) return;

        if (DevicesList.Children.Count > 0)
        {
            var answer = await Msg.ConfirmAsync(this, Lang.T("Devices.ResetConfirm"));
            if (!answer) return;
        }

        try
        {
            var response = await _http.PostAsync(DevicesUrl("/api/device/reset"), null);
            if (!response.IsSuccessStatusCode)
            {
                PairHintText.Text = Lang.T("Err.Prefix");
                return;
            }

            // The answer carries the new token: show it right away
            // rather than waiting for the reload's round trip.
            var json = await response.Content.ReadAsStringAsync();
            using var doc = JsonDocument.Parse(json);
            if (doc.RootElement.TryGetProperty("device_token", out var tokenProp))
            {
                var rotated = tokenProp.GetString();
                if (!string.IsNullOrEmpty(rotated))
                    DeviceTokenValue = rotated;
            }
        }
        catch
        {
            PairHintText.Text = Lang.T("Err.Prefix");
            return;
        }

        UpdatePairSection();
        await LoadDevicesAsync();
    }

    // The whole pairing link into the clipboard (the label wraps it),
    // then the button says so for a moment - same pattern as the token
    // copy just above.
    private async void BtnCopyLink_Click(object? sender, RoutedEventArgs e)
    {
        var link = PairLink;
        if (string.IsNullOrEmpty(link)) return;

        try
        {
            if (TopLevel.GetTopLevel(this)?.Clipboard is not { } clipboard) return;
            // Avalonia 12: IClipboard takes an IAsyncDataTransfer, not a raw string.
            var payload = new DataTransfer();
            payload.Add(DataTransferItem.CreateText(link));
            await clipboard.SetDataAsync(payload);

            BtnCopyLink.Content = Lang.T("Btn.Copied");
            await Task.Delay(1500);
            BtnCopyLink.Content = Lang.T("Btn.Copy");
        }
        catch { }
    }

    // Opens the pairing link in the default browser, for whoever would
    // rather type the URL on the other device than scan it. Silent on
    // failure: no handler registered is not worth a popup.
    private void BtnOpenLink_Click(object? sender, RoutedEventArgs e)
    {
        var link = PairLink;
        if (string.IsNullOrEmpty(link)) return;

        try
        {
            Process.Start(new ProcessStartInfo(link) { UseShellExecute = true });
        }
        catch { }
    }

    // Full token into the clipboard (the label only shows its first 8
    // characters), then the button says so for a moment — same pattern
    // as the session-code copy in the main window.
    private async void BtnCopyToken_Click(object? sender, RoutedEventArgs e)
    {
        if (string.IsNullOrEmpty(DeviceTokenValue)) return;

        try
        {
            if (TopLevel.GetTopLevel(this)?.Clipboard is not { } clipboard) return;
            // Avalonia 12: IClipboard takes an IAsyncDataTransfer, not a raw string.
            var payload = new DataTransfer();
            payload.Add(DataTransferItem.CreateText(DeviceTokenValue));
            await clipboard.SetDataAsync(payload);

            BtnCopyToken.Content = Lang.T("Btn.Copied");
            await Task.Delay(1500);
            BtnCopyToken.Content = Lang.T("Btn.Copy");
        }
        catch { }
    }

    // Removes the device record; the device token is left alone (only
    // Réinitialiser rotates it, on the server), so the reload below
    // just drops the row.
    private async void BtnDissociate_Click(object? sender, string ip)
    {
        if (string.IsNullOrEmpty(ip)) return;

        var answer = await Msg.ConfirmAsync(this, Lang.T("Devices.DissociateConfirm"));
        if (!answer) return;

        try
        {
            var url = DevicesUrl("/api/device/dissociate") +
                      $"&ip={Uri.EscapeDataString(ip)}";
            var response = await _http.PostAsync(url, null);
            if (!response.IsSuccessStatusCode)
            {
                PairHintText.Text = Lang.T("Err.Prefix");
                return;
            }
        }
        catch
        {
            PairHintText.Text = Lang.T("Err.Prefix");
            return;
        }

        await LoadDevicesAsync();
    }

    private async void BtnRefreshDevices_Click(object? sender, RoutedEventArgs e)
        => await LoadDevicesAsync();

    private static string GetConfigPath()
    {
        return QuotaUsage.ConfigPath;
    }
}
