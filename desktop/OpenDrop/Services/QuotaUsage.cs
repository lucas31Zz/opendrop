using System;
using System.Globalization;
using System.IO;
using System.Text.Json;

namespace OpenDrop;

// Utilise par la fenetre principale (affichage "x / y") et par les Reglages
// (compteur d'usage) : une seule source pour le calcul et le formatage.
internal static class QuotaUsage
{
    // Meme logique que le cote Python (src/opendrop/config/config.py) :
    // LOCALAPPDATA/APPDATA s'il existe, sinon ~/.opendrop sous Linux/macOS.
    // Sans cela, le desktop et le serveur liraient deux config.json differents.
    public static string ConfigDir
    {
        get
        {
            var env = Environment.GetEnvironmentVariable("LOCALAPPDATA")
                      ?? Environment.GetEnvironmentVariable("APPDATA");
            if (!string.IsNullOrEmpty(env))
                return Path.Combine(env, "OpenDrop");
            return Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
                ".opendrop");
        }
    }

    public static string ConfigPath => Path.Combine(ConfigDir, "config.json");

    public static long ScanDirectory(string? dir)
    {
        if (string.IsNullOrWhiteSpace(dir) || !Directory.Exists(dir))
            return 0;

        long total = 0;
        try
        {
            foreach (var file in Directory.EnumerateFiles(dir, "*", SearchOption.AllDirectories))
            {
                try { total += new FileInfo(file).Length; }
                catch { }
            }
        }
        catch { }
        return total;
    }

    public static long ReadLimit()
    {
        try
        {
            using var doc = JsonDocument.Parse(File.ReadAllText(ConfigPath));
            if (doc.RootElement.TryGetProperty("global_quota_bytes", out var q) &&
                q.ValueKind == JsonValueKind.Number && q.TryGetInt64(out var bytes))
                return bytes < 0 ? 0 : bytes;
        }
        catch { }
        return 0;
    }

    public static string? ReadDownloadDir(string? fallback)
    {
        try
        {
            using var doc = JsonDocument.Parse(File.ReadAllText(ConfigPath));
            if (doc.RootElement.TryGetProperty("download_directory", out var d) &&
                d.ValueKind == JsonValueKind.String && !string.IsNullOrWhiteSpace(d.GetString()))
                return d.GetString();
        }
        catch { }
        return fallback;
    }

    public static string Format(long bytes)
    {
        string number;
        string unit;
        if (bytes >= 1024L * 1024 * 1024)
        {
            number = (bytes / (1024d * 1024 * 1024)).ToString("0.###", CultureInfo.InvariantCulture);
            unit = "Go";
        }
        else if (bytes >= 1024L * 1024)
        {
            number = (bytes / (1024d * 1024)).ToString("0.#", CultureInfo.InvariantCulture);
            unit = "Mo";
        }
        else if (bytes >= 1024L)
        {
            number = (bytes / 1024d).ToString("0.#", CultureInfo.InvariantCulture);
            unit = "Ko";
        }
        else
        {
            number = bytes.ToString(CultureInfo.InvariantCulture);
            unit = "o";
        }
        return number.Replace('.', ',') + " " + unit;
    }
}
