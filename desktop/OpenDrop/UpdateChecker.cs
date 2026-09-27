using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Xml.Linq;
using Avalonia.Controls;

namespace OpenDrop;

// Update check for Windows: reads update.xml from the public updates repo,
// compares with the assembly version, verifies the SHA-256 of the new setup,
// and offers to download + launch it. The setup reinstalls into Program
// Files only; %LOCALAPPDATA% (config, session, certs) is never touched.
internal static class UpdateChecker
{
    private const string ManifestUrl =
        "https://raw.githubusercontent.com/lucas31Zz/opendrop-updates/main/update.xml";

    private static readonly HttpClient _http = new(new HttpClientHandler
    {
        UseProxy = false,
        AllowAutoRedirect = false
    })
    { Timeout = TimeSpan.FromSeconds(15) };

    // Called once at startup (Windows only).
    public static async void CheckAsync(object owner)
    {
        try
        {
            var xml = await _http.GetStringAsync(ManifestUrl);
            var root = XDocument.Parse(xml).Root;
            if (root == null) return;

            var latest = root.Element("version")?.Value?.Trim();
            var setupUrl = root.Element("url")?.Value?.Trim();
            var expectedHash = root.Element("sha256")?.Value?.Trim();
            if (string.IsNullOrEmpty(latest) || string.IsNullOrEmpty(setupUrl)) return;

            var current = typeof(UpdateChecker).Assembly.GetName().Version;
            if (current == null || !Version.TryParse(latest, out var latestVer)) return;
            if (latestVer <= current) return;

            // Defer until the owner window is shown.
            if (owner is Window w)
            {
                async void Show()
                {
                    var answer = await Msg.ConfirmAsync(w,
                        Lang.Format("Update.Available", current.ToString(), latest),
                        Lang.T("Update.Title"));
                    if (!answer) return;
                    var dest = Path.Combine(Path.GetTempPath(),
                        "OpenDrop-" + latest + "-win-x64-setup.exe");
                    if (!await DownloadAndVerifyAsync(setupUrl, dest, expectedHash))
                    {
                        await Msg.ShowAsync(w, Lang.T("Update.Failed"), Lang.T("Update.Title"));
                        return;
                    }
                    try
                    {
                        // The installer detects the running app (CloseApplications=yes)
                        // and closes it itself.
                        Process.Start(new ProcessStartInfo(dest) { UseShellExecute = true });
                    }
                    catch
                    {
                        Process.Start(new ProcessStartInfo(setupUrl) { UseShellExecute = true });
                    }
                }

                if (w.IsVisible)
                    Show();
                else
                    w.Opened += (_, _) => Show();
            }
        }
        catch { }
    }

    private static async Task<bool> DownloadAndVerifyAsync(
        string setupUrl, string dest, string? expectedHash)
    {
        try
        {
            using var response = await _http.GetAsync(setupUrl);
            response.EnsureSuccessStatusCode();
            await using var fs = new FileStream(dest, FileMode.Create, FileAccess.Write);
            await response.Content.CopyToAsync(fs);
        }
        catch
        {
            return false;
        }

        if (!string.IsNullOrEmpty(expectedHash))
        {
            try
            {
                await using var fs = File.OpenRead(dest);
                var hash = Convert.ToHexString(SHA256.HashData(fs));
                if (!string.Equals(hash, expectedHash, StringComparison.OrdinalIgnoreCase))
                {
                    File.Delete(dest);
                    return false;
                }
            }
            catch
            {
                return false;
            }
        }
        return true;
    }
}

