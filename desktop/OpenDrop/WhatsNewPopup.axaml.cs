using System;
using System.Collections.Generic;
using System.Diagnostics;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.Documents;
using Avalonia.Input;
using Avalonia.Interactivity;
using Avalonia.Media;

namespace OpenDrop;

// The what's-new popup: a fixed, centred overlay INSIDE the owner window
// (replaces the movable OS dialog). One screen, three ways out (close
// button, Escape, backdrop), a body that always scrolls inside its frame,
// and the release notes' links rendered as REAL links - left click opens
// them in the default browser, the tooltip shows the URL, right click
// copies it. The Decide/SetLastSeen rules live in WhatsNew.cs and are
// untouched: this class only draws what it is given.
internal sealed partial class WhatsNewPopup : UserControl
{
    internal WhatsNewPopup()
    {
        InitializeComponent();
        Focusable = true;
    }

    // Builds the body from parsed blocks. Called once, right before Show
    // adds this control to the owner's root panel. (Focus is taken in
    // OnAttachedToVisualTree: Focus() on a control that is not yet in
    // the tree is silently ignored - and Escape would not work.)
    internal void Setup(string version, IReadOnlyList<NoteBlock> blocks)
    {
        TitleText.Text = $"OpenDrop {version} - {Lang.T("WhatsNew.Title")}";
        foreach (var block in blocks)
            BlocksPanel.Children.Add(BuildBlock(block));

        KeyDown += OnKeyDown;
    }

    protected override void OnAttachedToVisualTree(
        VisualTreeAttachmentEventArgs e)
    {
        base.OnAttachedToVisualTree(e);
        Focus();                            // so Escape reaches OnKeyDown
    }

    // Attaches to the owner's root panel as the LAST child (so it paints
    // above everything) spanning every row/column: the backdrop must dim
    // the whole window, not one grid cell.
    internal static void Show(Window owner, string version,
                              IReadOnlyList<NoteBlock> blocks)
    {
        if (owner.Content is not Panel host || blocks.Count == 0) return;

        var popup = new WhatsNewPopup();
        popup.Setup(version, blocks);
        Grid.SetRowSpan(popup, 100);
        Grid.SetColumnSpan(popup, 100);
        host.Children.Add(popup);
    }

    // ---- block rendering ------------------------------------------------

    private Control BuildBlock(NoteBlock block) => block.Kind switch
    {
        NoteBlockKind.Heading => BuildText(block, 15, FontWeight.SemiBold,
            Resolve("Brush.TextTitle", Colors.White), new Thickness(0, 10, 0, 4)),
        NoteBlockKind.Bullet => BuildBullet(block),
        _ => BuildText(block, 13, FontWeight.Normal,
            Resolve("Brush.TextSecondary", Color.FromRgb(0xcc, 0xcc, 0xcc)),
            new Thickness(0, 0, 0, 6)),
    };

    // A bullet is a two-column grid (marker, content), NOT a horizontal
    // StackPanel: an infinite-width StackPanel would stop the content
    // from wrapping, and a single TextBlock with a "•" run would align
    // wrapped lines under the marker instead of the text.
    private Control BuildBullet(NoteBlock block)
    {
        var grid = new Grid
        {
            ColumnDefinitions = new ColumnDefinitions("Auto,*"),
            Margin = new Thickness(0, 0, 0, 6),
        };

        var dot = new TextBlock
        {
            Text = "•",
            FontSize = 13,
            Foreground = Resolve("Brush.TextMuted",
                Color.FromRgb(0x77, 0x77, 0x77)),
            Margin = new Thickness(0, 0, 8, 0),
            VerticalAlignment = Avalonia.Layout.VerticalAlignment.Top,
        };
        var content = BuildText(block, 13, FontWeight.Normal,
            Resolve("Brush.TextSecondary", Color.FromRgb(0xcc, 0xcc, 0xcc)),
            new Thickness(0));
        Grid.SetColumn(content, 1);

        grid.Children.Add(dot);
        grid.Children.Add(content);
        return grid;
    }

    // One line of the notes: plain runs for text, inline UI containers
    // for links (the only element that can be clicked and copied).
    private TextBlock BuildText(NoteBlock block, double size, FontWeight weight,
                                IBrush foreground, Thickness margin)
    {
        var tb = new TextBlock
        {
            FontSize = size,
            FontWeight = weight,
            Foreground = foreground,
            TextWrapping = TextWrapping.Wrap,
            Margin = margin,
        };

        // The TextBlock ctor always builds Inlines (Avalonia 12 source),
        // the nullable annotation only exists because XAML can clear it.
        var inlines = tb.Inlines!;
        foreach (var segment in block.Segments)
        {
            if (segment.IsLink)
                inlines.Add(new InlineUIContainer(BuildLink(segment!, size)));
            else
                inlines.Add(new Run(segment.Text));
        }
        return tb;
    }

    // A link segment: accent + underline + hand cursor, the URL as
    // tooltip, left click -> browser, right click -> copy the URL.
    private Control BuildLink(NoteSegment segment, double fontSize)
    {
        var url = segment.Url!;
        var link = new TextBlock
        {
            Text = segment.Text,
            FontSize = fontSize,
        };
        link.Classes.Add("note-link");
        ToolTip.SetTip(link, url);

        link.PointerPressed += (_, e) =>
        {
            if (!e.GetCurrentPoint(link).Properties.IsLeftButtonPressed) return;
            OpenUrl(url);
            e.Handled = true;               // no text selection gesture
        };

        var copy = new MenuItem { Header = Lang.T("WhatsNew.CopyLink") };
        copy.Click += (_, _) =>
        {
            if (TopLevel.GetTopLevel(this)?.Clipboard is not { } clipboard) return;
            // Avalonia 12: IClipboard takes an IAsyncDataTransfer, not a raw string.
            var payload = new DataTransfer();
            payload.Add(DataTransferItem.CreateText(url));
            _ = clipboard.SetDataAsync(payload);
        };
        var menu = new ContextMenu();
        menu.Items.Add(copy);
        link.ContextMenu = menu;

        return link;
    }

    private static void OpenUrl(string url)
    {
        try
        {
            Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
        }
        catch
        {
            // no browser registered: nothing sensible to do - the URL is
            // still visible in the tooltip and copyable.
        }
    }

    // ---- dismissal ------------------------------------------------------

    private void Close_Click(object? sender, RoutedEventArgs e) => ClosePopup();

    private void Backdrop_PointerPressed(object? sender, PointerPressedEventArgs e)
        => ClosePopup();

    private void OnKeyDown(object? sender, KeyEventArgs e)
    {
        if (e.Key != Key.Escape) return;
        e.Handled = true;
        ClosePopup();
    }

    // The popup leaves the tree the way it entered it; the owner window
    // regains the keyboard focus.
    private void ClosePopup()
    {
        KeyDown -= OnKeyDown;
        if (TopLevel.GetTopLevel(this) is Window owner) owner.Activate();
        if (Parent is Panel host) host.Children.Remove(this);
    }

    // ---- brush lookup (same pattern as Msg.cs) --------------------------

    private static IBrush Resolve(string key, Color fallback)
    {
        var app = Application.Current;
        if (app != null &&
            app.TryGetResource(key, app.ActualThemeVariant, out var value) &&
            value is IBrush brush)
            return brush;
        return new SolidColorBrush(fallback);
    }
}
