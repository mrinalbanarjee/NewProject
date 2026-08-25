namespace TriageApi.Api.Configuration;

/// <summary>
/// Bound from the "LoanBoarding" configuration section - feature flags and
/// retry/throttling tuning for the loan boarding flow.
/// </summary>
public sealed class LoanBoardingAppConfig
{
    public const string SectionName = "LoanBoarding";

    public bool CreateLoanOnIdenticalAppId { get; set; }
    public List<string> Dealers { get; set; } = new();
    public bool EnableAfsFlow { get; set; }
    public bool EnableAlfaFlow { get; set; }
    public bool EnableDay1Throttling { get; set; }
    public bool EnablePrePilotMode { get; set; }
    public bool EnableRetryFromLoanBoardingRecords { get; set; }
    public List<string>? ExcludedCities { get; set; }
    public int? FicoScoreThreshold { get; set; }
    public int MaxConcurrencyForRetry { get; set; }
    public int MaxRetries { get; set; }
    public int MinConcurrencyForRetry { get; set; }
    public bool MockResponses { get; set; }
    public int MongoRecordDeleteDelaySeconds { get; set; }
    public bool RemoveLoanBoardingRecordsOnSuccess { get; set; }
    public bool ResetRetryCounterAfterPublish { get; set; }
    public int RetryIntervalMinutes { get; set; }
    public bool SaveLoanBoardingRecords { get; set; }
    public List<string> States { get; set; } = new();
}
