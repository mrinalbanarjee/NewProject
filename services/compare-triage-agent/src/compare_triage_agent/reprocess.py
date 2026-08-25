"""
Builds the Mongo shell reprocess script from a set of correlationIds a human
has already chosen (typically: the primary boarding event plus whichever
canBeReprocessed:true dependent failures they accepted or hand-picked from the
classification table). Purely templated - no LLM call belongs here, this step
is mechanical once the selection is made.
"""

from __future__ import annotations

COLLECTION = "customerevent"
REPROCESS_STATUS = "Reprocess"


def build_reprocess_script(
    primary_correlation_id: str | None,
    selected_correlation_ids: list[str],
    primary_label: str = "Primary Boarding Message",
    selected_label: str = "Selected Dependent Message",
) -> str:
    entries: list[tuple[str, str]] = []
    seen: set[str] = set()
    if primary_correlation_id:
        entries.append((primary_correlation_id, primary_label))
        seen.add(primary_correlation_id)
    for correlation_id in selected_correlation_ids:
        if correlation_id in seen:
            continue  # already listed (as the primary, or a duplicate selection) - don't repeat the $in entry
        seen.add(correlation_id)
        entries.append((correlation_id, selected_label))

    if not entries:
        raise ValueError("Nothing to reprocess: no primary correlation id and no selected correlation ids given.")

    lines = []
    for i, (correlation_id, label) in enumerate(entries):
        comma = "," if i < len(entries) - 1 else ""
        lines.append(f'        "{correlation_id}"{comma}  // {label}')
    id_lines = "\n".join(lines)

    return f"""// TARGETED REPROCESS SCRIPT: Run in Mongo Shell / Compass
db.{COLLECTION}.updateMany(
  {{
    "correlationId": {{
      $in: [
{id_lines}
      ]
    }},
    "status": "FAILED"
  }},
  {{
    $set: {{
      "status": "{REPROCESS_STATUS}",
      "reprocessRequestedBy": "AI_AGENT_DIAGNOSTIC",
      "reprocessTimestamp": new Date(),
      "retryCount": 0
    }}
  }}
);"""
