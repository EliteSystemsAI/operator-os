# /leads — GHL Pipeline Snapshot

Pull the current lead pipeline from GHL and give a quick status on where opportunities stand.

## Steps

### Step 1: Pull contacts from GHL pipeline

```bash
source .env
curl -s -X GET "https://services.leadconnectorhq.com/contacts/?locationId=$GHL_LOCATION_ID&limit=20" \
  -H "Authorization: Bearer $GHL_API_KEY" \
  -H "Version: 2021-07-28"
```

### Step 2: Pull opportunities (pipeline)

```bash
source .env
curl -s -X GET "https://services.leadconnectorhq.com/opportunities/search?location_id=$GHL_LOCATION_ID&limit=20" \
  -H "Authorization: Bearer $GHL_API_KEY" \
  -H "Version: 2021-07-28"
```

### Step 3: Output pipeline snapshot

```
📊 LEAD PIPELINE SNAPSHOT — [DATE]

🔥 QUALIFIED LEADS (ready to close)
[List name, source, stage, days in pipeline]

🌡️ WARM (nurturing)
[List name, source, last contact]

❄️ COLD / STALLED
[List name, days since last contact — flag if > 3 days]

📥 NEW THIS WEEK
[New leads added in last 7 days]

─────────────────
Total pipeline: X leads
Qualified: X | Nurturing: X | Stalled: X

💡 ACTION NEEDED
[Any leads that need Zac's attention — stalled > 3 days, no follow-up, etc.]
```

### Step 4: Flag anything urgent

- Leads tagged `qualified_lead` with no activity in 24h → Zac needs to follow up NOW
- Leads stalled > 3 days → re-engagement needed
- Any new `qualified_lead` tags from today → surface immediately

Say `/leads call [name]` to prep for a specific sales call.
