using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Xunit;

namespace OpenDrop.Tests;

public class ShareFolderOpsTests
{
    // --- Rename ---------------------------------------------------------

    [Fact]
    public void Rename_moves_the_file_and_keeps_its_content()
    {
        using var share = new TempShare();
        var source = share.NewFile("report.txt", "hello");

        var outcome = ShareFolderOps.Rename(share.Dir, source, "invoice.txt", out var error);

        Assert.Equal(RenameOutcome.Ok, outcome);
        Assert.Null(error);
        Assert.Equal(new[] { "invoice.txt" }, share.Entries());
        Assert.Equal("hello", File.ReadAllText(Path.Combine(share.Dir, "invoice.txt")));
    }

    [Fact]
    public void Rename_moves_the_move_registry_entry()
    {
        using var share = new TempShare();
        var source = share.NewFile("report.txt");
        var origin = Path.Combine(TestInit.Root, "origin", "report.txt");
        MoveRegistry.Record(source, origin);

        var outcome = ShareFolderOps.Rename(share.Dir, source, "invoice.txt", out _);

        Assert.Equal(RenameOutcome.Ok, outcome);
        var map = MoveRegistry.Load();
        Assert.False(map.ContainsKey(source));
        Assert.Equal(origin, map[Path.Combine(share.Dir, "invoice.txt")]);
    }

    [Fact]
    public void Rename_refuses_a_name_already_taken()
    {
        using var share = new TempShare();
        var source = share.NewFile("report.txt", "mine");
        share.NewFile("invoice.txt", "theirs");

        var outcome = ShareFolderOps.Rename(share.Dir, source, "invoice.txt", out var error);

        Assert.Equal(RenameOutcome.AlreadyExists, outcome);
        Assert.Null(error);
        Assert.Equal("mine", File.ReadAllText(source));
        Assert.Equal("theirs", File.ReadAllText(Path.Combine(share.Dir, "invoice.txt")));
    }

    [Fact]
    public void Rename_refuses_a_name_with_forbidden_characters()
    {
        using var share = new TempShare();
        var source = share.NewFile("report.txt");

        var outcome = ShareFolderOps.Rename(share.Dir, source, "sub/report.txt", out var error);

        Assert.Equal(RenameOutcome.InvalidName, outcome);
        Assert.Null(error);
        Assert.True(File.Exists(source));
    }

    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    [InlineData("report.txt")]
    public void Rename_changes_nothing_when_the_name_stays_the_same(string name)
    {
        using var share = new TempShare();
        var source = share.NewFile("report.txt");

        var outcome = ShareFolderOps.Rename(share.Dir, source, name, out var error);

        Assert.Equal(RenameOutcome.NoChange, outcome);
        Assert.Null(error);
        Assert.Equal(new[] { "report.txt" }, share.Entries());
    }

    [Fact]
    public void Rename_reports_the_error_when_the_source_is_gone()
    {
        using var share = new TempShare();
        var source = share.NewFile("report.txt");
        File.Delete(source);

        var outcome = ShareFolderOps.Rename(share.Dir, source, "invoice.txt", out var error);

        Assert.Equal(RenameOutcome.Failed, outcome);
        Assert.False(string.IsNullOrEmpty(error));
        Assert.Empty(share.Entries());
    }

    [Fact]
    public void Rename_changes_only_the_case_of_the_name()
    {
        using var share = new TempShare();
        var source = share.NewFile("report.txt", "content");

        var outcome = ShareFolderOps.Rename(share.Dir, source, "REPORT.TXT", out var error);

        Assert.Equal(RenameOutcome.Ok, outcome);
        Assert.Null(error);
        Assert.Equal(new[] { "REPORT.TXT" }, share.Entries());
        Assert.Equal("content", File.ReadAllText(Path.Combine(share.Dir, "REPORT.TXT")));
    }

    [Fact]
    public void Rename_refuses_a_case_variant_owned_by_another_file()
    {
        // Windows cannot hold two names differing only by case, so the
        // fixture itself only exists on a case-sensitive filesystem.
        if (OperatingSystem.IsWindows()) return;

        using var share = new TempShare();
        share.NewFile("report.txt", "mine");
        share.NewFile("REPORT.TXT", "theirs");
        var source = Path.Combine(share.Dir, "report.txt");

        var outcome = ShareFolderOps.Rename(share.Dir, source, "REPORT.TXT", out _);

        Assert.Equal(RenameOutcome.AlreadyExists, outcome);
        Assert.Equal("mine", File.ReadAllText(source));
        Assert.Equal("theirs", File.ReadAllText(Path.Combine(share.Dir, "REPORT.TXT")));
    }

    // --- Delete ---------------------------------------------------------

    [Fact]
    public void Delete_removes_the_file()
    {
        using var share = new TempShare();
        var source = share.NewFile("report.txt");

        var failed = ShareFolderOps.Delete(new[] { source });

        Assert.Equal(0, failed);
        Assert.Empty(share.Entries());
    }

    [Fact]
    public void Delete_forgets_the_move_registry_entry()
    {
        using var share = new TempShare();
        var source = share.NewFile("report.txt");
        MoveRegistry.Record(source, Path.Combine(TestInit.Root, "origin", "report.txt"));

        var failed = ShareFolderOps.Delete(new[] { source });

        Assert.Equal(0, failed);
        Assert.False(MoveRegistry.Load().ContainsKey(source));
    }

    [Fact]
    public void Delete_counts_the_paths_it_could_not_remove()
    {
        using var share = new TempShare();
        var good = share.NewFile("report.txt");
        // A directory: both platforms refuse to delete it as a file, which is
        // exactly the "one entry failed, the others still go" path.
        var undeletable = Path.Combine(share.Dir, "folder");
        Directory.CreateDirectory(undeletable);

        var failed = ShareFolderOps.Delete(new List<string> { good, undeletable });

        Assert.Equal(1, failed);
        Assert.False(File.Exists(good));
        Assert.True(Directory.Exists(undeletable));
    }

    [Fact]
    public void Delete_ignores_a_file_that_is_already_gone()
    {
        using var share = new TempShare();
        var ghost = Path.Combine(share.Dir, "ghost.txt");

        var failed = ShareFolderOps.Delete(new[] { ghost });

        Assert.Equal(0, failed);
    }

    // --- Isolation ------------------------------------------------------

    [Fact]
    public void Configuration_stays_inside_the_test_folder()
    {
        Assert.StartsWith(TestInit.Root, QuotaUsage.ConfigDir, StringComparison.Ordinal);
        Assert.NotEqual(
            Path.Combine(TestInit.OriginalLocalAppData, "OpenDrop"),
            QuotaUsage.ConfigDir);
    }
}
