using Avalonia;
using Avalonia.Controls;
using Avalonia.Input;
using Avalonia.Layout;
using Avalonia.Media;
using Avalonia.Threading;

namespace OpenDrop;

// Avalonia has no MessageBox: minimal windows matching the app's dark
// theme, same usage as System.Windows.MessageBox.
internal static class Msg
{
    private static readonly SolidColorBrush WindowBg = new(Color.FromRgb(0x0f, 0x0f, 0x0f));
    private static readonly SolidColorBrush BodyText = new(Color.FromRgb(0xcc, 0xcc, 0xcc));
    private static readonly SolidColorBrush FieldText = new(Color.FromRgb(0xe0, 0xe0, 0xe0));
    private static readonly SolidColorBrush AccentBg = new(Color.FromRgb(0x4a, 0x9e, 0xff));
    private static readonly SolidColorBrush QuietBg = new(Color.FromRgb(0x2a, 0x2a, 0x2a));
    private static readonly SolidColorBrush InputBg = new(Color.FromRgb(0x22, 0x22, 0x22));

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
            BorderBrush = new SolidColorBrush(Color.FromRgb(0x4a, 0x9e, 0xff)),
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
