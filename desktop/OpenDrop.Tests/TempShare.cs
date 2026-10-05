using System;
using System.IO;

namespace OpenDrop.Tests;

// A fresh share folder per test, removed with it.
internal sealed class TempShare : IDisposable
{
    public string Dir { get; }

    public TempShare()
    {
        Dir = Path.Combine(TestInit.Root, "share-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(Dir);
    }

    public string NewFile(string name, string content = "payload")
    {
        var path = Path.Combine(Dir, name);
        File.WriteAllText(path, content);
        return path;
    }

    public string[] Entries()
    {
        return Directory.GetFileSystemEntries(Dir)
            .Select(path => Path.GetFileName(path)!)
            .ToArray();
    }

    public void Dispose()
    {
        try { Directory.Delete(Dir, true); }
        catch { }
    }
}
