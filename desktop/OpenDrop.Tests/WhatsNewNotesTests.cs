using System.Linq;
using Xunit;

namespace OpenDrop.Tests;

// The What's-New popup renders release notes as blocks with CLICKABLE
// links (the old dialog flattened every link to plain text). The parser
// is the whole testable core: markdown in, blocks of inline segments
// out - a link segment carries its URL so the popup can open it in the
// browser and offer "copy link".
public class WhatsNewNotesTests
{
    // ---- block kinds ----------------------------------------------------

    [Fact]
    public void Parse_a_heading_line_becomes_a_heading_block()
    {
        var blocks = WhatsNewNotes.Parse("## Fixed");

        var block = Assert.Single(blocks);
        Assert.Equal(NoteBlockKind.Heading, block.Kind);
        Assert.Equal("Fixed", block.Text);
    }

    [Fact]
    public void Parse_a_third_level_heading_drops_all_the_hashes()
    {
        // The changelog's own sub-sections use "### Added": raw hashes in
        // the popup would be visual noise, not markdown.
        var blocks = WhatsNewNotes.Parse("### Added");

        var block = Assert.Single(blocks);
        Assert.Equal(NoteBlockKind.Heading, block.Kind);
        Assert.Equal("Added", block.Text);
    }

    [Fact]
    public void Parse_a_bullet_line_becomes_a_bullet_block()
    {
        var blocks = WhatsNewNotes.Parse("- faster resume");

        var block = Assert.Single(blocks);
        Assert.Equal(NoteBlockKind.Bullet, block.Kind);
        Assert.Equal("faster resume", block.Text);
    }

    [Fact]
    public void Parse_a_plain_line_becomes_a_paragraph_block()
    {
        var blocks = WhatsNewNotes.Parse("just text");

        var block = Assert.Single(blocks);
        Assert.Equal(NoteBlockKind.Paragraph, block.Kind);
        Assert.Equal("just text", block.Text);
    }

    [Fact]
    public void Parse_blank_lines_produce_no_blocks()
    {
        var blocks = WhatsNewNotes.Parse("\n\n\n");

        Assert.Empty(blocks);
    }

    [Fact]
    public void Parse_null_or_empty_returns_no_blocks()
    {
        Assert.Empty(WhatsNewNotes.Parse(null));
        Assert.Empty(WhatsNewNotes.Parse(""));
    }

    [Fact]
    public void Parse_keeps_one_block_per_line()
    {
        var blocks = WhatsNewNotes.Parse("## Fixed\n- one\n- two\ntext");

        Assert.Equal(4, blocks.Count);
        Assert.Equal(NoteBlockKind.Heading, blocks[0].Kind);
        Assert.Equal(NoteBlockKind.Bullet, blocks[1].Kind);
        Assert.Equal(NoteBlockKind.Bullet, blocks[2].Kind);
        Assert.Equal(NoteBlockKind.Paragraph, blocks[3].Kind);
    }

    // ---- inline segments ------------------------------------------------

    [Fact]
    public void Parse_bold_and_code_markers_are_stripped_from_text()
    {
        // Italic markers too: "*Standard*" in the release notes would
        // otherwise render with visible asterisks.
        var blocks = WhatsNewNotes.Parse("**Fixed** *fast* the `resume`");

        var block = Assert.Single(blocks);
        Assert.Equal("Fixed fast the resume", block.Text);
        Assert.All(block.Segments, s => Assert.Null(s.Url));
    }

    [Fact]
    public void Parse_a_markdown_link_keeps_its_url_as_a_link_segment()
    {
        var blocks = WhatsNewNotes.Parse("see [the zip](http://x/zip) done");

        var block = Assert.Single(blocks);
        Assert.Equal("see the zip done", block.Text);

        var link = block.Segments.Single(s => s.Url != null);
        Assert.Equal("the zip", link.Text);
        Assert.Equal("http://x/zip", link.Url);
    }

    [Fact]
    public void Parse_a_bare_url_becomes_a_link_segment_too()
    {
        var blocks = WhatsNewNotes.Parse("changelog at https://github.com/x/y");

        var block = Assert.Single(blocks);
        var link = block.Segments.Single(s => s.Url != null);
        Assert.Equal("https://github.com/x/y", link.Url);
        Assert.Equal("https://github.com/x/y", link.Text);
    }

    [Fact]
    public void Parse_plain_text_around_a_link_stays_clickable_free()
    {
        var blocks = WhatsNewNotes.Parse("plain [l](http://x) plain");

        var block = Assert.Single(blocks);
        Assert.Equal(3, block.Segments.Count);
        Assert.Null(block.Segments[0].Url);
        Assert.NotNull(block.Segments[1].Url);
        Assert.Null(block.Segments[2].Url);
    }
}
