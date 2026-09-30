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
        // Update worker: replaces the application files and restarts the
        // program. Started from the staged payload, no window, no server.
        if (args.Length >= 5 && args[0] == "--apply-update")
            return UpdateApplier.Run(args[1], args[2], args[3], args[4]);

        // Single-instance via named mutex (robust, no race conditions)
        bool createdNew;
        _singleInstanceMutex = new Mutex(true, MutexName, out createdNew);

        if (!createdNew)
        {
            // Another instance is running: signal it to show and exit
            if (TrySignalExistingInstance())
                return 0;
            // If signaling failed, fall through and run anyway (fallback)
            Console.WriteLine("[Main] Another instance exists but signaling failed, continuing anyway");
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
            Console.WriteLine("[PipeClient] Connecting to pipe...");
            using var client = new NamedPipeClientStream(".", "OpenDrop.SingleInstance", PipeDirection.InOut);
            client.Connect(1000);
            Console.WriteLine("[PipeClient] Connected, sending SHOW...");
            var msg = Encoding.UTF8.GetBytes("SHOW\n");
            client.Write(msg, 0, msg.Length);
            client.Flush();
            Console.WriteLine("[PipeClient] Sent SHOW, waiting for ACK...");
            
            var buffer = new byte[256];
            int bytesRead = client.Read(buffer, 0, buffer.Length);
            var response = Encoding.UTF8.GetString(buffer, 0, bytesRead).Trim();
            Console.WriteLine($"[PipeClient] Received: '{response}'");
            return response == "OK";
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[PipeClient] Failed: {ex.Message}");
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

                    Console.WriteLine("[PipeServer] Waiting for connection...");
                    await server.WaitForConnectionAsync(_pipeCts.Token);
                    Console.WriteLine("[PipeServer] Client connected");

                    var buffer = new byte[256];
                    int bytesRead = await server.ReadAsync(buffer, 0, buffer.Length, _pipeCts.Token);
                    var request = Encoding.UTF8.GetString(buffer, 0, bytesRead).Trim();
                    Console.WriteLine($"[PipeServer] Received: '{request}'");

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
                        Console.WriteLine("[PipeServer] Sent OK");
                    }
                }
                catch (OperationCanceledException)
                {
                    Console.WriteLine("[PipeServer] Cancelled");
                    break;
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"[PipeServer] Error: {ex.Message}");
                }
                finally
                {
                    server?.Dispose();
                    Console.WriteLine("[PipeServer] Disposed, looping...");
                }
            }
        }, _pipeCts.Token);
    }

    public static AppBuilder BuildAvaloniaApp()
        => AppBuilder.Configure<App>()
            .UsePlatformDetect()
            .LogToTrace();
}