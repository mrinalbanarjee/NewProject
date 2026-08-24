using Microsoft.AspNetCore.Mvc;
using TriageApi.Api.Authorization;
using TriageApi.Core.Authorization;
using TriageApi.Core.Models;
using TriageApi.Core.Redaction;
using TriageApi.Core.Repositories;
using TriageApi.Core.Triage;

namespace TriageApi.Api.Controllers;

[ApiController]
[Route("api/notifications")]
public sealed class NotificationsController(
    INotificationRepository repository,
    IMessageRedactor redactor) : ControllerBase
{
    /// <summary>Redacted, structured triage view of one failed notification - safe to hand to the agent/LLM.</summary>
    [HttpGet("{correlationId}/triage")]
    public async Task<ActionResult<NotificationTriageCase>> GetTriage(string correlationId, CancellationToken cancellationToken)
    {
        var failed = await repository.FindFailedByCorrelationIdAsync(correlationId, cancellationToken);
        if (failed is null)
        {
            return NotFound(new { error = $"No failed notification found for CorrelationId '{correlationId}'." });
        }

        var candidates = await repository.FindAllByEcnAsync(failed.Ecn, cancellationToken);
        var triageCase = NotificationTriageCaseBuilder.Build(failed, candidates, redactor);
        return Ok(triageCase);
    }

    /// <summary>Lightweight listing for browsing failures on an ECN - no XML fields included.</summary>
    [HttpGet("by-ecn/{ecn}")]
    public async Task<ActionResult<IReadOnlyList<NotificationSummary>>> GetByEcn(string ecn, CancellationToken cancellationToken)
    {
        var all = await repository.FindAllByEcnAsync(ecn, cancellationToken);
        var summaries = all
            .Select(n => new NotificationSummary(n.CorrelationId, n.NotificationType, n.Status, n.HoganTimeStamp, n.RetryCounter, n.ProcessorText))
            .ToList();
        return Ok(summaries);
    }

    /// <summary>Read-only preview of the reprocessing plan for a failed notification - no writes.</summary>
    [HttpGet("{correlationId}/reprocess-plan")]
    public async Task<ActionResult<ReprocessPlan>> PreviewReprocessPlan(string correlationId, CancellationToken cancellationToken)
    {
        var failed = await repository.FindFailedByCorrelationIdAsync(correlationId, cancellationToken);
        if (failed is null)
        {
            return NotFound(new { error = $"No failed notification found for CorrelationId '{correlationId}'." });
        }

        var candidates = await repository.FindAllByEcnAsync(failed.Ecn, cancellationToken);
        var plan = ReprocessPlanBuilder.Build(failed, candidates);
        return Ok(plan);
    }

    /// <summary>
    /// Commits a human-approved reprocessing plan. The submitted order is validated
    /// against a freshly recomputed canonical plan - it is not trusted as-is - to guard
    /// against a stale preview (e.g. a later success arrived between preview and confirm)
    /// and to enforce that a dependent is never marked ahead of the root it depends on.
    /// Only reordering/subsetting of the canonical recommended set is accepted; ids
    /// outside that set are rejected rather than silently marked, since anything else
    /// would bypass the deterministic dependency check entirely.
    /// </summary>
    [HttpPost("reprocess-plan/confirm")]
    [RequireRole(Role.Approver)]
    public async Task<ActionResult<ReprocessAuditEntry>> ConfirmReprocessPlan(
        [FromBody] ConfirmReprocessRequest request,
        [FromServices] ICurrentCaller currentCaller,
        CancellationToken cancellationToken)
    {
        if (request.OrderedCorrelationIds.Count == 0)
        {
            return BadRequest(new { error = "OrderedCorrelationIds must not be empty." });
        }

        var root = await repository.FindFailedByCorrelationIdAsync(request.RootCorrelationId, cancellationToken);
        if (root is null)
        {
            return NotFound(new { error = $"No failed notification found for CorrelationId '{request.RootCorrelationId}'." });
        }

        var candidates = await repository.FindAllByEcnAsync(root.Ecn, cancellationToken);
        var canonicalPlan = ReprocessPlanBuilder.Build(root, candidates);

        if (canonicalPlan.RootStaleness.IsStale)
        {
            return Conflict(new
            {
                error = "Root failure is superseded by a later success - cannot confirm a reprocessing plan for it.",
                supersededBy = canonicalPlan.RootStaleness.SupersededByCorrelationId,
            });
        }

        var allowedIds = new HashSet<string>(canonicalPlan.RecommendedOrder.Select(i => i.CorrelationId));
        var dependentIds = canonicalPlan.RecommendedOrder
            .Where(i => i.CorrelationId != root.CorrelationId)
            .Select(i => i.CorrelationId)
            .ToHashSet();

        foreach (var id in request.OrderedCorrelationIds)
        {
            if (!allowedIds.Contains(id))
            {
                return BadRequest(new { error = $"'{id}' is not part of the recommended plan for root '{root.CorrelationId}'." });
            }
        }

        var submittedDependentIds = request.OrderedCorrelationIds.Where(dependentIds.Contains).ToList();
        if (submittedDependentIds.Count > 0)
        {
            var rootIndex = request.OrderedCorrelationIds.ToList().IndexOf(root.CorrelationId);
            if (rootIndex < 0)
            {
                return BadRequest(new { error = "Root correlation id must be included when its dependents are included." });
            }

            var earliestDependentIndex = submittedDependentIds.Min(id => request.OrderedCorrelationIds.ToList().IndexOf(id));
            if (rootIndex > earliestDependentIndex)
            {
                return BadRequest(new { error = "Root must be ordered before its dependents." });
            }
        }

        await repository.MarkReprocessAsync(request.OrderedCorrelationIds, cancellationToken);

        var auditEntry = new ReprocessAuditEntry
        {
            RootCorrelationId = root.CorrelationId,
            ApprovedByUserId = currentCaller.Context!.UserId,
            ApprovedAt = DateTime.UtcNow,
            OrderedCorrelationIds = request.OrderedCorrelationIds.ToList(),
        };
        await repository.RecordReprocessAuditAsync(auditEntry, cancellationToken);

        return Ok(auditEntry);
    }
}
