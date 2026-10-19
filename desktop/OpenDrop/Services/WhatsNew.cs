using System;
using System.IO;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using Avalonia.Controls;

namespace OpenDrop;

// The what's-new dialog: after an update, show the release notes once.
//
// The rules that keep it harmless (plan Review Focus 5):
//  - the first launch only records the baseline, silently;
//  - the new version is persisted BEFORE the notes are fetched, so a
//    version change with GitHub unreachable still ends the cycle: at
//    most one dialog attempt per version, ever - never a loop;
//  - every failure (offline, 404, unparseable JSON) means "no dialog",
//    and no exception may ever reach the fire-and-forget call at startup.
internal static class WhatsNew
{
    // config.json key holding the version whose notes were last offered
    // (spec: LastWhatsNewVersion).
    internal const string LastSeenKey = "LastWhatsNewVersion";

    // {ApiBase}/releases/tags/v<version> - the same endpoint family
    // UpdateService uses; a mutable static so the suites can point it at
    // FakeReleaseServer, exactly like UpdateService.ApiUrl.
    internal static string ApiBase { get; set; } =
        "https://api.github.com/repos/lucas31Zz/opendrop";

    // Same client pattern as UpdateService.ApiHttp: short timeout (a
    // stalled check is not worth reporting), the User-Agent the GitHub
    // API requires, and the GitHub JSON media type.
    private static readonly HttpClient ApiHttp = CreateClient(TimeSpan.FromSeconds(20));

    private static HttpClient CreateClient(TimeSpan timeout)
    {
        var client = new HttpClient { Timeout = timeout };
        client.DefaultRequestHeaders.UserAgent.ParseAdd(
            $"OpenDrop/{UpdateService.CurrentVersion}");
        client.DefaultRequestHeaders.Accept.Add(
            new MediaTypeWithQualityHeaderValue("application/vnd.github+json"));
        return client;
    }

    // What this launch should do: whether to show the dialog, and which
    // version to remember (always the current one).
    internal static (bool Show, string Persist) Decide(string? lastSeen, string current)
    {
        if (lastSeen == null)
            return (false, current);            // first run: baseline only
        if (string.Equals(lastSeen, current, StringComparison.Ordinal))
            return (false, current);            // nothing changed
        return (true, current);                 // changed: show once
    }

    // The body of the release for this version, or null on ANY failure
    // (404, network error, unparseable JSON): a missing dialog is worth
    // far more than an exception here, and never the other way round.
    internal static async Task<string?> FetchNotesAsync(
        string version, string? apiBase = null)
    {
        try
        {
            using var response = await ApiHttp.GetAsync(
                $"{apiBase ?? ApiBase}/releases/tags/v{version}");
            if (!response.IsSuccessStatusCode) return null;

            var json = await response.Content.ReadAsStringAsync();
            using var doc = JsonDocument.Parse(json);
            if (!doc.RootElement.TryGetProperty("body", out var body)) return null;
            if (body.ValueKind != JsonValueKind.String) return null;
            var text = body.GetString();
            return string.IsNullOrWhiteSpace(text) ? null : text;   // no notes = no dialog
        }
        catch (Exception)
        {
            return null;
        }
    }

    // ---- French notes ---------------------------------------------------
    // GitHub only ever carries the English body, so the French UI gets a
    // TRANSLATION bundled inside the app: one file, rewritten at every
    // version bump NEXT TO the changelog section it translates. The first
    // line is the version the bundle was written for; anything that does
    // not line up (missing bundle, malformed header, version drift after
    // a forgotten bump) keeps the fetched English body - the dialog never
    // dies over a translation, and it can never show another release's
    // French notes.

    // Embedded resource name of the bundled French notes (see the
    // csproj EmbeddedResource item with the same LogicalName).
    private const string BundledFrResource = "OpenDrop.whatsnew.fr.md";

    // A whole first line of the form "<!-- version: 0.15.0 -->", with the
    // trailing whitespace (the newline included) consumed, so the rest of
    // the file IS the notes body.
    private static readonly Regex FrBundleHeader = new(
        @"\A<!--\s*version:\s*(\d+\.\d+\.\d+)\s*-->\s*",
        RegexOptions.Compiled);

    // Which body the popup renders: the fetched English notes, or the
    // bundled French translation when the UI is French AND the bundle
    // declares exactly the running version. Pure function (unit-tested).
    internal static string PickNotes(string fetched, string? bundledFr,
                                     string current, string lang)
    {
        if (!string.Equals(lang, "fr", StringComparison.Ordinal)) return fetched;
        if (string.IsNullOrWhiteSpace(bundledFr)) return fetched;

        var header = FrBundleHeader.Match(bundledFr);
        if (!header.Success) return fetched;               // no version line
        if (!string.Equals(header.Groups[1].Value, current,
                StringComparison.Ordinal))
            return fetched;                                 // written for another release

        var body = bundledFr.Substring(header.Length);
        return string.IsNullOrWhiteSpace(body) ? fetched : body;
    }

    // The bundled file as shipped, or null when it is missing (a build
    // without the resource, or an unreadable stream): the caller falls
    // back to the English body.
    internal static string? ReadBundledFrNotes()
    {
        try
        {
            using var stream = typeof(WhatsNew).Assembly
                .GetManifestResourceStream(BundledFrResource);
            if (stream == null) return null;
            using var reader = new StreamReader(stream);
            return reader.ReadToEnd();
        }
        catch (Exception)
        {
            return null;
        }
    }

    // Fire-and-forget right after the main window is shown: Decide and
    // persist ALWAYS (the baseline is established even when silent), the
    // notes are fetched ONLY when Decide says show, and EVERYTHING is
    // swallowed - this runs detached off App startup, where an escaping
    // exception could take the whole application down.
    internal static async Task MaybeShowAsync(Window owner)
    {
        try
        {
            var current = UpdateService.CurrentVersion;
            var (show, persist) = Decide(LastSeen, current);
            SetLastSeen(persist);               // always, even when not showing
            if (!show) return;

            var notes = await FetchNotesAsync(current);
            if (notes == null) return;          // offline / no such release: stay quiet

            // The popup draws itself: no owner window (tests pass null)
            // or nothing to render means the rules above still ran, the
            // cycle is still closed for this version - just silently.
            // A French UI prefers the bundled translation of these notes.
            var body = PickNotes(notes, ReadBundledFrNotes(),
                current, Lang.Current);
            WhatsNewPopup.Show(owner, current, WhatsNewNotes.Parse(body));
        }
        catch (Exception)
        {
            // By design: nothing may escape into the startup path.
        }
    }

    // ---- storage --------------------------------------------------------
    // The cross-platform settings store the app already uses: config.json
    // through QuotaUsage.ConfigPath (LOCALAPPDATA/APPDATA when present,
    // ~/.opendrop otherwise). No registry, no new store - linux-x64 keeps
    // working, and Settings rewrites the file without dropping this key
    // because it copies the whole dictionary first.

    // The remembered version, null before the first run (an empty or
    // non-string value counts as "nothing recorded").
    internal static string? LastSeen
    {
        get
        {
            var value = UpdateService.ReadConfigValue(LastSeenKey);
            return string.IsNullOrWhiteSpace(value) ? null : value;
        }
    }

    // Remembers a version (null clears the record, i.e. back to "first
    // run"). Swallows everything: forgetting what was shown is never
    // worth breaking startup over. An unchanged value writes nothing:
    // MaybeShowAsync calls this on EVERY launch, and WriteConfigValue is
    // a non-atomic truncate+write that config.json simply does not need
    // when the stored value already matches.
    internal static void SetLastSeen(string? version)
    {
        var value = version ?? "";
        if (string.Equals(UpdateService.ReadConfigValue(LastSeenKey), value,
                StringComparison.Ordinal))
            return;                          // already stored: no I/O at all
        UpdateService.WriteConfigValue(LastSeenKey, value);
    }
}
