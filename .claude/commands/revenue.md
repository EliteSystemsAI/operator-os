# /revenue — Stripe Revenue Snapshot

Pull a live revenue snapshot from Stripe for the current month and compare to last month.

## Steps

### Step 1: Pull current month balance from Stripe

```bash
source .env
# Get current month charges
MONTH_START=$(date -u +%Y-%m-01T00:00:00Z)
curl -s "https://api.stripe.com/v1/charges?created[gte]=$(date -d "$MONTH_START" +%s 2>/dev/null || date -j -f "%Y-%m-%dT%H:%M:%SZ" "$MONTH_START" +%s)&limit=100" \
  -u "$STRIPE_API_KEY:" | python3 -m json.tool
```

Or use Stripe balance transactions endpoint:
```bash
source .env
curl -s "https://api.stripe.com/v1/balance_transactions?limit=100&type=charge" \
  -u "$STRIPE_API_KEY:"
```

### Step 2: Output revenue snapshot

```
💰 REVENUE SNAPSHOT — [MONTH YEAR]

📈 THIS MONTH (MTD)
Gross revenue:    $X,XXX
Refunds:          -$XXX
Net revenue:      $X,XXX
Transactions:     XX

📊 LAST MONTH
Gross:  $X,XXX | Net: $X,XXX

📉 TREND
MoM change: ↑/↓ X% ($X,XXX)

🏆 TOP REVENUE SOURCES
1. [Product/service] — $X,XXX (XX%)
2. [Product/service] — $X,XXX (XX%)
3. [Product/service] — $X,XXX (XX%)

⚠️ WATCH
[Any refunds, disputes, or anomalies to flag]

─────────────────
YTD Revenue: $XXX,XXX
Monthly run rate: $XX,XXX
Annual run rate: $XXX,XXX
```

### Step 3: Flag anything notable

- Revenue significantly down vs last month → flag
- Refund rate > 5% → flag
- Any active disputes → flag immediately
- Run rate vs $100K/month target

## Notes

- Stripe API key stored in `.env` as `STRIPE_API_KEY`
- Always use live key (rk_live_...) not test key
- Reference period: current month to date vs previous full month
