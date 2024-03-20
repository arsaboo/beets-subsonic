# beets-subsonic
A plugin for [beets](https://github.com/beetbox/beets) to sync with Subsonic servers.

## Installation

Install the plugin using `pip`:

```shell
pip install -U --force-reinstall --no-deps git+https://github.com/arsaboo/beets-subsonic.git
```

Then, [configure](#configuration) the plugin in your
[`config.yaml`](https://beets.readthedocs.io/en/latest/plugins/index.html) file.

## Configuration

Add `Subsonic` to your list of enabled plugins.

```yaml
subsonic:
    url: http://localhost:4533
    user: username
    pass: password
    auth: token
    auto_scan: True
```

The available options under the ``subsonic:`` section are:

- **url**: The Subsonic server resource. Default: ``http://localhost:4533``
- **user**: The Subsonic user. Default: ``admin``
- **pass**: The Subsonic user password. (This may either be a clear-text
  password or hex-encoded with the prefix ``enc:``.) Default: ``admin``
- **auth**: The authentication method. Possible choices are ``token`` or
  ``password``. ``token`` authentication is preferred to avoid sending
  cleartext password.
- **auto_scan**: Determines whether the plugin should automatically trigger scan on the Subsonic server. Default: `True`

## Features

- **Get subsonic_id**: You can use `beet subsonic_getids` function to retrieve the Subsonic IDs for all songs in your beets library and stores them for future use. You can add the `-f` flag to force-update the ids in your library. You can use the default beets queries format to limit the items to be updated.

- **Update Rating**: You can sync your song ratings from your Beets library to your Subsonic server. You can specify the rating field to be used, e.g., `beet subsonic_addrating --rating plex_userrating`. The default is `plex_userrating`, but you can also use `spotify_track_popularity` as the rating field. You can use the default beets queries format to limit the items to be updated.

- **Scrobble tracks**: You can use `beet subsonic_scrobble` to scrobble tracks in Subsonic server. Right now, it supports the `lastViewedAt` timestamp from Plex and uses the [Plexsync](https://github.com/arsaboo/beets-plexsync) plugin. Please make sure you update your beets library before running this. You can use beets queries format to limit the items to be scrobbled. For example, `beet subsonic_scrobble year:2024` will only update tracks from 2024.

- **Trigger Subsonic update**: You can use `beet subsonic_update` to manually trigger a scan.

