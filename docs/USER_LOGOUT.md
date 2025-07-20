# User Logout and Multi-User Support Documentation

## Overview

OneNote Copilot now supports comprehensive user logout functionality, enabling clean user switching in multi-user environments. The logout system clears all user-specific data including authentication tokens, indexed content, and caches.

## Features

### Complete Data Cleanup
- **Authentication Data**: Removes MSAL tokens, session data, and cache files
- **Vector Database**: Clears all indexed OneNote content and embeddings
- **Embedding Cache**: Removes cached embeddings to free up space
- **Temporary Files**: Cleans up temporary files and caches
- **Optional Log Clearing**: Can optionally clear application logs

### Safety and Flexibility
- **Confirmation Prompts**: Prevents accidental data loss
- **Status Checking**: Shows what data exists before logout
- **Selective Clearing**: Options to preserve specific data types
- **Force Mode**: Skip confirmations for automated scenarios
- **Detailed Reporting**: Clear feedback on what was cleared

## Usage

### Basic Logout
```bash
# Full logout with confirmation prompt
python -m src.main logout

# Quick status check
python -m src.main logout --status

# Force logout without confirmation
python -m src.main logout --force
```

### Selective Data Preservation
```bash
# Logout but keep indexed content (vector database)
python -m src.main logout --keep-vector-db

# Logout but keep embedding cache
python -m src.main logout --keep-cache

# Logout and also clear application logs
python -m src.main logout --clear-logs
```

### Status Checking
```bash
# Check what user data exists
python -m src.main logout --status
```

Example output:
```
                User Data Status
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Data Type       ┃ Status    ┃ Details                   ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Authentication  │ ✅ Active │ 1,234 bytes               │
│ Vector Database │ ✅ Exists │ 12 embeddings, 300.2 MB  │
│ Embedding Cache │ ✅ Exists │ 45 entries                │
│ Temporary Files │ ❌ None   │ No temp files             │
└─────────────────┴───────────┴───────────────────────────┘
```

## Multi-User Workflow

### Switching Users

**Step 1: Current User Logout**
```bash
# Logout current user completely
python -m src.main logout
```

**Step 2: New User Authentication**
```bash
# New user authenticates
python -m src.main --auth-only
```

**Step 3: Index New User's Content**
```bash
# Index the new user's OneNote content
python -m src.main index --initial
```

**Step 4: Start Using**
```bash
# Start interactive session with new user's data
python -m src.main
```

### Shared System Scenarios

**Scenario 1: Preserve Common Content**
```bash
# Logout but keep vector database for shared content
python -m src.main logout --keep-vector-db
```

**Scenario 2: Clean Slate for New User**
```bash
# Complete cleanup for fresh start
python -m src.main logout --clear-logs --force
```

**Scenario 3: Development/Testing**
```bash
# Quick status check during development
python -m src.main logout --status
```

## Technical Implementation

### Authentication Clearing
- Clears MSAL token cache from memory
- Removes token cache file from disk
- Resets authenticator state
- Handles missing files gracefully

### Vector Database Clearing
- Deletes ChromaDB collection completely
- Removes vector database directory
- Recreates empty collection
- Resets operation counters

### Cache Management
- Clears embedding cache completely
- Removes temporary files by pattern
- Preserves directory structure
- Handles permission errors gracefully

### Error Handling
- Graceful handling of missing files
- Permission error recovery
- Partial success reporting
- Detailed error logging

## Security Considerations

### Data Privacy
- **Complete Token Removal**: All authentication tokens are securely cleared
- **Content Isolation**: Vector database clearing prevents data leakage between users
- **Cache Cleanup**: Embedding cache is completely cleared to prevent content access
- **Temporary File Cleanup**: All temporary files are removed

### Access Control
- **Confirmation Prompts**: Prevent accidental data loss
- **Status Checking**: Users can see what data exists before clearing
- **Selective Options**: Users can choose what to preserve
- **Audit Trail**: All operations are logged for accountability

## Troubleshooting

### Common Issues

**Permission Errors**
```bash
# If you get permission errors, try:
python -m src.main logout --force
```

**Partial Logout**
```bash
# Check what wasn't cleared:
python -m src.main logout --status

# Try individual operations if needed
```

**Authentication Issues After Logout**
```bash
# New user authentication:
python -m src.main --auth-only
```

### Verification

**Verify Complete Logout**
```bash
# All should show "None" or "❌":
python -m src.main logout --status
```

**Verify New User Setup**
```bash
# Should show new user's data:
python -m src.main index --status
```

## Integration with Existing Features

### Semantic Search
- Logout clears all indexed content by default
- New user must re-index their content
- Preserves search infrastructure and configuration

### Content Indexing
- Index commands work normally after logout
- Fresh indexing creates clean vector database
- Previous user's content completely removed

### Authentication
- Clean authentication state after logout
- New user gets fresh authentication flow
- No interference between user sessions

## Best Practices

### Regular Use
1. **Always check status first**: `logout --status`
2. **Use confirmations**: Avoid `--force` unless necessary
3. **Preserve data when appropriate**: Use `--keep-*` options wisely
4. **Verify logout completion**: Check status after logout

### Shared Systems
1. **Document user switching procedures**
2. **Use `--clear-logs` for privacy**
3. **Verify complete cleanup between users**
4. **Consider automated logout scripts for kiosks**

### Development
1. **Use status checks during testing**
2. **Preserve vector database when testing search**
3. **Clear logs when debugging authentication**
4. **Use force mode in automated tests**

## Examples

### Full Multi-User Scenario
```bash
# User A finishes work
python -m src.main logout
# Confirms: "The following data will be cleared: ..."
# User responds: Y

# System ready for User B
python -m src.main --auth-only
# User B authenticates

# Index User B's content
python -m src.main index --initial
# System indexes User B's OneNote pages

# User B starts working
python -m src.main
# Clean session with User B's data
```

This logout system ensures complete data isolation between users while maintaining the flexibility to preserve data when appropriate.
