# GitHub Copilot Instructions for beets-subsonic

## Repository Overview

This is a plugin for the [beets](https://github.com/beetbox/beets) music library manager that provides integration with Subsonic-compatible music servers. The plugin allows users to sync their beets library with Subsonic servers, including features like retrieving song IDs, updating ratings, scrobbling tracks, and triggering server scans.

## Project Structure

```
beets-subsonic/
├── beetsplug/
│   ├── __init__.py          # Empty init file for plugin package
│   └── subsonic.py          # Main plugin implementation
├── setup.py                 # Package setup configuration
├── README.md                # User documentation
├── LICENSE                  # MIT license
└── .gitignore              # Git ignore patterns
```

## Key Files and Components

### `beetsplug/subsonic.py`
The main plugin implementation containing:
- `SubsonicPlugin`: Main plugin class inheriting from `BeetsPlugin`
- Authentication methods (token-based and password-based)
- API communication with Subsonic servers
- Command implementations for various operations

### Key Plugin Commands
- `subsonic_update`: Manually trigger a Subsonic server scan
- `subsonic_getids`: Retrieve and store Subsonic IDs for songs
- `subsonic_addrating`: Sync ratings from beets to Subsonic
- `subsonic_scrobble`: Scrobble listening history to Subsonic

## Dependencies

- `beets>=1.6.0`: Core music library manager
- `requests`: HTTP client for Subsonic API calls
- `tqdm`: Progress bars for long-running operations
- `concurrent.futures`: ThreadPoolExecutor for parallel operations

## Configuration

The plugin uses beets' configuration system with the following options:
- `url`: Subsonic server URL (default: http://localhost:4533)
- `user`: Username (default: admin)
- `pass`: Password (marked as redacted in config)
- `auth`: Authentication method ('token' or 'password')
- `auto_scan`: Auto-trigger scans on database changes

## Code Patterns and Style

### Authentication
- Supports both token-based (preferred) and password-based authentication
- Token authentication uses MD5 hashing with random salt
- Password authentication uses hex encoding

### API Communication
- Uses requests.Session for connection reuse
- Implements comprehensive error handling for Subsonic API responses
- Supports timeout configuration (5 seconds default)
- Handles Subsonic-specific error codes (e.g., code 70 for data not found)

### Search and Matching
- Multiple search strategies for finding songs:
  1. Title-only search (most successful)
  2. Exact title matching
  3. Title + album search
  4. Artist + title search
  5. Album-only fallback
- Lenient matching using substring comparison
- Album-based search as final fallback

### Threading
- Uses ThreadPoolExecutor with MAX_WORKERS=3 for parallel operations
- Progress tracking with tqdm for user feedback
- Thread-safe operations for bulk updates

## Development Guidelines

### Error Handling
- Use plugin's `_log` for consistent logging
- Handle RequestException for network errors
- Check for valid JSON responses from Subsonic API
- Graceful degradation when items can't be found

### Rating Transformations
- `plex_userrating`: Divide by 2 and round (10-point to 5-point scale)
- `spotify_track_popularity`: Convert percentage to 0-5 scale using thresholds
- Default: Cast to integer

### Search Optimization
- Start with simplest search queries (title-only works best)
- Clean artist names by removing featuring artists
- Store and reuse potential matches for lenient matching
- Use album search as fallback when direct song search fails

### Plugin Lifecycle
- Register database change listeners for auto-scan functionality
- Use session.close() for proper cleanup
- Register CLI exit listeners for deferred operations

## Testing Considerations

Currently, the project doesn't have a formal test suite. When adding tests, consider:
- Mock Subsonic API responses for unit tests
- Test authentication methods separately
- Validate search strategy effectiveness
- Test error handling for various API failure modes
- Integration tests with actual Subsonic server (if available)

## Common Patterns

### Command Implementation
```python
def commands(self):
    cmd = ui.Subcommand("command_name", help="Description")
    cmd.parser.add_option("--flag", dest="flag", help="Help text")
    
    def func(lib, opts, args):
        items = lib.items(ui.decargs(args))
        # Process items
    
    cmd.func = func
    return [cmd]
```

### API Request Pattern
```python
url = self.__format_url("endpoint")
payload = self.authenticate()
if payload is None:
    return
    
json = self.send_request(url, payload)
if json:
    # Process successful response
```

### Item Processing with Progress
```python
with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
    for item in tqdm(items, total=len(items)):
        future = executor.submit(self.process_item, item)
        result = future.result()
        # Handle result
```

## Security Notes

- Passwords are marked as redacted in configuration
- Token authentication preferred over password authentication
- Hex encoding used for password transmission
- No sensitive data should be logged at non-debug levels