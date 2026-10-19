using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using Xunit;

namespace OpenDrop.Tests;

// The what's-new dialog rules (plan Review Focus 5): the Decide matrix,
// the markdown stripping, and a notes fetch that returns null instead of
// throwing - so a version change with GitHub unreachable can never loop
// the dialog or block startup.
public class WhatsNewTests : IDisposable
{
    private readonly FakeReleaseServer _server = new();
    private readonly string _apiBase = WhatsNew.ApiBase;

    public WhatsNewTests() => _server.Json = ReleaseJson();

    public void Dispose()
    {
        WhatsNew.ApiBase = _apiBase;
        _server.Dispose();
    }

    private static string ReleaseJson() =>
        JsonSerializer.Serialize(new Dictionary<string, object?>
        {
            ["tag_name"] = "v0.15.0",
            ["body"] = "**Fixed** the [zip](http://x/y) progress\nand `resume`",
        });

    // ---- Decide ---------------------------------------------------------

    [Fact]
    public void Decide_first_launch_establishes_the_baseline_silently()
    {
        var (show, persist) = WhatsNew.Decide(null, "0.16.0");

        Assert.False(show);
        Assert.Equal("0.16.0", persist);
    }

    [Fact]
    public void Decide_the_same_version_stays_silent()
    {
        var (show, persist) = WhatsNew.Decide("0.16.0", "0.16.0");

        Assert.False(show);
        Assert.Equal("0.16.0", persist);
    }

    [Fact]
    public void Decide_a_changed_version_shows_once_and_persists_the_current()
    {
        var (show, persist) = WhatsNew.Decide("0.15.0", "0.16.0");

        Assert.True(show);
        Assert.Equal("0.16.0", persist);
    }

    // Markdown stripping moved to WhatsNewNotes.Parse - it now lives in
    // WhatsNewNotesTests together with the link segments it preserves.

    // ---- FetchNotesAsync ------------------------------------------------

    [Fact]
    public async Task Fetch_returns_the_release_body()
    {
        _server.Asset = Encoding.UTF8.GetBytes(ReleaseJson());

        var notes = await WhatsNew.FetchNotesAsync("0.15.0", _server.BaseUrl);

        Assert.NotNull(notes);
        Assert.Contains("**Fixed**", notes);
        Assert.Contains("and `resume`", notes);
    }

    [Fact]
    public async Task Fetch_returns_null_for_a_tag_the_API_does_not_know()
    {
        _server.OtherStatus = 404;

        Assert.Null(await WhatsNew.FetchNotesAsync("9.9.9", _server.BaseUrl));
    }

    [Fact]
    public async Task Fetch_returns_null_instead_of_throwing_when_the_body_is_not_json()
    {
        _server.Asset = Encoding.UTF8.GetBytes("this is not json");

        Assert.Null(await WhatsNew.FetchNotesAsync("0.15.0", _server.BaseUrl));
    }

    [Fact]
    public async Task Fetch_returns_null_instead_of_throwing_when_the_API_is_unreachable()
    {
        Assert.Null(await WhatsNew.FetchNotesAsync("0.15.0", ClosedPortBase()));
    }

    // ---- MaybeShowAsync -------------------------------------------------

    [Fact]
    public async Task MaybeShowAsync_first_run_persists_the_baseline_without_fetching_or_throwing()
    {
        WhatsNew.SetLastSeen(null);
        WhatsNew.ApiBase = ClosedPortBase();   // no network may be needed on this path

        await WhatsNew.MaybeShowAsync(null!);  // fire-and-forget: nothing may escape

        Assert.Equal(UpdateService.CurrentVersion, WhatsNew.LastSeen);
    }

    [Fact]
    public async Task MaybeShowAsync_a_new_version_is_remembered_even_when_GitHub_is_unreachable()
    {
        WhatsNew.ApiBase = ClosedPortBase();   // GitHub is down
        WhatsNew.SetLastSeen("0.14.0");         // a version change is pending

        await WhatsNew.MaybeShowAsync(null!);  // fire-and-forget: nothing may escape

        // Persisted before the fetch, so the next launch stays silent: at
        // most one dialog attempt per version, ever - no loop.
        Assert.Equal(UpdateService.CurrentVersion, WhatsNew.LastSeen);
    }

    // ---- FR notes selection (PickNotes) ---------------------------------

    [Fact]
    public void PickNotes_keeps_the_fetched_english_body_for_an_english_ui()
    {
        var picked = WhatsNew.PickNotes("### Added\n- x",
            "<!-- version: 0.15.0 -->\n### Ajoute\n- y", "0.15.0", "en");

        Assert.Equal("### Added\n- x", picked);
    }

    [Fact]
    public void PickNotes_keeps_the_fetched_body_when_french_has_no_bundle()
    {
        var picked = WhatsNew.PickNotes("body", null, "0.15.0", "fr");

        Assert.Equal("body", picked);
    }

    [Fact]
    public void PickNotes_uses_the_bundle_for_a_french_ui_at_the_matching_version()
    {
        var picked = WhatsNew.PickNotes("body",
            "<!-- version: 0.15.0 -->\n### Ajoute\n- y", "0.15.0", "fr");

        // The version header is machinery, not notes: it must not render.
        Assert.Equal("### Ajoute\n- y", picked);
    }

    [Fact]
    public void PickNotes_keeps_the_fetched_body_when_the_bundle_version_differs()
    {
        // A bundle written for another release would show the WRONG
        // version's notes: the English body is the honest fallback.
        var picked = WhatsNew.PickNotes("body",
            "<!-- version: 0.14.0 -->\nancien", "0.15.0", "fr");

        Assert.Equal("body", picked);
    }

    [Fact]
    public void PickNotes_ignores_a_bundle_whose_first_line_is_not_a_version_header()
    {
        var picked = WhatsNew.PickNotes("body", "### Ajoute\n- y", "0.15.0", "fr");

        Assert.Equal("body", picked);
    }

    [Fact]
    public void PickNotes_keeps_the_fetched_body_when_the_bundle_has_no_body()
    {
        var picked = WhatsNew.PickNotes("body", "<!-- version: 0.15.0 -->\n", "0.15.0", "fr");

        Assert.Equal("body", picked);
    }

    // The bundle ships INSIDE the app assembly: it must load and declare
    // the version it was written for (the bump rewrites both together).
    [Fact]
    public void Bundled_fr_notes_load_and_declare_their_version()
    {
        var bundle = WhatsNew.ReadBundledFrNotes();

        Assert.NotNull(bundle);
        Assert.Matches(@"\A<!--\s*version:\s*\d+\.\d+\.\d+\s*-->", bundle!);
    }

    // A loopback port nothing listens on: the connection is refused at once.
    private static string ClosedPortBase()
    {
        var probe = new TcpListener(IPAddress.Loopback, 0);
        probe.Start();
        var port = ((IPEndPoint)probe.LocalEndpoint).Port;
        probe.Stop();
        return $"http://127.0.0.1:{port}";
    }
}
