using System.Runtime.InteropServices;
using Avalonia;
using Avalonia.Animation;
using Avalonia.Controls;
using Avalonia.Styling;

namespace OpenDrop;

// Reduced motion, desktop side. Windows reports whether the user asked
// for animations to be off (Settings > Accessibility > Visual effects >
// Animation effects); the app then keeps every state change but drops
// the movement: the aurora parks, list fades and springs apply at
// once.
internal static class Motion
{
    private const uint SpiGetClientAreaAnimation = 0x1042;

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool SystemParametersInfoW(uint uiAction, uint uiParam, ref int pvParam, uint fWinIni);

    // Fail open: when the query fails the default experience (motion)
    // is what the user gets.
    public static bool Allowed { get; } = Query();

    private static bool Query()
    {
        try
        {
            var enabled = 1;
            return SystemParametersInfoW(SpiGetClientAreaAnimation, 0, ref enabled, 0) && enabled != 0;
        }
        catch
        {
            return true;
        }
    }

    // Called right after InitializeComponent, before the first frame:
    // Style.Animations never start and every Transitions set becomes
    // instant. Static decoration is untouched - the aurora blobs keep
    // the position, fill and opacity their styles give them, they just
    // never move.
    public static void Apply(StyledElement root)
    {
        if (Allowed) return;

        foreach (var style in root.Styles)
        {
            if (style is not Style concrete) continue;

            concrete.Animations?.Clear();
            foreach (var setter in concrete.Setters)
            {
                if (setter is Setter { Value: Transitions transitions })
                    transitions.Clear();
            }
        }
    }
}
