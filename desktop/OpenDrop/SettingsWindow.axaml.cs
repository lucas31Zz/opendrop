using System.Globalization;
using System.Text.Json;
using Avalonia.Controls;
using Avalonia.Interactivity;
using Avalonia.Media;
using Avalonia.Platform.Storage;
using Avalonia.Threading;

namespace OpenDrop;

public partial class SettingsWindow : Window
{
    public bool SettingsChanged { get; private set; }

    public SettingsWindow()
    {
        InitializeComponent();
        LoadSettings();
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

        UpdateQuotaUsage();
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
                Lang.Set(newLang);

            SettingsChanged = true;

            BtnSave.Content = Lang.T("Btn.Saved");
            BtnSave.Background = new SolidColorBrush(Color.FromRgb(76, 175, 80));

            var timer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(2) };
            timer.Tick += (_, _) =>
            {
                BtnSave.Content = Lang.T("Btn.Save");
                BtnSave.Background = new SolidColorBrush(Color.FromRgb(74, 158, 255));
                timer.Stop();
            };
            timer.Start();
        }
        catch { }
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
