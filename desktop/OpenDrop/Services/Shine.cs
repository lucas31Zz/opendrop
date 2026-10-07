using Avalonia;
using Avalonia.Controls;
using Avalonia.Input;
using Avalonia.Media;
using Avalonia.VisualTree;

namespace OpenDrop;

// Specular sheen on the buttons (the reactbits SpecularButton idea,
// without the WebGL): a band of light follows the pointer across the
// button and leaves with it.
//
// Only the Background is touched, and only while the pointer is inside.
// On the way out the local value is *cleared* rather than set to null:
// a local null wins over the style and would blank the button's box for
// good (which is exactly what happened the first time around), while
// clearing lets the style and the current theme take the colour back.
internal static class Shine
{
    private static readonly HashSet<Button> Attached = new();
    private static readonly Dictionary<Button, Color> BaseColors = new();

    // Safe to call again at any time: buttons already wired are skipped,
    // so a refresh of a list can re-attach the rows it just created.
    public static void Attach(Control root)
    {
        foreach (var button in root.GetVisualDescendants().OfType<Button>())
        {
            if (!Attached.Add(button)) continue;

            button.PointerEntered += OnEntered;
            button.PointerMoved += OnMoved;
            button.PointerExited += OnExited;
        }
    }

    private static void OnEntered(object? sender, PointerEventArgs e)
    {
        if (sender is not Button button) return;

        // The colour the style gives right now (hover state included),
        // captured before the first gradient replaces it.
        if (button.Background is SolidColorBrush solid)
            BaseColors[button] = solid.Color;
        else
            BaseColors.Remove(button);

        Paint(button, e);
    }

    private static void OnMoved(object? sender, PointerEventArgs e)
    {
        if (sender is Button button) Paint(button, e);
    }

    private static void OnExited(object? sender, PointerEventArgs e)
    {
        if (sender is not Button button) return;
        BaseColors.Remove(button);

        // Hand the button back to its style: no local value left, so the
        // palette keeps owning the colour and a theme switch keeps
        // working while the pointer is away.
        button.ClearValue(Button.BackgroundProperty);
    }

    private static void Paint(Button button, PointerEventArgs e)
    {
        var width = button.Bounds.Width;
        var height = button.Bounds.Height;
        if (width <= 1 || height <= 1) return;
        if (!BaseColors.TryGetValue(button, out var baseColor)) return;

        var point = e.GetPosition(button);
        // Where the light stands along the diagonal: 0 top-left, 1 bottom-right.
        var offset = Math.Clamp(((point.X / width) + (point.Y / height)) / 2, 0.1, 0.9);
        var light = Lift(baseColor);

        button.Background = new LinearGradientBrush
        {
            StartPoint = new RelativePoint(0, 0, RelativeUnit.Relative),
            EndPoint = new RelativePoint(1, 1, RelativeUnit.Relative),
            GradientStops =
            {
                new GradientStop(baseColor, 0),
                new GradientStop(light, offset),
                new GradientStop(baseColor, 1),
            },
        };
    }

    // Pushes the colour towards white so the band reads as a reflection
    // in both themes (a pure white band would be invisible on white).
    private static Color Lift(Color color) => Color.FromRgb(
        (byte)(color.R + (255 - color.R) * 0.45),
        (byte)(color.G + (255 - color.G) * 0.45),
        (byte)(color.B + (255 - color.B) * 0.45));
}
