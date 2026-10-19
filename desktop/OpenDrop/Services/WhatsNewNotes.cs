using System.Collections.Generic;
using System.Text.RegularExpressions;

namespace OpenDrop;

// A block of the what's-new popup body: one line of the release notes,
// already classified. The popup renders blocks (headings, bullets,
// paragraphs) instead of one wall of plain text.
internal enum NoteBlockKind
{
    Paragraph,
    Heading,     // "## text"
    Bullet,      // "- text" or "* text"
}

// One inline run inside a block: plain text, or a link with its URL -
// which is what lets the popup open the release notes' links in the
// browser and offer "copy link" (the old dialog flattened them away).
internal sealed class NoteSegment
{
    internal NoteSegment(string text, string? url)
    {
        Text = text;
        Url = url;
    }

    internal string Text { get; }
    internal string? Url { get; }        // null = plain text segment
    internal bool IsLink => Url != null;
}

// A rendered line: its kind plus its inline segments. Text is the plain
// concatenation of the segment texts (no markers), for tooltips/tests.
internal sealed class NoteBlock
{
    internal NoteBlock(NoteBlockKind kind, IReadOnlyList<NoteSegment> segments)
    {
        Kind = kind;
        Segments = segments;
    }

    internal NoteBlockKind Kind { get; }
    internal IReadOnlyList<NoteSegment> Segments { get; }

    internal string Text
    {
        get
        {
            var s = "";
            foreach (var segment in Segments) s += segment.Text;
            return s;
        }
    }
}

// Markdown -> blocks. Deliberately tiny: it understands exactly what a
// GitHub release body tends to use inside OpenDrop's own changelog -
// headings, bullet lines, **bold**, `code`, [text](url) links and bare
// URLs. Everything else passes through as plain text, markers stripped,
// the same spirit as WhatsNew.StripMarkdown - but links SURVIVE.
internal static class WhatsNewNotes
{
    // [text](url) first so bare-URL scanning never eats the parentheses;
    // the bare URL alternative keeps the trailing slash and query.
    private static readonly Regex LinkOrUrl = new(
        @"\[([^\]]*)\]\(([^)\s]+)\)" +
        @"|(https?://[^\s)<]+)",
        RegexOptions.Compiled | RegexOptions.IgnoreCase);

    internal static List<NoteBlock> Parse(string? markdown)
    {
        var blocks = new List<NoteBlock>();
        if (string.IsNullOrEmpty(markdown)) return blocks;

        foreach (var raw in markdown.Replace("\r\n", "\n").Split('\n'))
        {
            var line = raw.Trim();
            if (line.Length == 0) continue;              // blank: separator

            var kind = NoteBlockKind.Paragraph;
            if (line[0] == '#')
            {
                // "# " / "## " / "### ": every level renders as one
                // heading, all the hashes stripped.
                kind = NoteBlockKind.Heading;
                line = line.TrimStart('#').TrimStart();
            }
            else if (line.StartsWith("- ", StringComparison.Ordinal) ||
                     line.StartsWith("* ", StringComparison.Ordinal))
            {
                kind = NoteBlockKind.Bullet;
                line = line.Substring(2);
            }

            if (line.Length == 0) continue;   // a line of only "##": nothing to show

            blocks.Add(new NoteBlock(kind, ParseSegments(line)));
        }
        return blocks;
    }

    // Splits one line into text and link segments. Bold, italic and code
    // markers are stripped from the text runs - the popup has no
    // mono/weight styling for them, and unstripped ** or * would just
    // look like noise. The ** is removed before the single *, so an
    // emphasis pair collapses cleanly.
    private static IReadOnlyList<NoteSegment> ParseSegments(string line)
    {
        var segments = new List<NoteSegment>();
        var last = 0;
        foreach (Match m in LinkOrUrl.Matches(line))
        {
            if (m.Index > last)
                segments.Add(Text(line.Substring(last, m.Index - last)));

            if (m.Groups[1].Success)                       // [text](url)
                segments.Add(new NoteSegment(
                    StripMarkers(m.Groups[1].Value), m.Groups[2].Value));
            else                                           // bare url
                segments.Add(new NoteSegment(m.Groups[3].Value, m.Groups[3].Value));
            last = m.Index + m.Length;
        }
        if (last < line.Length)
            segments.Add(Text(line.Substring(last)));

        return segments.Count > 0
            ? segments
            : new List<NoteSegment> { Text(line) };
    }

    private static NoteSegment Text(string s)
        => new(StripMarkers(s), null);

    private static string StripMarkers(string s)
        => s.Replace("**", "").Replace("`", "").Replace("*", "");
}
