# Authentication Troubleshooting Guide

## Common Authentication Issues

### 1. "OAuth2 error: server_error" after User Logout

**Symptoms:**
- Previous user successfully logged out
- New user gets "server_error" in browser during login
- Empty error description in logs

**Root Causes:**
1. **Microsoft Server-Side Session Conflict**: Microsoft's OAuth2 servers may retain session state
2. **Browser Cache Issues**: Browser may have residual authentication cookies
3. **Application State Conflicts**: MSAL application state not fully reset
4. **Port Conflicts**: Callback server port 8080 may be in use

**Solutions:**

#### Quick Fix (Recommended First)
```powershell
# Clear browser cache for Microsoft authentication
# In Edge/Chrome: Clear browsing data for "login.microsoftonline.com"

# Clear any residual token cache
Remove-Item "$env:USERPROFILE\.onenote_copilot" -Recurse -Force -ErrorAction SilentlyContinue

# Restart the application
```

#### Advanced Troubleshooting
1. **Check Port Availability:**
   ```powershell
   netstat -an | findstr :8080
   ```

2. **Clear All Microsoft Sessions:**
   - Open browser
   - Go to https://login.microsoftonline.com/logout
   - Clear all Microsoft session cookies

3. **Reset Application State:**
   ```powershell
   # Force remove all cache directories
   Remove-Item "$env:USERPROFILE\.onenote_copilot" -Recurse -Force
   Remove-Item ".\.onenote_copilot" -Recurse -Force -ErrorAction SilentlyContinue
   ```

#### If Problem Persists
- Try different browser
- Wait 5-10 minutes for Microsoft session cleanup
- Use incognito/private browsing mode
- Check if corporate firewall blocks OAuth2 redirects

## Prevention

1. **Proper Logout Sequence**: Always use the built-in logout command
2. **Browser Hygiene**: Periodically clear Microsoft authentication cookies
3. **Port Management**: Ensure port 8080 is available for callbacks

## Technical Details

The `server_error` typically indicates:
- Microsoft's authorization server encountered an internal error
- Session state conflicts between multiple users
- Timing issues with token cache cleanup
- Network/firewall interference with OAuth2 flow

## Contact Support

If issues persist after trying all solutions, provide:
- Complete log file content
- Browser type and version
- Network environment details (corporate/home)
- Exact timing of logout→login sequence
