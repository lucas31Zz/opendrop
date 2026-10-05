using System;
using System.IO;
using System.Runtime.CompilerServices;
using Xunit;

[assembly: CollectionBehavior(DisableTestParallelization = true)]

namespace OpenDrop.Tests;

// The desktop app reads its configuration from LOCALAPPDATA\OpenDrop, which
// also holds config.json: every test runs against a throw-away folder in the
// system temp directory, so the real configuration is never read or written.
internal static class TestInit
{
    internal static string Root { get; private set; } = "";
    internal static string OriginalLocalAppData { get; private set; } = "";

    [ModuleInitializer]
    internal static void RedirectConfiguration()
    {
        OriginalLocalAppData = Environment.GetEnvironmentVariable("LOCALAPPDATA") ?? "";
        Root = Path.Combine(Path.GetTempPath(),
            "opendrop-tests-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(Root);
        Environment.SetEnvironmentVariable("LOCALAPPDATA", Root);

        // Same for the update cache: the suites must never delete a real
        // partial download or write a real setup exit code.
        UpdateService.DownloadDir = Path.Combine(Root, "opendrop-update");
        Directory.CreateDirectory(UpdateService.DownloadDir);

        AppDomain.CurrentDomain.ProcessExit += (_, _) =>
        {
            try { Directory.Delete(Root, true); }
            catch { }
        };
    }
}
