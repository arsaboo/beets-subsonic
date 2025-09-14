# Beets Subsonic Plugin

The beets-subsonic plugin enables synchronization between your beets music library and Subsonic servers. It provides commands for getting song IDs, updating ratings, scrobbling tracks, and triggering server scans.

Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.

## Working Effectively

### Bootstrap and Setup
- Install Python 3.12+ and pip (already available in this environment)
- Install the plugin in development mode:
  ```bash
  cd /home/runner/work/beets-subsonic/beets-subsonic
  pip3 install -e .
  ```
  - Takes ~30 seconds. NEVER CANCEL. Set timeout to 60+ seconds.
  - This installs beets>=1.6.0, requests, tqdm, and all dependencies

### Build and Development
- **No separate build step required** - this is a pure Python plugin
- Install development tools:
  ```bash
  pip3 install flake8
  ```

### Testing and Validation
- **No existing test infrastructure** - the project has no test files or test runners
- Validate plugin installation and functionality:
  ```bash
  beet --help | grep -i subsonic
  ```
  - Should show: `subsonic_addrating`, `subsonic_getids`, `subsonic_scrobble`, `subsonic_update`

### Linting and Code Quality  
- Run flake8 linting (ALWAYS do this before committing):
  ```bash
  cd /home/runner/work/beets-subsonic/beets-subsonic
  flake8 beetsplug/
  ```
  - Takes ~2 seconds. Currently shows 24 style issues (mostly line length > 79 chars)
  - Fix line length issues by breaking long lines appropriately

### Plugin Configuration
- Create beets config file if testing:
  ```bash
  mkdir -p ~/.config/beets
  cat > ~/.config/beets/config.yaml << 'EOF'
  plugins: subsonic
  
  subsonic:
      url: http://localhost:4533
      user: admin  
      pass: admin
      auth: token
      auto_scan: true
  EOF
  ```

### Testing Plugin Commands
- Test without Subsonic server (will fail gracefully with connection errors):
  ```bash
  beet subsonic_update
  beet help subsonic_getids
  beet help subsonic_addrating  
  beet help subsonic_update
  ```

## Validation

- ALWAYS run `flake8 beetsplug/` before committing changes
- ALWAYS test plugin commands with `beet --help | grep subsonic` after making changes
- Python syntax validation: `python3 -m py_compile beetsplug/subsonic.py`
- Test plugin installation: `pip3 install -e .` after any setup.py changes

## Common Tasks

### Repository Structure
```
/home/runner/work/beets-subsonic/beets-subsonic/
├── README.md (2473 chars) - Plugin documentation
├── LICENSE (MIT license)  
├── setup.py (19 lines) - Package configuration
├── .gitignore - Standard Python gitignore
└── beetsplug/
    ├── __init__.py (2 lines) - Package init
    └── subsonic.py (527 lines) - Main plugin implementation
```

### Key Plugin Methods
- `SubsonicPlugin.commands()` - Defines CLI commands
- `subsonic_getids()` - Retrieves Subsonic IDs for songs
- `subsonic_add_rating()` - Syncs ratings to Subsonic  
- `subsonic_scrobble()` - Scrobbles track plays
- `start_scan()` - Triggers Subsonic library scan

### Dependencies from setup.py
- `beets>=1.6.0` - Core beets library
- `requests` - HTTP client for Subsonic API
- `tqdm` - Progress bars

### Configuration Options
All under `subsonic:` section in beets config:
- `url` (default: http://localhost:4533) - Subsonic server URL
- `user` (default: admin) - Username  
- `pass` (default: admin) - Password (can be hex-encoded with 'enc:' prefix)
- `auth` (default: token) - Auth method: 'token' or 'password'
- `auto_scan` (default: True) - Auto-trigger scans on library changes

### Common Commands and Expected Results

#### Plugin Installation Check
```bash
$ beet --help | grep -i subsonic
subsonic_addrating      Add ratings to Subsonic library
subsonic_getids         Get subsonic_id for items  
subsonic_scrobble       Scrobble tracks
subsonic_update         Update Subsonic library
```

#### Linting Results (Current State)
```bash
$ flake8 beetsplug/
# Currently shows 24 issues:
# - 1 unused import (F401)
# - 23 line length violations (E501)
# - 1 spacing issue (E261)
```

#### File Stats
```bash  
$ find . -name "*.py" -exec wc -l {} \;
2 ./beetsplug/__init__.py
19 ./setup.py  
527 ./beetsplug/subsonic.py
```

### Working with the Plugin Code

#### Main Plugin File Structure
- Lines 1-50: Imports and plugin initialization
- Lines 50-122: CLI command definitions  
- Lines 123-228: Authentication and HTTP utilities
- Lines 229-527: Core plugin functionality (scan, get IDs, ratings, scrobble)

#### Making Changes
- Edit `beetsplug/subsonic.py` for plugin functionality
- Edit `setup.py` for dependencies or package metadata
- Always run `flake8 beetsplug/` before committing
- Test with `pip3 install -e .` and verify commands appear in `beet --help`

#### Authentication Methods
- Token auth (preferred): Uses MD5 hash with salt
- Password auth: Sends cleartext password
- Configured via `auth: token` or `auth: password` in beets config