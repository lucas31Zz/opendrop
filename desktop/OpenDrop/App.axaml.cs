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
        Console.WriteLine("[App] OnFrameworkInitializationCompleted started");
        
        // Apply the configured UI language before any window is built.
        Console.WriteLine("[App] Lang.Init()...");
        Lang.Init();
        Console.WriteLine("[App] Lang.Init() done");

        // Initialize and apply the saved theme (must run after Lang.Init
        // because theme names are localised via Lang.T).
        Console.WriteLine("[App] ThemeManager.Initialize()...");
        ThemeManager.Initialize();
        Console.WriteLine("[App] ThemeManager.Initialize() done");
        
        Console.WriteLine("[App] ThemeManager.LoadAndApply()...");
        ThemeManager.LoadAndApply();
        Console.WriteLine("[App] ThemeManager.LoadAndApply() done");

        Console.WriteLine("[App] Checking ApplicationLifetime...");
        if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop)
        {
            Console.WriteLine("[App] Creating MainWindow...");
            desktop.MainWindow = new MainWindow();
            Console.WriteLine("[App] MainWindow created, showing...");
            desktop.MainWindow.Show();
            Console.WriteLine("[App] MainWindow shown");
        }
        base.OnFrameworkInitializationCompleted();
        Console.WriteLine("[App] OnFrameworkInitializationCompleted done");
    }
}
