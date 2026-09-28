using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;

namespace OpenDrop;

// Remembers where a file was before it was moved into the share folder, so
// the "Put back" button can return it. Stored in moves.json next to
// config.json as { "<path in the share folder>": "<original path>" }, and
// cleaned up as soon as the file is deleted, put back or moved elsewhere.
internal static class MoveRegistry
{
    private static readonly object Sync = new();

    private static string StorePath => Path.Combine(QuotaUsage.ConfigDir, "moves.json");

    public static Dictionary<string, string> Load()
    {
        var map = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        try
        {
            if (!File.Exists(StorePath)) return map;

            using var doc = JsonDocument.Parse(File.ReadAllText(StorePath));
            if (doc.RootElement.ValueKind != JsonValueKind.Object) return map;

            foreach (var property in doc.RootElement.EnumerateObject())
            {
                if (property.Value.ValueKind != JsonValueKind.String) continue;
                var origin = property.Value.GetString();
                if (!string.IsNullOrWhiteSpace(origin))
                    map[property.Name] = origin;
            }
        }
        catch { }
        return map;
    }

    public static void Record(string sharePath, string origin)
    {
        if (string.IsNullOrWhiteSpace(sharePath) || string.IsNullOrWhiteSpace(origin)) return;
        Update(map => map[sharePath] = origin);
    }

    // The file left the share folder by itself: nothing to put back.
    public static void Forget(string sharePath)
    {
        if (string.IsNullOrWhiteSpace(sharePath)) return;
        Update(map => map.Remove(sharePath));
    }

    public static void Rename(string oldPath, string newPath)
    {
        if (string.IsNullOrWhiteSpace(oldPath) || string.IsNullOrWhiteSpace(newPath)) return;
        Update(map =>
        {
            if (!map.Remove(oldPath, out var origin)) return;
            map[newPath] = origin;
        });
    }

    // The map is tiny: a whole read-modify-write is cheaper than any
    // invalidation logic, and the file is only touched from the UI thread.
    private static void Update(Action<Dictionary<string, string>> change)
    {
        lock (Sync)
        {
            var map = Load();
            change(map);
            try
            {
                Directory.CreateDirectory(QuotaUsage.ConfigDir);
                File.WriteAllText(StorePath,
                    JsonSerializer.Serialize(map, new JsonSerializerOptions { WriteIndented = true }));
            }
            catch { }
        }
    }
}
