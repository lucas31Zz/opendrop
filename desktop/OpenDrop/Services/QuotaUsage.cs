using System;
using System.Globalization;
using System.IO;
using System.Text.Json;

namespace OpenDrop;

// Used by the main window ("x / y" display) and by Settings (usage
// counter): a single source for the computation and the formatting.
internal static class QuotaUsage
{
    // Same logic as the Python side (src/opendrop/config/config.py):
    // LOCALAPPDATA/APPDATA when present, otherwise ~/.opendrop on
    // Linux/macOS. Without this, desktop and server would read two
    // different config.json files.
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
        return ReadConfigString("download_directory", fallback);
    }

    // The share folder as configured (used when the server is stopped:
    // once it runs, /api/info reports its own resolved path).
    public static string? ReadShareDir(string? fallback)
    {
        return ReadConfigString("share_directory", fallback);
    }

    private static string? ReadConfigString(string key, string? fallback)
    {
        try
        {
            using var doc = JsonDocument.Parse(File.ReadAllText(ConfigPath));
            if (doc.RootElement.TryGetProperty(key, out var d) &&
                d.ValueKind == JsonValueKind.String && !string.IsNullOrWhiteSpace(d.GetString()))
                return d.GetString();
        }
        catch { }
        return fallback;
    }

    public static string Format(long bytes)
    {
        var fr = Lang.Current == "fr";
        string number;
        string unit;
        if (bytes >= 1024L * 1024 * 1024)
        {
            number = (bytes / (1024d * 1024 * 1024)).ToString("0.###", CultureInfo.InvariantCulture);
            unit = fr ? "Go" : "GB";
        }
        else if (bytes >= 1024L * 1024)
        {
            number = (bytes / (1024d * 1024)).ToString("0.#", CultureInfo.InvariantCulture);
            unit = fr ? "Mo" : "MB";
        }
        else if (bytes >= 1024L)
        {
            number = (bytes / 1024d).ToString("0.#", CultureInfo.InvariantCulture);
            unit = fr ? "Ko" : "KB";
        }
        else
        {
            number = bytes.ToString(CultureInfo.InvariantCulture);
            unit = fr ? "o" : "B";
        }
        // French displays use a decimal comma, English a decimal point.
        if (fr)
            number = number.Replace('.', ',');
        return number + " " + unit;
    }
}
