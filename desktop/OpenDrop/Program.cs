using System;
using Avalonia;

namespace OpenDrop;

internal static class Program
{
    [STAThread]
    public static int Main(string[] args)
    {
        // Update worker: replaces the application files and restarts the
        // program. Started from the staged payload, no window, no server.
        if (args.Length >= 5 && args[0] == "--apply-update")
            return UpdateApplier.Run(args[1], args[2], args[3], args[4]);

        BuildAvaloniaApp().StartWithClassicDesktopLifetime(args);
        return 0;
    }

    public static AppBuilder BuildAvaloniaApp()
        => AppBuilder.Configure<App>()
            .UsePlatformDetect()
            .LogToTrace();
}
