using System.Globalization;
using System.Text.Json;
using Avalonia;
using Avalonia.Animation;
using Avalonia.Animation.Easings;
using Avalonia.Controls;
using Avalonia.Interactivity;
using Avalonia.Media;
using Avalonia.Platform.Storage;
using Avalonia.Styling;
using Avalonia.Threading;

namespace OpenDrop;

public partial class SettingsWindow : Window
{
    public bool SettingsChanged { get; private set; }

    // Guards the theme combo while the saved value is being restored:
    // SelectionChanged would otherwise rewrite config.json on open.
    private bool _loadingTheme;

    // The highlight that springs between the tabs: one run at a time.
    private CancellationTokenSource? _pillCts;

    public SettingsWindow()
    {
        InitializeComponent();
        // Same pointer-following sheen as the main window.
        Shine.Attach(this);
        LoadSettings();

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
        ShowPage(TabAppearance, id, "appearance");
        ShowPage(TabUpdates, id, "updates");
        MoveTabPill(animate: true);
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

    private static string GetConfigPath()
    {
        return QuotaUsage.ConfigPath;
    }
}
