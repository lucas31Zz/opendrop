using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Xml.Linq;
using Avalonia.Controls;

namespace OpenDrop;

// Update check for Windows: reads update.xml from GitHub, compares with
// the assembly version, and offers to download + launch the new setup.
// The setup reinstalls into Program Files only; %LOCALAPPDATA% (config,
// session, certs) is never touched.
internal static class UpdateChecker
{
    private static readonly HttpClient _http = new(new HttpClientHandler
    {
        UseProxy = false,
        AllowAutoRedirect = false
    })
    { Timeout = TimeSpan.FromSeconds(8) };

    // Called once at startup (Windows only).
    public static async void CheckAsync(object owner)
    {
        try
        {
            var req = new HttpRequestMessage(HttpMethod.Get,
                "https://raw.githubusercontent.com/lucas31Zz/opendrop/main/update.xml");
            req.Headers.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue(
                "Bearer", "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");
            using var resp = await _http.SendAsync(req);
            resp.EnsureSuccessStatusCode();
            var xml = await resp.Content.ReadAsStringAsync();
            var root = XDocument.Parse(xml).Root;
            if (root == null) return;

            var latest = root.Element("version")?.Value?.Trim();
            var setupUrl = root.Element("url")?.Value?.Trim();
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
                    await DownloadAndLaunchAsync(setupUrl, dest);
                }

                if (w.IsVisible)
                    Show();
                else
                    w.Opened += (_, _) => Show();
            }
        }
        catch { }
    }

    private static async Task DownloadAndLaunchAsync(string setupUrl, string dest)
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
            Process.Start(new ProcessStartInfo(setupUrl) { UseShellExecute = true });
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
}
