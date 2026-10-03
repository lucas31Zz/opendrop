using Avalonia;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Markup.Xaml;

namespace OpenDrop;

public partial class App : Application
{
    public override void Initialize()
    {
        AvaloniaXamlLoader.Load(this);
    }

    public override void OnFrameworkInitializationCompleted()
    {
        // Apply the configured UI language before any window is built.
        Lang.Init();

        // Pick the saved light/dark variant: the palette itself is resolved
        // from App.axaml, this only sets RequestedThemeVariant. It must run
        // before the first window is created.
        ThemeManager.LoadAndApply();

        if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop)
        {
            desktop.MainWindow = new MainWindow();
            desktop.MainWindow.Show();
        }
        base.OnFrameworkInitializationCompleted();
    }
}
