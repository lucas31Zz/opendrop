using Avalonia;
using Avalonia.Controls;
using Avalonia.Input;
using Avalonia.Layout;
using Avalonia.Media;
using Avalonia.Threading;

namespace OpenDrop;

// Avalonia has no MessageBox: minimal windows matching the app palette,
// same usage as System.Windows.MessageBox. The brushes come from the theme
// dictionaries in App.axaml, so dialogs follow the light/dark variant.
internal static class Msg
{
    private static IBrush Resolve(string key, Color fallback)
    {
        var app = Application.Current;
        if (app != null &&
            app.TryGetResource(key, app.ActualThemeVariant, out var value) &&
            value is IBrush brush)
            return brush;
        return new SolidColorBrush(fallback);
    }

    private static IBrush WindowBg => Resolve("Brush.Window", Color.FromRgb(0x0f, 0x0f, 0x0f));
    private static IBrush BodyText => Resolve("Brush.TextSecondary", Color.FromRgb(0xcc, 0xcc, 0xcc));
    private static IBrush FieldText => Resolve("Brush.TextPrimary", Color.FromRgb(0xe0, 0xe0, 0xe0));
    private static IBrush AccentBg => Resolve("Brush.Accent", Color.FromRgb(0x4a, 0x9e, 0xff));
    private static IBrush QuietBg => Resolve("Brush.Control", Color.FromRgb(0x2a, 0x2a, 0x2a));
    private static IBrush InputBg => Resolve("Brush.Input", Color.FromRgb(0x22, 0x22, 0x22));

    public static Task ShowAsync(Window owner, string text, string title = "OpenDrop")
        => BuildAsync(owner, text, title, new[] { "OK" }, primaryIndex: 0);

    public static async Task<bool> ConfirmAsync(Window owner, string text, string title = "OpenDrop")
        => await BuildAsync(owner, text, title,
            new[] { Lang.T("Msg.No"), Lang.T("Msg.Yes") }, primaryIndex: 1) == 1;

    // Several choices side by side. Returns the index of the clicked
    // button, or -1 when the window is closed / Escape is pressed.
    public static Task<int> ChoiceAsync(Window owner, string text, string title,
                                        params string[] options)
        => BuildAsync(owner, text, title, options, primaryIndex: options.Length - 1);

    // Free-form input: the typed text, or null on cancel/Escape/close.
    public static async Task<string?> InputAsync(Window owner, string title,
                                                 string label, string initial)
    {
        var tcs = new TaskCompletionSource<string?>();

        var window = new Window
        {
            Title = title,
            SizeToContent = SizeToContent.WidthAndHeight,
            CanResize = false,
            MaxWidth = 520,
            MinWidth = 320,
            WindowStartupLocation = WindowStartupLocation.CenterOwner,
            Background = WindowBg
        };

        var box = new TextBox
        {
            Text = initial,
            Width = 340,
            FontSize = 13,
            Foreground = FieldText,
            Background = InputBg,
            BorderThickness = new Thickness(1),
            BorderBrush = AccentBg,
            Margin = new Thickness(0, 0, 0, 16),
            CaretBrush = Brushes.White
        };

        var ok = MakeButton(Lang.T("Msg.Ok"), accent: true, () =>
        {
            tcs.TrySetResult(box.Text);
            window.Close();
        });

        var cancel = MakeButton(Lang.T("Msg.Cancel"), accent: false, () =>
        {
            tcs.TrySetResult(null);
            window.Close();
        });

        var buttons = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            HorizontalAlignment = HorizontalAlignment.Right,
            Children = { cancel, ok }
        };

        window.Content = new StackPanel
        {
            Margin = new Thickness(20),
            Children =
            {
                new TextBlock
                {
                    Text = label,
                    FontSize = 13,
                    Foreground = BodyText,
                    TextWrapping = TextWrapping.Wrap,
                    MaxWidth = 460,
                    Margin = new Thickness(0, 0, 0, 8)
                },
                box,
                buttons
            }
        };

        void Accept()
        {
            tcs.TrySetResult(box.Text);
            window.Close();
        }

        void Reject()
        {
            tcs.TrySetResult(null);
            window.Close();
        }

        window.KeyDown += (_, e) =>
        {
            if (e.Key == Key.Enter) Accept();
            else if (e.Key == Key.Escape) Reject();
        };
        window.Closed += (_, _) => tcs.TrySetResult(null);

        await window.ShowDialog(owner);
        return await tcs.Task;
    }

    // Non-modal progress window for a job that takes long enough to be
    // worth showing (an update download). The caller reports progress and
    // closes it when done; the window never blocks anything.
    public sealed class ProgressReporter
    {
        private readonly Window _window;
        private readonly TextBlock _heading;
        private readonly TextBlock _detail;
        private readonly ProgressBar _bar;

        internal ProgressReporter(Window window, TextBlock heading,
                                  TextBlock detail, ProgressBar bar)
        {
            _window = window;
            _heading = heading;
            _detail = detail;
            _bar = bar;
        }

        public void Title(string text) => Post(() => _heading.Text = text);

        public void Report(long done, long total) => Post(() =>
        {
            if (total > 0)
            {
                var percent = 100.0 * done / total;
                _bar.Value = Math.Clamp(percent, 0, 100);
                _detail.Text = $"{Bytes(done)} / {Bytes(total)}";
            }
            else
            {
                _bar.IsIndeterminate = true;
            }
        });

        public void Close() => Post(() =>
        {
            try { _window.Close(); } catch (Exception) { }
        });

        private static void Post(Action action)
            => Dispatcher.UIThread.Post(action);

        private static string Bytes(long value)
        {
            if (value >= 1024L * 1024 * 1024)
                return $"{value / (1024d * 1024 * 1024):0.#} GB";
            if (value >= 1024L * 1024)
                return $"{value / (1024d * 1024):0.#} MB";
            if (value >= 1024L)
                return $"{value / 1024d:0.#} KB";
            return $"{value} B";
        }
    }

    public static ProgressReporter Progress(Window owner, string title, string text)
    {
        var heading = new TextBlock
        {
            Text = text,
            FontSize = 13,
            FontWeight = FontWeight.SemiBold,
            Foreground = FieldText,
            TextWrapping = TextWrapping.Wrap,
            MaxWidth = 420,
            Margin = new Thickness(0, 0, 0, 12)
        };

        var detail = new TextBlock
        {
            Text = "",
            FontSize = 12,
            Foreground = BodyText,
            Margin = new Thickness(0, 0, 0, 8)
        };

        var bar = new ProgressBar
        {
            Minimum = 0,
            Maximum = 100,
            Value = 0,
            Height = 6,
            Width = 420
        };

        var window = new Window
        {
            Title = title,
            SizeToContent = SizeToContent.WidthAndHeight,
            CanResize = false,
            MaxWidth = 520,
            MinWidth = 320,
            WindowStartupLocation = WindowStartupLocation.CenterOwner,
            Background = WindowBg,
            Content = new StackPanel
            {
                Margin = new Thickness(20),
                Children = { heading, detail, bar }
            }
        };

        // Modal on purpose: the update is a one-shot job, the owner has
        // nothing to gain from being usable while the file downloads.
        _ = window.ShowDialog(owner);
        return new ProgressReporter(window, heading, detail, bar);
    }

    // Every button in visual order; -1 when dismissed without a choice.
    private static Task<int> BuildAsync(Window owner, string text, string title,
                                        string[] buttons, int primaryIndex)
    {
        var tcs = new TaskCompletionSource<int>();

        var window = new Window
        {
            Title = title,
            SizeToContent = SizeToContent.WidthAndHeight,
            CanResize = false,
            MaxWidth = 520,
            MinWidth = 260,
            WindowStartupLocation = WindowStartupLocation.CenterOwner,
            Background = WindowBg
        };

        void Choose(int index)
        {
            tcs.TrySetResult(index);
            window.Close();
        }

        var message = new TextBlock
        {
            Text = text,
            FontSize = 13,
            Foreground = BodyText,
            TextWrapping = TextWrapping.Wrap,
            MaxWidth = 460,
            Margin = new Thickness(0, 0, 0, 16)
        };

        var panel = new StackPanel { Orientation = Orientation.Horizontal };
        for (var i = 0; i < buttons.Length; i++)
        {
            var index = i;
            panel.Children.Add(MakeButton(buttons[i], i == primaryIndex, () => Choose(index)));
        }

        window.KeyDown += (_, e) =>
        {
            if (e.Key == Key.Enter)
                Choose(primaryIndex);
            else if (e.Key == Key.Escape)
                Choose(-1);
        };
        window.Closed += (_, _) => tcs.TrySetResult(-1);

        window.Content = new StackPanel
        {
            Margin = new Thickness(20),
            Children = { message, panel }
        };

        // The dialog completes through Closed; a failure to show it must
        // not leave the caller awaiting forever.
        _ = window.ShowDialog(owner).ContinueWith(
            task => { if (task.IsFaulted) tcs.TrySetResult(-1); },
            TaskScheduler.Default);
        return tcs.Task;
    }

    private static Button MakeButton(string text, bool accent, Action onClick)
    {
        var button = new Button
        {
            Content = text,
            MinWidth = 90,
            HorizontalAlignment = HorizontalAlignment.Right,
            Background = accent ? AccentBg : QuietBg,
            Foreground = accent ? Brushes.White : FieldText,
            FontWeight = accent ? FontWeight.SemiBold : FontWeight.Normal,
            FontSize = 13,
            Padding = new Thickness(14, 8),
            BorderThickness = new Thickness(0),
            CornerRadius = new CornerRadius(6),
            Margin = new Thickness(8, 0, 0, 0),
            Cursor = new Cursor(StandardCursorType.Hand)
        };
        button.Click += (_, _) => onClick();
        return button;
    }
}
