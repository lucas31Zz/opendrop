using System;
using System.Linq;
using System.Threading.Tasks;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.ApplicationLifetimes;

namespace OpenDrop;

// Single entry point for the two places that ask "is there a newer
// version?" (the main window at startup, the button in Settings): the
// dialogue, the "skip this version" rule and the install steps would
// otherwise drift apart.
internal static class UpdateRunner
{
    // Returns the text for the Settings status line, null when there is
    // nothing worth showing there (no update, update skipped, update done).
    public static async Task<string?> RunAsync(Window owner, bool interactive)
    {
        UpdateInfo? info;
        try
        {
            info = await UpdateService.CheckAsync();
        }
        catch (Exception ex)
        {
            var error = Lang.Format("Up.Error", ex.Message);
            if (interactive)
                await Msg.ShowAsync(owner, error, Lang.T("Update.Title"));
            return error;
        }

        if (info == null)
        {
            var upToDate = Lang.Format("Up.UpToDate", UpdateService.CurrentVersion);
            if (interactive)
                await Msg.ShowAsync(owner, upToDate, Lang.T("Update.Title"));
            return upToDate;
        }

        // A version the user decided to ignore stays quiet until a newer
        // one shows up.
        if (UpdateService.SkippedVersion == info.Version)
            return null;

        var choice = await Msg.ChoiceAsync(owner,
            Lang.Format("Up.Available", info.Version, UpdateService.CurrentVersion),
            Lang.T("Update.Title"),
            Lang.T("Up.Skip"), Lang.T("Up.Later"), Lang.T("Up.Install"));

        if (choice == 0)
        {
            UpdateService.SetSkippedVersion(info.Version);
            return null;
        }
        if (choice != 2)
            return null;

        return await ApplyAsync(owner, info);
    }

    private static async Task<string?> ApplyAsync(Window owner, UpdateInfo info)
    {
        var progress = Msg.Progress(owner, Lang.T("Update.Title"),
                                    Lang.Format("Up.Downloading", info.AssetName));
        try
        {
            var file = await UpdateService.DownloadAsync(
                info, progress.Report, progress.Token);
            progress.Title(Lang.T("Up.Installing"));

            if (OperatingSystem.IsWindows())
                UpdateService.ApplyWindows(file);
            else
                await UpdateService.ApplyLinuxAsync(file);

            progress.Close();
            await Msg.ShowAsync(owner, Lang.T("Up.Done"), Lang.T("Update.Title"));
            Shutdown();
            return null;
        }
        catch (OperationCanceledException)
        {
            // The user dismissed the progress window. Nothing is reported:
            // the partial file stays in %TEMP% and the next attempt
            // resumes it from where it stopped.
            progress.Close();
            return null;
        }
        catch (Exception ex)
        {
            progress.Close();
            var error = Lang.Format("Up.InstallError", ex.Message);
            await Msg.ShowAsync(owner, error, Lang.T("Update.Title"));
            return error;
        }
    }

    // Leaves through the normal path: the Closed handler of MainWindow
    // stops the Python server and drops the tray icon, and the helper
    // waiting on our PID (a PowerShell one on Windows, a shell loop on
    // Linux) takes over from there.
    private static void Shutdown()
    {
        if (Application.Current?.ApplicationLifetime
            is not IClassicDesktopStyleApplicationLifetime desktop)
            return;

        // Settings (or any other dialog) first: closing the main window
        // while a child is open would leave it behind.
        foreach (var window in desktop.Windows.OfType<Window>().ToArray())
        {
            if (window is not MainWindow)
                window.Close();
        }

        if (desktop.MainWindow is MainWindow main)
            main.ForceCloseForUpdate();
        else
            desktop.MainWindow?.Close();
    }
}
