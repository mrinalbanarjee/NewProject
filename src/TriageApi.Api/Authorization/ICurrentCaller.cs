using TriageApi.Core.Authorization;

namespace TriageApi.Api.Authorization;

/// <summary>Per-request resolved caller, set by CallerIdentityMiddleware.</summary>
public interface ICurrentCaller
{
    CallerContext? Context { get; set; }
}

public sealed class CurrentCaller : ICurrentCaller
{
    public CallerContext? Context { get; set; }
}
