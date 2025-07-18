# Enhanced --info Command Documentation

## Overview

The `--info` command has been enhanced to include information about the currently authenticated user. This provides users with better visibility into their authentication status and account details.

## What's New

### Before Enhancement
The `--info` command displayed:
- OneNote Copilot version
- System information (Python version, platform)
- Configuration settings
- Microsoft Graph API settings

### After Enhancement
The `--info` command now also displays:
- **Authenticated User Information**
  - Display Name: User's full name from Microsoft account
  - Email: User's email address (userPrincipalName)
  - Authentication Status: Whether user is currently authenticated

## Usage

```bash
# Show enhanced system information including user details
python -m src.main --info
```

## Implementation Details

### New Method Added
- `MicrosoftAuthenticator.get_user_profile()` - Retrieves user profile from Microsoft Graph API `/me` endpoint

### Enhanced Function
- `show_system_info()` - Now includes authenticated user information with proper error handling

### Error Handling
The enhancement includes robust error handling:
- Shows "Not authenticated" if user is not logged in
- Shows "Error retrieving information" if API call fails
- Shows "Failed to retrieve profile" if profile data is unavailable

## Sample Output

```
OneNote Copilot v1.0.0

Authenticated User:
- Display Name: John Doe
- Email: john.doe@outlook.com

System Information:
- Python: 3.11.9
- Platform: win32
- Settings file: C:\Users\John\.onenote_copilot\settings.toml
- Cache directory: C:\Users\John\.onenote_copilot\cache

Configuration:
- OpenAI Model: gpt-4o-mini
- CLI Colors: Enabled
- CLI Markdown: Enabled
- Debug Mode: Disabled

Microsoft Graph API:
- Client ID: [configured client ID]
- Scopes: User.Read, Notes.Read
- Cache: C:\Users\John\.onenote_copilot\token_cache.bin
```

## Benefits

1. **User Awareness**: Users can quickly verify which account they're authenticated with
2. **Debugging**: Helps troubleshoot authentication issues
3. **Multi-Account Support**: Useful when working with multiple Microsoft accounts
4. **Security**: Users can verify their identity before performing operations

## Files Modified

- `src/auth/microsoft_auth.py`: Added `get_user_profile()` method
- `src/main.py`: Enhanced `show_system_info()` function
- `PROGRESS.md`: Updated progress tracking
- `prompts/TASK.md`: Marked task as completed
