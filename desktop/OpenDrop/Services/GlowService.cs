using Avalonia;
using Avalonia.Controls;
using Avalonia.Input;
using Avalonia.Media;

namespace OpenDrop;

// Ambient light that follows the pointer. A fixed-size radial patch
// (Glow.Ambient in the theme dictionaries) sits behind the content and is
// only moved with a render transform, so one pointer event costs a single
// assignment: no layout pass, no allocation, no timer running in the
// background. The patch is never hit-tested, so it cannot steal a click,
// and it hides itself as soon as the pointer leaves the window.
//
// The instance is kept alive by the events it subscribes to on the
// window; the window keeps its own reference only so a later settings
// switch (effects on/off) can reach Enabled.
internal sealed class GlowService
{
    private readonly Window _window;
    private readonly Border _glow;
    private readonly TranslateTransform _transform = new();

    private GlowService(Window window, Border glow)
    {
        _window = window;
        _glow = glow;
        _glow.RenderTransform = _transform;
    }

    // glow: the overlay declared in the window XAML (x:Name="GlowLayer"),
    // anchored top-left so the transform below is enough to centre it.
    public static GlowService Attach(Window window, Border glow)
    {
        var service = new GlowService(window, glow);
        window.PointerMoved += service.OnMoved;
        window.PointerExited += service.OnExited;
        window.Closed += service.OnClosed;
        return service;
    }

    // Decorative only: turning it off simply keeps the patch hidden, the
    // events stay cheap (they return on the first line).
    public bool Enabled { get; set; } = true;

    private void OnMoved(object? sender, PointerEventArgs e)
    {
        if (!Enabled)
        {
            if (_glow.IsVisible) _glow.IsVisible = false;
            return;
        }
        if (_glow.Parent is not Visual host) return;

        var p = e.GetPosition(host);
        // Width/Height from the XAML, not Bounds: an element that starts
        // hidden is never measured, so Bounds would be zero on the very
        // first move and the patch would jump one half-step to the side.
        var w = double.IsNaN(_glow.Width) || _glow.Width <= 0 ? _glow.Bounds.Width : _glow.Width;
        var h = double.IsNaN(_glow.Height) || _glow.Height <= 0 ? _glow.Bounds.Height : _glow.Height;
        _transform.X = p.X - w / 2;
        _transform.Y = p.Y - h / 2;
        if (!_glow.IsVisible) _glow.IsVisible = true;
    }

    private void OnExited(object? sender, PointerEventArgs e)
    {
        if (_glow.IsVisible) _glow.IsVisible = false;
    }

    private void OnClosed(object? sender, EventArgs e)
    {
        _window.PointerMoved -= OnMoved;
        _window.PointerExited -= OnExited;
        _window.Closed -= OnClosed;
        _glow.RenderTransform = null;
    }
}
