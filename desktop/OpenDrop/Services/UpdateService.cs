using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

namespace OpenDrop;

// A candidate update, as described by one GitHub release asset.
internal sealed class UpdateInfo
{
    public required string Tag { get; init; }         // "v0.1.8"
    public required string Version { get; init; }     // "0.1.8"
    public required string AssetName { get; init; }   // "OpenDrop-v0.1.8-win-x64-setup.exe"
    public required string AssetUrl { get; init; }
    public long AssetSize { get; init; }
    public string? Digest { get; init; }              // "sha256:..." when published
    public string ReleaseUrl { get; init; } = "";
}

// Talks to GitHub Releases: is there a newer version than mine, and how do
// I apply it without asking the user to reinstall by hand.
//
// The rules are deliberately strict, because this code downloads and then
// executes a file:
//  - only /releases/latest, never a branch or a tag we pick ourselves;
//  - the tag is mandatory and must look like "vX.Y.Z" (an "untagged" or
//    free-form release is rejected, whatever its title says);
//  - a draft or a pre-release is never offered, checked twice (the endpoint
//    already filters them, the fields are read back anyway);
//  - the downloaded file must match the SHA-256 digest GitHub publishes
//    with the asset, when there is one.
internal static class UpdateService
{
    private const string ApiUrl = "https://api.github.com/repos/lucas31Zz/opendrop/releases/latest";

    // Short timeout for the metadata call; the download gets its own client
    // with no timeout at all (an 80 MB archive on a slow link is fine, a
    // stalled check after 20 s is not an error worth reporting).
    private static readonly HttpClient ApiHttp = CreateClient(TimeSpan.FromSeconds(20));
    private static readonly HttpClient DownloadHttp = CreateClient(Timeout.InfiniteTimeSpan);

    private static readonly Regex TagPattern =
        new(@"^v\d+\.\d+\.\d+$", RegexOptions.Compiled | RegexOptions.CultureInvariant);

    // "0.1.8" from the assembly version (csproj <Version>).
    public static string CurrentVersion { get; } = ReadCurrentVersion();

    private static HttpClient CreateClient(TimeSpan timeout)
    {
        var client = new HttpClient { Timeout = timeout };
        client.DefaultRequestHeaders.UserAgent.ParseAdd($"OpenDrop/{ReadCurrentVersion()}");
        client.DefaultRequestHeaders.Accept.Add(
            new MediaTypeWithQualityHeaderValue("application/vnd.github+json"));
        return client;
    }

    private static string ReadCurrentVersion()
    {
        try
        {
            var v = typeof(UpdateService).Assembly.GetName().Version;
            if (v != null)
                return $"{v.Major}.{v.Minor}.{Math.Max(v.Build, 0)}";
        }
        catch { }
        return "0.0.0";
    }

    // The asset this machine can install, or null on a platform we do not
    // ship for (macOS: no release asset exists).
    private static string AssetSuffix =>
        OperatingSystem.IsWindows() ? "-win-x64-setup.exe" :
        OperatingSystem.IsLinux() ? "-linux-x64.tar.gz" : "";

    // null = up to date (or nothing usable was published).
    // Throws on network/parse failure, so the caller can tell "no update"
    // from "could not check".
    public static async Task<UpdateInfo?> CheckAsync(CancellationToken ct = default)
    {
        using var response = await ApiHttp.GetAsync(ApiUrl, ct);
        response.EnsureSuccessStatusCode();

        await using var stream = await response.Content.ReadAsStreamAsync(ct);
        using var doc = await JsonDocument.ParseAsync(stream, cancellationToken: ct);
        var root = doc.RootElement;

        // Belt and braces: /releases/latest already excludes both, but an
        // updater must not depend on the endpoint staying that polite.
        if (TryBool(root, "draft") || TryBool(root, "prerelease"))
            return null;

        var tag = root.TryGetProperty("tag_name", out var tagEl)
            ? tagEl.GetString() ?? ""
            : "";
        if (!TagPattern.IsMatch(tag))
            return null;                       // no tag = no update

        var version = tag[1..];
        if (!IsNewer(version, CurrentVersion))
            return null;

        var suffix = AssetSuffix;
        if (suffix.Length == 0)
            return null;

        if (!root.TryGetProperty("assets", out var assets) ||
            assets.ValueKind != JsonValueKind.Array)
            return null;

        foreach (var asset in assets.EnumerateArray())
        {
            var name = asset.TryGetProperty("name", out var nameEl)
                ? nameEl.GetString() ?? ""
                : "";
            if (!name.EndsWith(suffix, StringComparison.OrdinalIgnoreCase))
                continue;

            var url = asset.TryGetProperty("browser_download_url", out var urlEl)
                ? urlEl.GetString() ?? ""
                : "";
            if (url.Length == 0)
                return null;

            return new UpdateInfo
            {
                Tag = tag,
                Version = version,
                AssetName = name,
                AssetUrl = url,
                AssetSize = asset.TryGetProperty("size", out var sizeEl) &&
                            sizeEl.TryGetInt64(out var size) ? size : 0,
                Digest = asset.TryGetProperty("digest", out var digestEl)
                    ? digestEl.GetString()
                    : null,
                ReleaseUrl = root.TryGetProperty("html_url", out var relEl)
                    ? relEl.GetString() ?? ""
                    : ""
            };
        }
        return null;
    }

    private static bool TryBool(JsonElement root, string name)
        => root.TryGetProperty(name, out var el) &&
           el.ValueKind == JsonValueKind.True;

    // Ordinal X.Y.Z comparison; an unparsable version is never an update.
    private static bool IsNewer(string candidate, string current)
    {
        if (!Version.TryParse(candidate, out var c)) return false;
        if (!Version.TryParse(current, out var cur)) return true;
        return c > cur;
    }

    // Downloads the asset to %TEMP%\opendrop-update and verifies it.
    public static async Task<string> DownloadAsync(
        UpdateInfo info,
        Action<long, long>? onProgress = null,
        CancellationToken ct = default)
    {
        var dir = Path.Combine(Path.GetTempPath(), "opendrop-update");
        Directory.CreateDirectory(dir);
        var path = Path.Combine(dir, info.AssetName);

        using var request = new HttpRequestMessage(HttpMethod.Get, info.AssetUrl);
        // GitHub answers with the file itself when the asset is requested
        // with this Accept header.
        request.Headers.Accept.Add(new MediaTypeWithQualityHeaderValue("application/octet-stream"));

        using var response = await DownloadHttp.SendAsync(
            request, HttpCompletionOption.ResponseHeadersRead, ct);
        response.EnsureSuccessStatusCode();

        var total = response.Content.Headers.ContentLength ?? info.AssetSize;
        await using (var source = await response.Content.ReadAsStreamAsync(ct))
        await using (var target = File.Create(path))
        {
            var buffer = new byte[81920];
            long done = 0;
            int read;
            while ((read = await source.ReadAsync(buffer.AsMemory(0, buffer.Length), ct)) > 0)
            {
                await target.WriteAsync(buffer.AsMemory(0, read), ct);
                done += read;
                onProgress?.Invoke(done, total);
            }
        }

        if (!VerifyDigest(path, info.Digest))
        {
            try { File.Delete(path); } catch (IOException) { }
            throw new InvalidDataException(Lang.T("Up.BadChecksum"));
        }
        return path;
    }

    private static bool VerifyDigest(string path, string? digest)
    {
        // No digest published (older releases): nothing to compare against,
        // the transport is still HTTPS with GitHub's certificate.
        if (string.IsNullOrWhiteSpace(digest)) return true;
        if (!digest.StartsWith("sha256:", StringComparison.OrdinalIgnoreCase)) return true;
        var expected = digest["sha256:".Length..].Trim();
        if (expected.Length != 64) return true;

        using var sha = SHA256.Create();
        using var stream = File.OpenRead(path);
        var actual = Convert.ToHexString(sha.ComputeHash(stream));
        return string.Equals(actual, expected, StringComparison.OrdinalIgnoreCase);
    }

    // ---- Windows ------------------------------------------------------
    // Inno Setup in silent mode: the new setup over the old installation
    // (same AppId => same folder, a single entry in the Programs list, the
    // old version is replaced, not added next to it). Settings live in
    // %LOCALAPPDATA%\OpenDrop, outside {app}, so the installer never sees
    // them.
    //
    // The installer cannot touch a running OpenDrop.exe, so a detached
    // helper waits for this process to exit (which also stops the Python
    // server through the Closed handler), runs the setup, then relaunches
    // the application from the very same path it was started from.
    public static void ApplyWindows(string installerPath)
    {
        var exe = Environment.ProcessPath
                  ?? Path.Combine(AppContext.BaseDirectory, "OpenDrop.exe");
        var pid = Environment.ProcessId;

        var script =
            $"Wait-Process -Id {pid} -Timeout 120; " +
            $"Start-Process -FilePath '{installerPath}' " +
            "-ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-' -Wait; " +
            $"if (Test-Path -LiteralPath '{exe}') {{ Start-Process -FilePath '{exe}' }}";

        if (Process.Start(new ProcessStartInfo
        {
            FileName = "powershell.exe",
            Arguments = $"-NoProfile -ExecutionPolicy Bypass -Command \"{script}\"",
            UseShellExecute = false,
            CreateNoWindow = true
        }) == null)
        {
            throw new InvalidOperationException("powershell.exe not found");
        }
    }

    // ---- Linux --------------------------------------------------------
    // Two cases, decided by where this binary lives:
    //  - a writable folder (extracted archive run by hand): the files are
    //    replaced in place, then the dependencies are refreshed from the
    //    bundled wheels;
    //  - /opt/opendrop (install.sh): root is required, so the bundled
    //    install.sh is run through pkexec, the standard polkit password
    //    dialog on a desktop (Kali/GNOME included).
    // Either way ~/.opendrop (config, session, certificates) and the
    // receive/share folders are outside the prefix and stay untouched.
    public static async Task ApplyLinuxAsync(
        string tarballPath, CancellationToken ct = default)
    {
        var work = Path.Combine(Path.GetTempPath(), "opendrop-update",
                                "extract-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(work);

        await using (var file = File.OpenRead(tarballPath))
        await using (var gz = new GZipStream(file, CompressionMode.Decompress))
        {
            System.Formats.Tar.TarFile.ExtractToDirectory(gz, work, overwriteFiles: true);
        }

        var bundle = Path.Combine(work, "OpenDrop");
        if (!File.Exists(Path.Combine(bundle, "src", "opendrop", "main.py")))
            throw new InvalidDataException(Lang.T("Up.BadArchive"));

        var current = Environment.ProcessPath ?? "";
        var appDir = Path.GetDirectoryName(current) ?? "";

        if (IsWritable(appDir) && File.Exists(Path.Combine(bundle, "OpenDrop")))
        {
            ReplaceInPlace(appDir, bundle);
            await RefreshDependenciesAsync(appDir, bundle, ct);
            RelaunchWhenGone(current);
        }
        else
        {
            var script = Path.Combine(bundle, "install.sh");
            EnsureExecutable(script);
            await RunElevatedAsync(script, ct);
            RelaunchWhenGone(current);
        }

        try { Directory.Delete(work, recursive: true); } catch (IOException) { }
        catch (UnauthorizedAccessException) { }
    }

    private static bool IsWritable(string dir)
    {
        if (string.IsNullOrEmpty(dir)) return false;
        try
        {
            var probe = Path.Combine(dir, ".opendrop-write-test");
            File.WriteAllText(probe, "1");
            File.Delete(probe);
            return true;
        }
        catch (Exception)
        {
            return false;
        }
    }

    // A file that is being executed cannot be opened for writing (ETXTBSY):
    // the running binary is renamed first, the new copy lands on a fresh
    // inode and the old process keeps running until it exits by itself.
    private static void ReplaceInPlace(string appDir, string bundle)
    {
        var current = Environment.ProcessPath ?? "";
        if (current.StartsWith(appDir, StringComparison.Ordinal))
        {
            try
            {
                var aside = current + ".old";
                if (File.Exists(aside)) File.Delete(aside);
                File.Move(current, aside);
            }
            catch (Exception)
            {
                // Not fatal: the copy below reports the real error.
            }
        }

        foreach (var entry in Directory.GetFileSystemEntries(bundle))
        {
            var name = Path.GetFileName(entry);
            var destination = Path.Combine(appDir, name);
            if (Directory.Exists(entry))
            {
                CopyDirectory(entry, destination);
            }
            else
            {
                File.Copy(entry, destination, overwrite: true);
            }
        }
    }

    private static void CopyDirectory(string source, string destination)
    {
        Directory.CreateDirectory(destination);
        foreach (var file in Directory.GetFiles(source))
            File.Copy(file, Path.Combine(destination, Path.GetFileName(file)), overwrite: true);
        foreach (var sub in Directory.GetDirectories(source))
            CopyDirectory(sub, Path.Combine(destination, Path.GetFileName(sub)));
    }

    // Same job as install.sh does at install time: the wheels are bundled
    // next to the sources, so no network is needed and no index is queried.
    private static async Task RefreshDependenciesAsync(
        string appDir, string bundle, CancellationToken ct)
    {
        var pip = Path.Combine(appDir, "venv",
            OperatingSystem.IsWindows() ? "Scripts" : "bin", "pip");
        if (!File.Exists(pip)) return;

        var wheels = Path.Combine(bundle, "wheels");
        var requirements = Path.Combine(appDir, "requirements.txt");
        if (!Directory.Exists(wheels) || !File.Exists(requirements)) return;

        var start = new ProcessStartInfo
        {
            FileName = pip,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true
        };
        start.ArgumentList.Add("install");
        start.ArgumentList.Add("--quiet");
        start.ArgumentList.Add("--no-index");
        start.ArgumentList.Add("--find-links");
        start.ArgumentList.Add(wheels);
        start.ArgumentList.Add("--requirement");
        start.ArgumentList.Add(requirements);

        using var process = Process.Start(start);
        if (process == null) return;
        await process.WaitForExitAsync(ct);
    }

    private static void EnsureExecutable(string path)
    {
        if (!OperatingSystem.IsLinux() && !OperatingSystem.IsMacOS()) return;
        try
        {
            File.SetUnixFileMode(path,
                File.GetUnixFileMode(path) |
                UnixFileMode.UserExecute | UnixFileMode.GroupExecute | UnixFileMode.OtherExecute);
        }
        catch (Exception) { }
    }

    private static async Task RunElevatedAsync(string script, CancellationToken ct)
    {
        // pkexec = graphical polkit agent (password prompt in a dialog).
        // The script needs an absolute path: pkexec refuses a relative one.
        var start = new ProcessStartInfo
        {
            FileName = "pkexec",
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true
        };
        start.ArgumentList.Add(script);

        try
        {
            using var process = Process.Start(start)
                ?? throw new InvalidOperationException("pkexec not found");
            var stderr = await process.StandardError.ReadToEndAsync(ct);
            await process.WaitForExitAsync(ct);
            if (process.ExitCode != 0)
                throw new InvalidOperationException(
                    string.IsNullOrWhiteSpace(stderr) ? $"pkexec ({process.ExitCode})" : stderr.Trim());
        }
        catch (System.ComponentModel.Win32Exception)
        {
            throw new InvalidOperationException(Lang.T("Up.NoPolkit"));
        }
    }

    // The new process must start only once this one is gone, otherwise the
    // single-instance mutex (Program.cs) makes it hand the "show" signal
    // back to us and quit. A detached shell waits for the PID instead.
    private static void RelaunchWhenGone(string executable)
    {
        if (string.IsNullOrEmpty(executable)) return;
        var pid = Environment.ProcessId;
        var script = $"while kill -0 {pid} 2>/dev/null; do sleep 0.2; done; exec \"{executable}\"";

        try
        {
            var start = new ProcessStartInfo
            {
                FileName = "/bin/sh",
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                RedirectStandardInput = true
            };
            start.ArgumentList.Add("-c");
            start.ArgumentList.Add(script);
            Process.Start(start);
        }
        catch (Exception)
        {
            // The update is already installed; a missing auto-restart only
            // costs the user one manual launch.
        }
    }

    // ---- "Skip this version" ------------------------------------------
    // Stored in config.json so it survives a restart and is kept when
    // Settings rewrites the file (the whole dictionary is copied first).
    public static string? SkippedVersion => ReadConfigValue("skip_version");

    public static void SetSkippedVersion(string version) => WriteConfigValue("skip_version", version);

    private static string? ReadConfigValue(string key)
    {
        try
        {
            var path = QuotaUsage.ConfigPath;
            if (!File.Exists(path)) return null;
            using var doc = JsonDocument.Parse(File.ReadAllText(path));
            return doc.RootElement.TryGetProperty(key, out var value)
                ? value.GetString()
                : null;
        }
        catch (Exception)
        {
            return null;
        }
    }

    private static void WriteConfigValue(string key, string value)
    {
        try
        {
            var path = QuotaUsage.ConfigPath;
            var values = new System.Collections.Generic.Dictionary<string, JsonElement>();
            if (File.Exists(path))
            {
                try
                {
                    using var doc = JsonDocument.Parse(File.ReadAllText(path));
                    foreach (var property in doc.RootElement.EnumerateObject())
                        values[property.Name] = property.Value.Clone();
                }
                catch (JsonException) { }
            }

            using var stream = new MemoryStream();
            using (var writer = new Utf8JsonWriter(stream, new JsonWriterOptions { Indented = true }))
            {
                writer.WriteStartObject();
                foreach (var pair in values)
                {
                    if (pair.Key == key) continue;   // replaced below
                    writer.WritePropertyName(pair.Key);
                    pair.Value.WriteTo(writer);
                }
                writer.WriteString(key, value);
                writer.WriteEndObject();
            }

            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            File.WriteAllBytes(path, stream.ToArray());
        }
        catch (Exception)
        {
            // Failing to remember "never ask again" is not worth breaking
            // the update itself.
        }
    }
}
