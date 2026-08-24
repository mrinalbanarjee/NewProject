using Microsoft.Extensions.Options;
using MongoDB.Driver;
using TriageApi.Api.Configuration;
using TriageApi.Core.Models;

namespace TriageApi.Api.Infrastructure;

/// <summary>Owns the Mongo client/database handle and typed collection accessors.</summary>
public sealed class MongoContext
{
    private readonly MongoOptions _options;

    public MongoContext(IOptions<MongoOptions> options)
    {
        _options = options.Value;
        var client = new MongoClient(_options.ConnectionString);
        Database = client.GetDatabase(_options.DatabaseName);
    }

    public IMongoDatabase Database { get; }

    public IMongoCollection<NotificationDocument> NotificationAudit =>
        Database.GetCollection<NotificationDocument>(_options.NotificationAuditCollectionName);

    public IMongoCollection<NotificationDocument> FailedHoganNotification =>
        Database.GetCollection<NotificationDocument>(_options.FailedHoganNotificationCollectionName);

    public IMongoCollection<CustomerEventDocument> CustomerEvents =>
        Database.GetCollection<CustomerEventDocument>(_options.CustomerEventCollectionName);

    public IMongoCollection<UserRoleDocument> UserRoles =>
        Database.GetCollection<UserRoleDocument>(_options.UserRolesCollectionName);

    public IMongoCollection<ReprocessAuditEntry> ReprocessAudit =>
        Database.GetCollection<ReprocessAuditEntry>(_options.ReprocessAuditCollectionName);
}
