# Inbox
## Task 25 Addition — Feature Status JSON

At Task 25, before go-live, create a file at docs/feature_status.json listing every 
user-facing feature of the Asset Board. Each feature starts marked as "passes": false 
and only gets flipped to true after real end-to-end testing. Use JSON format (not 
Markdown) because Claude is less likely to accidentally overwrite or rewrite JSON files.

Example format:
{
  "features": [
    {
      "category": "asset_lifecycle",
      "description": "Operator can start a session on an available room",
      "passes": false
    },
    {
      "category": "asset_lifecycle", 
      "description": "Asset moves from Available to Occupied after session start",
      "passes": false
    }
  ]
}

Do not deploy to Frappe Cloud until every feature shows "passes": true.
Source: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
