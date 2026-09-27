using System;
using System.Globalization;
using System.IO;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Media;
using System.Windows.Threading;
using Microsoft.Win32;

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

        UpdateQuotaUsage();
    }

    private void BtnBrowseDownload_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var dialog = new OpenFolderDialog
            {
                Title = "Choisir le dossier de reception"
            };

            if (dialog.ShowDialog() == true)
            {
                DownloadDirText.Text = dialog.FolderName;
                UpdateQuotaUsage();
            }
        }
        catch { }
    }

    private void BtnBrowseShare_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var dialog = new OpenFolderDialog
            {
                Title = "Choisir le dossier de partage"
            };

            if (dialog.ShowDialog() == true)
            {
                ShareDirText.Text = dialog.FolderName;
            }
        }
        catch { }
    }

    private void BtnSave_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var configPath = GetConfigPath();

            // On repart du fichier existant : l'ecraser entierement supprimerait
            // les cles que cette fenetre ne gere pas (session_expires_in,
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

            config["download_directory"] = DownloadDirText.Text;
            config["share_directory"] = ShareDirText.Text;
            config["preferred_port"] = int.TryParse(PortBox.Text, out var p) ? p : 8080;
            config["generate_new_token"] = ToggleNewToken.IsChecked == true;

            // Avertissement si le quota demande depasse 20% de l'espace libre
            // du disque : on laisse l'utilisateur choisir, mais il le fait en
            // connaissance de cause.
            var quotaBytes = 0L;
            if (!TryParseQuota(QuotaBox.Text, out quotaBytes))
            {
                MessageBox.Show(
                    "Quota invalide : \"" + QuotaBox.Text + "\"\n\n" +
                    "Exemples acceptes : 0,5 go (512 Mo), 500 mo, 10.75.\n" +
                    "Un nombre sans unite est compte en Go. 0 = illimite.",
                    "Quota global", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }
            var freeBytes = GetFreeSpace(DownloadDirText.Text);
            if (ExceedsFreeSpaceWarning(quotaBytes, freeBytes))
            {
                var answer = MessageBox.Show(
                    "Quota global de " + FormatSize(quotaBytes) + "\n\n" +
                    "Ce quota depasse 20% de l'espace libre sur ce disque (" +
                    FormatSize(freeBytes) + " libres).\n\n" +
                    "Des transferts successifs finiraient par saturer ce disque : " +
                    "la machine peut ralentir, voir ne plus pouvoir ecrire " +
                    "(systeme, mises a jour, fichiers temporaires).\n\n" +
                    "A vos risques et perils : enregistrer quand meme ?",
                    "Quota global important",
                    MessageBoxButton.YesNo, MessageBoxImage.Warning);
                if (answer != MessageBoxResult.Yes)
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

            SettingsChanged = true;

            BtnSave.Content = "Enregistre !";
            BtnSave.Background = new SolidColorBrush(Color.FromRgb(76, 175, 80));

            var timer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(2) };
            timer.Tick += (_, _) =>
            {
                BtnSave.Content = "Enregistrer";
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
        QuotaUsageText.Text = "Analyse du dossier...";
        Task.Run(() =>
        {
            var used = QuotaUsage.ScanDirectory(dir);
            Dispatcher.Invoke(() =>
            {
                QuotaUsageText.Text = used > 0
                    ? "Actuellement recu : " + QuotaUsage.Format(used) + " dans ce dossier"
                    : "Aucun fichier recu dans ce dossier pour l'instant";
            });
        });
    }

    // Unites : "0,5 go" ou "0.5" (sans unite = Go), "500 mo", "512000 ko".
    // Retourne false si le texte n'est pas compris : mieux vaut refuser
    // l'enregistrement que desactiver le quota en silence.
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
            return true;                       // vide = illimite

        var t = text.Trim().ToLowerInvariant().Replace(',', '.').Replace(" ", "");
        var factor = 1024d * 1024d * 1024d;    // nombre seul = Go

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
        return (bytes / (1024d * 1024d * 1024d))
            .ToString("0.###", CultureInfo.InvariantCulture).Replace('.', ',');
    }

    // Affichage du quota relut : "500 mo" reste "500 mo" a la relecture,
    // sinon l'utilisateur retrouverait "0.488" pour ce qu'il a tape en Mo.
    private static string QuotaToText(long bytes)
    {
        if (bytes <= 0)
            return "0";
        if (bytes % (1024L * 1024) == 0 && bytes / (1024L * 1024) < 1024)
            return bytes / (1024L * 1024) + " mo";
        return BytesToGo(bytes) + " go";
    }

    private static string FormatSize(long bytes)
    {
        return QuotaUsage.Format(bytes);
    }

    // Alerte si le quota depasse 20% de l'espace libre (0 = quota desactive,
    // espace libre inconnu = pas d'alerte pour ne pas bloquer a tort).
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
