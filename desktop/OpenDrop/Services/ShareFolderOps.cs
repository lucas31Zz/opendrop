using System;
using System.Collections.Generic;
using System.IO;

namespace OpenDrop;

// Result of a rename inside the share folder. The window turns every value
// into its own localized dialog, so this file needs no Avalonia and no Lang
// and can be exercised by the test project as it is.
internal enum RenameOutcome
{
    Ok,
    NoChange,
    InvalidName,
    AlreadyExists,
    Failed,
}

internal static class ShareFolderOps
{
    public static RenameOutcome Rename(string dir, string sourceFullPath,
                                       string newName, out string? error)
    {
        error = null;
        newName = newName.Trim();
        if (newName.Length == 0)
            return RenameOutcome.NoChange;

        if (string.Equals(newName, Path.GetFileName(sourceFullPath), StringComparison.Ordinal))
            return RenameOutcome.NoChange;

        if (newName.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0)
            return RenameOutcome.InvalidName;

        var sourceFull = Path.GetFullPath(sourceFullPath);
        var target = Path.Combine(dir, newName);
        var targetFull = Path.GetFullPath(target);

        if (TargetTaken(sourceFull, targetFull, target))
            return RenameOutcome.AlreadyExists;

        try
        {
            // Renames the real file in the share folder, not a copy.
            File.Move(sourceFullPath, target);
        }
        catch (Exception ex)
        {
            error = ex.Message;
            return RenameOutcome.Failed;
        }

        MoveRegistry.Rename(sourceFullPath, target);
        return RenameOutcome.Ok;
    }

    // A target that differs only by case is our own file on Windows, where
    // the filesystem ignores case: the rename then only changes the case.
    // On a case-sensitive filesystem the same name can belong to a second,
    // unrelated file, which must stay refused.
    private static bool TargetTaken(string sourceFull, string targetFull, string target)
    {
        var caseOnly = string.Equals(targetFull, sourceFull, StringComparison.OrdinalIgnoreCase);
        if (caseOnly && OperatingSystem.IsWindows())
            return false;
        return File.Exists(target);
    }

    // Returns how many files could not be removed; the rest are gone.
    public static int Delete(IReadOnlyList<string> paths)
    {
        var failed = 0;
        foreach (var path in paths)
        {
            try
            {
                File.Delete(path);
                MoveRegistry.Forget(path);
            }
            catch { failed++; }
        }
        return failed;
    }
}
