using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;
using Xunit;

namespace OpenDrop.Tests;

// What UpdateService.CheckAsync accepts from the release endpoint: the
// rules that decide whether a file gets downloaded and executed.
public class UpdateServiceCheckTests : IDisposable
{
    private const string NewTag = "v99.0.0";

    private readonly FakeReleaseServer _server = new();

    public UpdateServiceCheckTests()
    {
        _server.Json = ReleaseJson();
        UpdateService.ApiUrl = _server.BaseUrl + "/release";
    }

    public void Dispose() => _server.Dispose();

    private static string ReleaseJson(
        string tag = NewTag,
        bool draft = false,
        bool prerelease = false,
        string? assetName = null,
        string? assetUrl = "https://example.invalid/setup.exe",
        string? digest = null,
        bool withAssets = true)
    {
        var name = assetName ?? "OpenDrop-" + tag + UpdateService.AssetSuffix;
        var assets = new List<Dictionary<string, object?>>();
        if (withAssets)
        {
            var asset = new Dictionary<string, object?>
            {
                ["name"] = name,
                ["size"] = 1234,
            };
            if (assetUrl != null)
                asset["browser_download_url"] = assetUrl;
            if (digest != null)
                asset["digest"] = digest;
            assets.Add(asset);
        }

        return JsonSerializer.Serialize(new Dictionary<string, object?>
        {
            ["draft"] = draft,
            ["prerelease"] = prerelease,
            ["tag_name"] = tag,
            ["html_url"] = "https://github.com/lucas31Zz/opendrop/releases/tag/" + tag,
            ["assets"] = assets,
        });
    }

    private static string Digest() => "sha256:" + new string('a', 64);

    [Fact]
    public async Task Check_reads_the_release_this_platform_can_install()
    {
        _server.Json = ReleaseJson(digest: Digest());

        var info = await UpdateService.CheckAsync();

        Assert.NotNull(info);
        Assert.Equal(NewTag, info.Tag);
        Assert.Equal("99.0.0", info.Version);
        Assert.Equal("OpenDrop-" + NewTag + UpdateService.AssetSuffix, info.AssetName);
        Assert.Equal(1234, info.AssetSize);
        Assert.Equal(Digest(), info.Digest);
        Assert.Equal("https://example.invalid/setup.exe", info.AssetUrl);
        Assert.Contains("/releases/tag/", info.ReleaseUrl);
    }

    [Fact]
    public async Task Check_refuses_a_draft()
    {
        _server.Json = ReleaseJson(draft: true);

        Assert.Null(await UpdateService.CheckAsync());
    }

    [Fact]
    public async Task Check_refuses_a_pre_release()
    {
        _server.Json = ReleaseJson(prerelease: true);

        Assert.Null(await UpdateService.CheckAsync());
    }

    [Theory]
    [InlineData("v1.2")]
    [InlineData("latest")]
    [InlineData("untagged")]
    [InlineData("1.9.9")]
    public async Task Check_refuses_a_tag_that_is_not_a_version(string tag)
    {
        _server.Json = ReleaseJson(tag: tag);

        Assert.Null(await UpdateService.CheckAsync());
    }

    [Theory]
    [InlineData("v0.0.1")]
    [InlineData("v0.8.1")]
    public async Task Check_refuses_a_version_that_is_not_newer(string tag)
    {
        _server.Json = ReleaseJson(tag: tag);

        Assert.Null(await UpdateService.CheckAsync());
    }

    [Fact]
    public async Task Check_refuses_an_asset_for_another_platform()
    {
        _server.Json = ReleaseJson(assetName: "OpenDrop-" + NewTag + "-somewhere.zip");

        Assert.Null(await UpdateService.CheckAsync());
    }

    [Fact]
    public async Task Check_refuses_an_asset_without_a_download_url()
    {
        _server.Json = ReleaseJson(assetUrl: "");

        Assert.Null(await UpdateService.CheckAsync());
    }

    [Fact]
    public async Task Check_refuses_a_release_without_assets()
    {
        _server.Json = ReleaseJson(withAssets: false);

        Assert.Null(await UpdateService.CheckAsync());
    }

    [Fact]
    public async Task Check_still_reads_a_release_that_publishes_no_digest()
    {
        _server.Json = ReleaseJson(digest: null);

        var info = await UpdateService.CheckAsync();

        Assert.NotNull(info);
        Assert.Null(info.Digest);
    }

    [Fact]
    public async Task Check_reports_a_server_error_instead_of_silence()
    {
        // A failed check must not look like "you are up to date".
        _server.StatusCode = 500;

        await Assert.ThrowsAsync<HttpRequestException>(() => UpdateService.CheckAsync());
    }

    [Fact]
    public async Task Check_reports_invalid_json_instead_of_silence()
    {
        _server.Json = "this is not json";

        await Assert.ThrowsAnyAsync<JsonException>(() => UpdateService.CheckAsync());
    }
}
