# Cloudflare Integration Plan

## Current Session Management vs. Cloudflare Turnstile

### Current Approach
- Session-based job isolation using secure cookies
- In-memory session storage with 24-hour expiry
- Works well for single-server deployment

### Cloudflare Turnstile Integration Options

#### Option 1: Turnstile as Bot Protection (Recommended)
- Keep current session system for job isolation
- Add Turnstile challenge for job submission (not session management)
- Turnstile token validates human users, not sessions
- **Pros**: Simple integration, maintains current privacy model
- **Cons**: Still need session management for job isolation

#### Option 2: Turnstile + IP-based Rate Limiting
- Use Turnstile to validate human users
- Replace session-based job isolation with IP-based tracking
- **Pros**: Stateless, works with CDN caching
- **Cons**: Less privacy (users on same IP see each other's jobs)

#### Option 3: Hybrid Approach
- Turnstile for bot protection
- Cloudflare Workers for session management
- Store sessions in Cloudflare KV or R2
- **Pros**: Scalable, CDN-friendly
- **Cons**: More complex, requires Cloudflare Workers

## Recommended Implementation

### Phase 1: Add Turnstile Bot Protection
1. Add Turnstile widget to job submission form
2. Verify Turnstile token on backend before accepting jobs
3. Keep current session system for job isolation
4. Use Turnstile as additional layer, not session replacement

### Phase 2: Production Optimizations
1. Consider Cloudflare Workers for session management
2. Use Cloudflare KV for persistent session storage
3. Implement proper scaling for multiple server instances

## Environment-Specific Behavior

### Development Mode
- Relaxed rate limiting (100 jobs/minute)
- Optional Turnstile (can be disabled)
- Debug logging enabled

### Production Mode
- Strict rate limiting (5 jobs/minute)
- Mandatory Turnstile verification
- Cloudflare protection enabled

## Implementation Steps

1. **Environment Detection**: ✅ Done
2. **Relaxed Dev Rate Limits**: ✅ Done  
3. **Add Turnstile Integration**: Pending
4. **Production Deployment**: Pending

## Turnstile Integration Code Example

```javascript
// Frontend: Add Turnstile widget
<div class="cf-turnstile" data-sitekey="YOUR_SITE_KEY"></div>

// Backend: Verify Turnstile token
async function verifyTurnstile(token: string, ip: string): Promise<boolean> {
    const response = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            secret: process.env.TURNSTILE_SECRET,
            response: token,
            remoteip: ip
        })
    });
    const result = await response.json();
    return result.success;
}
```

This approach maintains privacy while adding robust bot protection suitable for public deployment.