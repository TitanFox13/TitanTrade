# Security Considerations

## API Key Management

### Rules
1. **Never commit API keys** to the repository
2. All keys loaded via environment variables (`os.environ`)
3. `.env` file is in `.gitignore`
4. GitHub Secrets used for CI/CD
5. No API keys in log files or AI prompts

### Key Rotation
- Rotate all API keys quarterly
- Alpaca keys can be regenerated in the dashboard
- FMP keys regenerated in account settings
- Claude/Gemini keys managed via their respective consoles

## Trading Safety

### Paper Trading Default
- System defaults to paper trading mode
- Live trading requires explicit `"trading_mode": "live"` in watchlist.json
- AND environment variable `TRADING_MODE=live`
- Both must agree to enable live trading (defense in depth)

### Position Limits
- Hard-coded maximum position size: 10% of portfolio
- Hard-coded stop-loss: 5% below entry
- These limits are enforced in code, not just in AI prompts
- AI cannot override position sizing rules

### Order Validation
- Every order is validated before submission:
  - Is the market open? (or is this a valid extended-hours order?)
  - Does the order exceed position size limits?
  - Is there already an open position for this ticker?
  - Is the thesis still valid (not expired)?

## Data Security

### Sensitive Data
- Portfolio values and positions are stored in `state/` files
- These files should NOT be in a public repository
- Use a private repo or encrypt state files for public repos

### AI Prompt Safety
- Never include API keys in AI prompts
- AI reasoning is logged but does not contain credentials
- Input data is hashed for reproducibility without exposing raw data

## Operational Security

### GitHub Actions
- All secrets stored as encrypted repository secrets
- Workflow files are version-controlled and auditable
- Bot commits use a dedicated email address
- Branch protection recommended on main branch

### Rate Limiting
- Built-in retry logic with exponential backoff
- Respects API rate limits to avoid account suspension
- Maximum 3 retries before graceful failure
