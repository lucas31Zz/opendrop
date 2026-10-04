using System;
using System.IO.Pipes;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Avalonia;

namespace OpenDrop;

internal static class Program
{
    private const string MutexName = "Global\\OpenDrop.SingleInstance";
    private const string PipeName = "OpenDrop.SingleInstance";
    private static readonly CancellationTokenSource _pipeCts = new();
    private static Task? _pipeServerTask;
    private static Mutex? _singleInstanceMutex;

    [STAThread]
    public static int Main(string[] args)
    {
        // Single-instance via named mutex (robust, no race conditions)
        bool createdNew;
        _singleInstanceMutex = new Mutex(true, MutexName, out createdNew);

        if (!createdNew)
        {
            // Another instance is running: signal it to show and exit
            if (TrySignalExistingInstance())
                return 0;
            // If signaling failed, fall through and run anyway (fallback)
        }

        // We're the first instance: start pipe server and run the app
        StartPipeServer();
        try
        {
            BuildAvaloniaApp().StartWithClassicDesktopLifetime(args);
        }
        finally
        {
            _pipeCts.Cancel();
            _pipeServerTask?.Wait(TimeSpan.FromSeconds(1));
            _singleInstanceMutex?.ReleaseMutex();
            _singleInstanceMutex?.Dispose();
        }
        return 0;
    }

    private static bool TrySignalExistingInstance()
    {
        try
        {
            using var client = new NamedPipeClientStream(".", "OpenDrop.SingleInstance", PipeDirection.InOut);
            client.Connect(1000);
            var msg = Encoding.UTF8.GetBytes("SHOW\n");
            client.Write(msg, 0, msg.Length);
            client.Flush();

            var buffer = new byte[256];
            int bytesRead = client.Read(buffer, 0, buffer.Length);
            var response = Encoding.UTF8.GetString(buffer, 0, bytesRead).Trim();
            return response == "OK";
        }
        catch (Exception)
        {
            return false;
        }
    }

    private static void StartPipeServer()
    {
        _pipeServerTask = Task.Run(async () =>
        {
            while (!_pipeCts.Token.IsCancellationRequested)
            {
                NamedPipeServerStream? server = null;
                try
                {
                    server = new NamedPipeServerStream(
                        "OpenDrop.SingleInstance",
                        PipeDirection.InOut,
                        1,
                        PipeTransmissionMode.Byte,
                        PipeOptions.Asynchronous);

                    await server.WaitForConnectionAsync(_pipeCts.Token);

                    var buffer = new byte[256];
                    int bytesRead = await server.ReadAsync(buffer, 0, buffer.Length, _pipeCts.Token);
                    var request = Encoding.UTF8.GetString(buffer, 0, bytesRead).Trim();

                    if (request == "SHOW")
                    {
                        // Signal UI thread to show window
                        if (Avalonia.Application.Current != null)
                        {
                            Avalonia.Threading.Dispatcher.UIThread.Post(() =>
                            {
                                if (Avalonia.Application.Current?.ApplicationLifetime is Avalonia.Controls.ApplicationLifetimes.IClassicDesktopStyleApplicationLifetime desktop)
                                {
                                    foreach (var window in desktop.Windows)
                                    {
                                        if (window is MainWindow mw)
                                        {
                                            mw.ShowFromTray();
                                            break;
                                        }
                                    }
                                }
                            });
                        }

                        var response = Encoding.UTF8.GetBytes("OK\n");
                        await server.WriteAsync(response, 0, response.Length, _pipeCts.Token);
                        await server.FlushAsync(_pipeCts.Token);
                    }
                }
                catch (OperationCanceledException)
                {
                    break;
                }
                catch (Exception)
                {
                }
                finally
                {
                    server?.Dispose();
                }
            }
        }, _pipeCts.Token);
    }

    public static AppBuilder BuildAvaloniaApp()
        => AppBuilder.Configure<App>()
            .UsePlatformDetect()
            .LogToTrace();
}