using Avalonia;
using Avalonia.Controls;
using Avalonia.Input;
using Avalonia.Media;
using Avalonia.Threading;

namespace OpenDrop;

// Avalonia has no MessageBox: minimal window matching the app's dark
// theme, same usage as System.Windows.MessageBox.
internal static class Msg
{
    public static Task ShowAsync(Window owner, string text, string title = "OpenDrop")
        => BuildAsync(owner, text, title, confirm: false);

    public static Task<bool> ConfirmAsync(Window owner, string text, string title = "OpenDrop")
        => BuildAsync(owner, text, title, confirm: true);

    private static Task<bool> BuildAsync(Window owner, string text, string title, bool confirm)
    {
        var window = new Window
        {
            Title = title,
            SizeToContent = SizeToContent.WidthAndHeight,
            CanResize = false,
            MaxWidth = 520,
            MinWidth = 260,
            WindowStartupLocation = WindowStartupLocation.CenterOwner,
            Background = new SolidColorBrush(Color.FromRgb(0x0f, 0x0f, 0x0f))
        };

        var message = new TextBlock
        {
            Text = text,
            FontSize = 13,
            Foreground = new SolidColorBrush(Color.FromRgb(0xcc, 0xcc, 0xcc)),
            TextWrapping = TextWrapping.Wrap,
            MaxWidth = 460,
            Margin = new Thickness(0, 0, 0, 16)
        };

        var primary = new Button
        {
            Content = confirm ? Lang.T("Msg.Yes") : "OK",
            MinWidth = 90,
            HorizontalAlignment = Avalonia.Layout.HorizontalAlignment.Right,
            Background = new SolidColorBrush(Color.FromRgb(0x4a, 0x9e, 0xff)),
            Foreground = Brushes.White,
            FontWeight = FontWeight.SemiBold,
            Padding = new Thickness(14, 8),
            BorderThickness = new Thickness(0),
            CornerRadius = new CornerRadius(6),
            Margin = new Thickness(8, 0, 0, 0)
        };

        var panel = new StackPanel { Orientation = Avalonia.Layout.Orientation.Horizontal };

        if (confirm)
        {
            var cancel = new Button
            {
                Content = Lang.T("Msg.No"),
                MinWidth = 90,
                HorizontalAlignment = Avalonia.Layout.HorizontalAlignment.Right,
                Background = new SolidColorBrush(Color.FromRgb(0x2a, 0x2a, 0x2a)),
                Foreground = new SolidColorBrush(Color.FromRgb(0xe0, 0xe0, 0xe0)),
                Padding = new Thickness(14, 8),
                BorderThickness = new Thickness(0),
                CornerRadius = new CornerRadius(6)
            };
            cancel.Click += (_, _) => window.Close(false);
            panel.Children.Add(cancel);
        }

        primary.Click += (_, _) => window.Close(true);
        panel.Children.Add(primary);

        window.KeyDown += (_, e) =>
        {
            if (e.Key == Key.Enter)
                window.Close(true);
            else if (e.Key == Key.Escape)
                window.Close(false);
        };

        window.Content = new StackPanel
        {
            Margin = new Thickness(20),
            Children = { message, panel }
        };

        return window.ShowDialog<bool>(owner);
    }
}
