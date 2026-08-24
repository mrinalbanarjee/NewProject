# TriageApi

Read/write API backing the AutoTriageSelf agent (see `ProblemStatement.txt`). Owns Mongo
access, deterministic PII redaction, dependency resolution, staleness checking, and
RBAC-gated reprocess-marking — the agent/LLM never talks to Mongo directly.

## Project layout

```
TriageApi.sln
src/
  TriageApi.Core/    Domain logic - models, redaction, dependency/staleness engine,
                      authorization contracts. No MongoDB.Driver query calls or ASP.NET
                      dependency - stays unit-testable without a live Mongo connection.
  TriageApi.Api/      ASP.NET Core Web API - controllers, Mongo repositories, RBAC wiring.
tests/
  TriageApi.Core.Tests/  xUnit tests for redaction, dependency resolution, staleness,
                          and the combined reprocess-plan builder.
```

## Setup

1. Requires .NET 8 SDK.
2. Point the API at your dev Mongo instance. Do **not** put the connection string in
   `appsettings.json` — use user-secrets or an environment variable:

   ```bash
   cd src/TriageApi.Api
   dotnet user-secrets init
   dotnet user-secrets set "Mongo:ConnectionString" "<your dev connection string>"
   dotnet user-secrets set "Mongo:DatabaseName" "<your dev database name>"
   ```

   Or via environment variable (double underscore separates nesting):
   `Mongo__ConnectionString`, `Mongo__DatabaseName`.

3. Collection names are configurable in `appsettings.json` under `Mongo:*CollectionName`
   if your dev instance uses different names than `NotificationAudit`,
   `FailedHoganNotification`, `CustomerEvent`, `UserRoles`, `ReprocessAudit`.

4. Seed at least one `UserRoles` document so you can call write endpoints:

   ```json
   { "UserId": "you@example.com", "Roles": ["Approver"], "UpdatedAt": "2026-08-09T00:00:00Z" }
   ```

   Use `"Roles": ["Viewer"]` for a read-only account.

## Running

```bash
dotnet run --project src/TriageApi.Api
```

Swagger UI is available at `/swagger` in development.

Every request must carry an `X-User-Id` header — see **Authentication caveat** below.

```bash
curl -H "X-User-Id: you@example.com" https://localhost:<port>/api/notifications/<correlationId>/triage
```

## Endpoints

- `GET /api/notifications/{correlationId}/triage` — redacted triage view (status,
  dependency resolution, staleness verdict) for one failed notification.
- `GET /api/notifications/by-ecn/{ecn}` — lightweight listing, no XML fields.
- `GET /api/notifications/{correlationId}/reprocess-plan` — read-only preview of the
  recommended reprocessing order (root + dependents, minus anything independently stale).
- `POST /api/notifications/reprocess-plan/confirm` — **requires the `Approver` role.**
  Commits a human-approved plan. Re-validates the submitted order against a freshly
  recomputed canonical plan server-side (rejects ids outside the recommended set, rejects
  a dependent ordered ahead of its root, rejects if the root turned out stale between
  preview and confirm) rather than trusting the caller's order blindly.
- `GET /api/customer-events/{eventMessageGuid}/triage` — redacted diagnostic view of a
  CustomerEvent. No confirm/write endpoint yet — see **Known gaps** below.

## Authentication caveat — read before using against real data

`CallerIdentityMiddleware` trusts an `X-User-Id` header at face value and looks up that
user's roles in the `UserRoles` collection. **This is not authentication** — anyone who
can reach the API can claim to be any user. It exists only so RBAC can be exercised in
dev, per the project decision to use a Mongo-backed role collection for now and the
internal IAM in production.

Before this runs against real customer data, replace `CallerIdentityMiddleware` with real
token validation (internal IAM / JWT bearer), and swap `MongoAuthorizationProvider` for an
IAM-backed `IAuthorizationProvider` implementation. Nothing else in the app should need to
change — both are the only two places identity/roles are resolved.

## The redaction guarantee

`XmlAllowListRedactor` (`TriageApi.Core/Redaction`) is the only path `NotificationMessage`
and `HoganRequestResponses[].RequestMessage`/`ResponseMessage` may travel through before
reaching an API response. It preserves XML element/attribute structure but masks every
leaf value by default; only names on `RedactionOptions.AllowedLeafElementNames` /
`AllowedAttributeNames` pass through unmasked, and malformed XML blocks the whole payload
rather than passing anything through. The allow-list is confirmed against a real OXCU054
sample message (same request-message format used for both `NotificationMessage` and
`HoganRequestResponses[].RequestMessage`/`ResponseMessage`) — it's applied globally across
all types for now, which is a simplification worth revisiting as samples for other types
arrive; see the doc comment on `RedactionOptions` for the full rationale.

### Phone-number matching (OXCU054 → OXCU066/OXCU021)

A phone-consent update only depends on a failed phone update if they're about the *same*
phone number — two unrelated phone changes for the same ECN shouldn't be bundled just
because they share a type-dependency rule. `PhoneMatchChecker`
(`TriageApi.Core/Triage`) extracts the phone number from each message's raw XML in
memory server-side and compares them, without ever putting the number itself into an API
response, log, or the LLM-facing case. `DependencyResolver` excludes a would-be dependent
- with a note - whenever the match is undeterminable, rather than guessing.

`NotificationTypePhoneField.ElementNameByType` only has **OXCU054** confirmed
(`newPhoneNbr`, from the real sample). **OXCU066 and OXCU021 are intentionally
unconfigured** — until real sample messages for those types confirm the correct element
name, the dependency rule will always exclude them pending manual review rather than risk
matching on the wrong field. Add real samples for those two types to unblock this.

## Known gaps / deferred work

- **CustomerEvent dependency graph and staleness rule** — not yet provided (per project
  decision, to arrive later). Until then, `CustomerEventTriageCaseBuilder` always reports
  `DependencyAnalysisAvailable`/`StalenessAnalysisAvailable` as `false`, and there is
  intentionally no reprocess-confirm endpoint for events — the agent should route event
  failures to an alert instead of proposing reprocessing.
- **Role granularity** — a single `Approver` role currently covers all write operations
  (notification reprocessing, and — once built — event reprocessing and Alfa
  case-opening). Split into per-capability roles once the project is further along.
- **PRD §3–§5** — the source `ProblemStatement.txt` only contained §1–§2 when this was
  built; §2.2 references a "§5" staleness section that wasn't in the file. The notification
  staleness rule implemented here came from a follow-up clarification, not the document
  itself. If more of the PRD surfaces, re-check `StalenessChecker` and
  `DependencyResolver` against it.
- **Alfa case-opening tool integration** — not implemented in this scaffold. Per the
  project decision it already exists elsewhere; wire it in as another controlled
  dependency the agent calls, the same way it calls this API.
- **Agent/orchestration layer itself** — this repo is the Triage API only. The LLM-facing
  tool layer (the decision policy: diagnose → dependents → staleness → reprocess-plan /
  open-case / alert) still needs to be built on top of these endpoints.
