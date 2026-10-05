using System;
using System.Net;
using System.Text;
using System.Threading;

namespace OpenDrop.Tests;

// Minimal local HTTP server for the update suites: /release answers the
// GitHub-shaped JSON, every other path is the asset, with the Range
// behaviour the downloader has to cope with.
internal sealed class FakeReleaseServer : IDisposable
{
    internal enum RangeMode
    {
        HonorRange,
        IgnoreRange,
        Always416,
    }

    private readonly HttpListener _listener;
    private readonly Thread _thread;
    private readonly object _sync = new();
    private volatile bool _stopping;

    public string Json { get; set; } = "{}";
    public byte[] Asset { get; set; } = Array.Empty<byte>();
    public RangeMode Mode { get; set; } = RangeMode.HonorRange;
    // Status for the /release answer: 500 simulates a broken API.
    public int StatusCode { get; set; } = 200;

    public string BaseUrl { get; }

    public int Requests { get; private set; }
    public string? LastRange { get; private set; }
    public string? LastPath { get; private set; }

    public FakeReleaseServer()
    {
        HttpListener? listener = null;
        string? baseUrl = null;

        for (var attempt = 0; attempt < 50 && listener == null; attempt++)
        {
            var port = Random.Shared.Next(20000, 60000);
            var candidate = new HttpListener();
            candidate.Prefixes.Add($"http://127.0.0.1:{port}/");
            try
            {
                candidate.Start();
                listener = candidate;
                baseUrl = $"http://127.0.0.1:{port}";
            }
            catch (HttpListenerException)
            {
                candidate.Close();
            }
        }

        if (listener == null || baseUrl == null)
            throw new InvalidOperationException("No free port for the fake release server");

        _listener = listener;
        BaseUrl = baseUrl;
        _thread = new Thread(Loop) { IsBackground = true };
        _thread.Start();
    }

    public void Dispose()
    {
        _stopping = true;
        try { _listener.Stop(); } catch { }
        try { _listener.Close(); } catch { }
        _thread.Join(TimeSpan.FromSeconds(5));
    }

    private void Loop()
    {
        while (!_stopping)
        {
            HttpListenerContext context;
            try { context = _listener.GetContext(); }
            catch { break; }

            try { Handle(context); }
            catch
            {
                try { context.Response.Abort(); } catch { }
            }
        }
    }

    private void Handle(HttpListenerContext context)
    {
        var range = context.Request.Headers["Range"];
        lock (_sync)
        {
            Requests++;
            LastRange = range;
            LastPath = context.Request.Url?.AbsolutePath;
        }

        if (context.Request.Url?.AbsolutePath == "/release")
        {
            var body = Encoding.UTF8.GetBytes(Json);
            context.Response.StatusCode = StatusCode;
            context.Response.ContentType = "application/json";
            context.Response.ContentLength64 = body.Length;
            context.Response.OutputStream.Write(body, 0, body.Length);
            context.Response.Close();
            return;
        }

        ServeAsset(context, range);
    }

    private void ServeAsset(HttpListenerContext context, string? range)
    {
        var asset = Asset;
        var start = 0L;
        var status = 200;

        if (range != null)
        {
            if (Mode == RangeMode.Always416)
            {
                SendEmpty(context, 416, asset.Length);
                return;
            }
            if (Mode == RangeMode.HonorRange && TryParseStart(range, out start) &&
                start >= asset.Length)
            {
                SendEmpty(context, 416, asset.Length);
                return;
            }
            if (Mode == RangeMode.HonorRange)
                status = 206;
        }

        var length = asset.Length - start;
        context.Response.StatusCode = status;
        context.Response.ContentType = "application/octet-stream";
        if (status == 206)
            TrySetHeader(context.Response, "Content-Range",
                $"bytes {start}-{asset.Length - 1}/{asset.Length}");
        context.Response.ContentLength64 = length;
        context.Response.OutputStream.Write(asset, (int)start, (int)length);
        context.Response.Close();
    }

    private static void SendEmpty(HttpListenerContext context, int status, long size)
    {
        context.Response.StatusCode = status;
        TrySetHeader(context.Response, "Content-Range", $"bytes */{size}");
        context.Response.ContentLength64 = 0;
        context.Response.Close();
    }

    private static void TrySetHeader(HttpListenerResponse response, string name, string value)
    {
        try { response.Headers[name] = value; }
        catch (ArgumentException) { }
    }

    private static bool TryParseStart(string range, out long start)
    {
        start = 0;
        if (!range.StartsWith("bytes=", StringComparison.Ordinal)) return false;
        var spec = range["bytes=".Length..];
        var dash = spec.IndexOf('-');
        if (dash <= 0) return false;
        return long.TryParse(spec[..dash], out start);
    }
}
