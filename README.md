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
    url: https://example.com:443/subsonic
    user: username
    pass: password
    auth: token
```

The available options under the ``subsonic:`` section are:

- **url**: The Subsonic server resource. Default: ``http://localhost:4040``
- **user**: The Subsonic user. Default: ``admin``
- **pass**: The Subsonic user password. (This may either be a clear-text
  password or hex-encoded with the prefix ``enc:``.) Default: ``admin``
- **auth**: The authentication method. Possible choices are ``token`` or
  ``password``. ``token`` authentication is preferred to avoid sending
  cleartext password.