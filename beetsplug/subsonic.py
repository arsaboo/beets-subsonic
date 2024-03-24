"""
Adds Subsonic support to Beets.
"""

import hashlib
import random
import string
from binascii import hexlify

import requests

from beets import config, ui
from beets.plugins import BeetsPlugin
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm


class SubsonicPlugin(BeetsPlugin):
    """Subsonic plugin for Beets."""

    data_source = "Subsonic"
    MAX_WORKERS = 3

    def __init__(self):
        super().__init__()
        # Set default configuration values
        config["subsonic"].add(
            {
                "user": "admin",
                "pass": "admin",
                "url": "http://localhost:4533",
                "auth": "token",
                'auto_scan': True,
            }
        )
        config["subsonic"]["pass"].redact = True
        self.session = requests.Session()
        self.register_listener("database_change", self.db_change)
        self.register_listener("smartplaylist_update", self.spl_update)

    def db_change(self, lib, model):
        if self.config['auto_scan'].get(bool):
            self.register_listener("cli_exit", self.start_scan)

    def spl_update(self):
        if self.config['auto_scan'].get(bool):
            self.register_listener("cli_exit", self.start_scan)

    def commands(self):
        """Add beet UI commands to interact with Subsonic."""

        # Subsonic update command
        subsonicupdate_cmd = ui.Subcommand(
            "subsonic_update", help=f"Update {self.data_source} library"
        )

        def func(lib, opts, args):
            self.start_scan()

        subsonicupdate_cmd.func = func

        # Subsonic rating update command
        subsonicaddrating_cmd = ui.Subcommand(
            "subsonic_addrating", help=f"Add ratings to {self.data_source} library"
        )

        subsonicaddrating_cmd.parser.add_option(
            "--rating",
            dest="rating",
            action="store_true",
            default="plex_userrating",
            help=(
                "Specify the rating field to be used for updating Subsonic ratings. "
                "Default is plex_userrating."
            ),
        )

        def func_add_rating(lib, opts, args):
            items = lib.items(ui.decargs(args))
            self.subsonic_add_rating(items, opts.rating)

        subsonicaddrating_cmd.func = func_add_rating

        # get subsonic ids
        subsonic_get_ids_cmd = ui.Subcommand(
            "subsonic_getids", help="Get subsonic_id for items"
        )

        subsonic_get_ids_cmd.parser.add_option(
            "-f",
            "--force",
            dest="force_refetch",
            action="store_true",
            default=False,
            help="Force subsonic_id update",
        )

        def func_get_ids(lib, opts, args):
            items = lib.items(ui.decargs(args))
            self.subsonic_get_ids(items, opts.force_refetch)

        subsonic_get_ids_cmd.func = func_get_ids

        # scrobble
        subsonic_scrobble_cmd = ui.Subcommand(
            "subsonic_scrobble", help="Scrobble tracks"
        )

        def func_scrobble(lib, opts, args):
            items = lib.items(ui.decargs(args))
            self.subsonic_scrobble(items)

        subsonic_scrobble_cmd.func = func_scrobble

        return [
            subsonicupdate_cmd,
            subsonicaddrating_cmd,
            subsonic_get_ids_cmd,
            subsonic_scrobble_cmd,
        ]

    @staticmethod
    def __create_token():
        """Create salt and token from given password.

        :return: The generated salt and hashed token
        """
        password = config["subsonic"]["pass"].as_str()

        # Pick the random sequence and salt the password
        r = string.ascii_letters + string.digits
        salt = "".join([random.choice(r) for _ in range(6)])
        salted_password = password + salt
        token = hashlib.md5(salted_password.encode("utf-8")).hexdigest()

        # Put together the payload of the request to the server and the URL
        return salt, token

    @staticmethod
    def __format_url(endpoint):
        """Get the Subsonic URL to trigger the given endpoint.
        Uses either the url config option or the deprecated host, port,
        and context_path config options together.

        :return: Endpoint for updating Subsonic
        """

        url = config["subsonic"]["url"].as_str()
        if url and url.endswith("/"):
            url = url[:-1]

        # @deprecated("Use url config option instead")
        if not url:
            host = config["subsonic"]["host"].as_str()
            port = config["subsonic"]["port"].get(int)
            context_path = config["subsonic"]["contextpath"].as_str()
            if context_path == "/":
                context_path = ""
            url = f"http://{host}:{port}{context_path}"

        return url + f"/rest/{endpoint}"

    def authenticate(self):
        user = config["subsonic"]["user"].as_str()
        auth = config["subsonic"]["auth"].as_str()

        if auth == "token":
            salt, token = self.__create_token()
            payload = {
                "u": user,
                "t": token,
                "s": salt,
                "v": "1.13.0",  # Subsonic 5.3 and newer
                "c": "beets",
                "f": "json",
            }
        elif auth == "password":
            password = config["subsonic"]["pass"].as_str()
            encpass = hexlify(password.encode()).decode()
            payload = {
                "u": user,
                "p": f"enc:{encpass}",
                "v": "1.12.0",
                "c": "beets",
                "f": "json",
            }
        else:
            raise ValueError(f"Invalid authentication method: {auth}")

        return payload

    def send_request(self, url, payload):
        try:
            response = self.session.get(url, params=payload, timeout=5.0)
            response.raise_for_status()
            json = response.json()
            if json["subsonic-response"]["status"] == "ok":
                return json
            else:
                error_message = json["subsonic-response"]["error"]["message"]
                self._log.error(f"Error while processing JSON response: {error_message}")
                return None
        except requests.exceptions.RequestException as error:
            self._log.error(f"RequestException occurred while sending request: {error}")
            return None

    def close(self):
        self.session.close()

    def start_scan(self):
        """Start a scan of the Subsonic library."""
        try:
            payload = self.authenticate()
        except ValueError as e:
            self._log.error(f"Authentication failed: {e}")
            return

        # get scan status
        url = self.__format_url("getScanStatus")
        self._log.debug("URL is {0}", url)
        self._log.debug("auth type is {0}", config["subsonic"]["auth"])
        json = self.send_request(url, payload)
        if json and json["subsonic-response"]["scanStatus"]["scanning"]:
            self._log.info("Subsonic is currently scanning")
            return

        url = self.__format_url("startScan")
        self._log.debug("URL is {0}", url)
        self._log.debug("auth type is {0}", config["subsonic"]["auth"])
        json = self.send_request(url, payload)
        if json:
            count = json["subsonic-response"]["scanStatus"]["count"]
            self._log.info(f"Updating Subsonic; scanning {count} tracks")

    def subsonic_get_ids(self, items, force):
        """Get subsonic_id for items"""
        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            for item in tqdm(items, total=len(items)):
                if not force and hasattr(item, "subsonic_id"):
                    self._log.debug("subsonic_id already present for: {}", item)
                    continue
                future = executor.submit(self.get_song_id, item)
                item.subsonic_id = future.result()
                item.store()

    def get_song_id(self, item):
        """
        Retrieves the ID of a song from the Subsonic server based on the provided item.

        Args:
            item: The item object representing the song.

        Returns:
            The ID of the song if found, None otherwise.
        """

        url = self.__format_url("search3")
        payload = self.authenticate()
        if payload is None:
            return None
        if item.album == item.title:
            query = f"{item.title} {item.artist}"
        else:
            query = f"{item.album} {item.title}"
        payload = {**payload, "query": query, "songCount": 1}
        json = self.send_request(url, payload)
        if json and "song" in json["subsonic-response"]["searchResult3"]:
            song = json["subsonic-response"]["searchResult3"]["song"][0]
            id = song["id"]
            album = song["album"]
            artist = song["artist"]
            title = song["title"]
            self._log.debug(
                f"{item.album} - {item.artist} - {item.title} matched "
                f"with {id}: {album} - {artist} - {title}"
            )
            return id
        else:
            self._log.error(
                f"Could not find {item.album} - {item.artist} - "
                f"{item.title} in Subsonic library."
            )

    def update_rating(self, item, url, payload, rating_field):
        """
        Update the rating of an item on the Subsonic server.

        Args:
            item: The item to update the rating for.
            url: The URL of the Subsonic server.
            payload: Additional parameters to include in the request.

        Returns:
            None

        Raises:
            None
        """

        id = getattr(item, "subsonic_id", None)
        if id is None:
            id = self.get_song_id(item)

        try:
            rating = getattr(item, rating_field)
        except AttributeError:
            self._log.debug("No rating found for: {}", item)
            return

        rating = self.transform_rating(rating, rating_field)

        payload.update({
            "id": id,
            "rating": rating,
        })

        json = self.send_request(url, payload)
        if json:
            self._log.debug(f"Rating updated for {item}: {rating}")
        else:
            self._log.error("Error updating rating")

    def transform_rating(self, rating, rating_field):
        """Transform rating from beets to subsonic rating"""
        if rating_field == "plex_userrating":
            return round(rating / 2)
        elif rating_field == "spotify_track_popularity":
            popularity = float(rating)
            if popularity < 16.66:
                return 0
            elif popularity < 33.33:
                return 1
            elif popularity < 50:
                return 2
            elif popularity < 66.66:
                return 3
            elif popularity < 83.33:
                return 4
            else:
                return 5
        else:
            return int(rating)

    def subsonic_add_rating(self, items, rating_field):
        url = self.__format_url("setRating")
        payload = self.authenticate()
        if payload is None:
            return

        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            list(
                tqdm(
                    executor.map(
                        lambda item: self.update_rating(
                            item, url, payload, rating_field
                        ),
                        items,
                    ),
                    total=len(items),
                )
            )

    def subsonic_scrobble(self, items):
        url = self.__format_url("scrobble")
        payload = self.authenticate()
        if payload is None:
            return

        for item in tqdm(items, total=len(items)):
            self.scrobble(item, url, payload)

    def scrobble(self, item, url, payload):
        """
        Scrobble an item to the Subsonic server.

        Args:
            item: The item to scrobble.
            url: The URL of the Subsonic server.
            payload: Additional parameters to include in the request.

        Returns:
            None

        Raises:
            None
        """

        if not hasattr(item, "subsonic_id"):
            id = self.get_song_id(item)
        else:
            id = item.subsonic_id
        try:
            payload = {
                **payload,
                "id": id,
                "time": int(item.plex_lastviewedat) * 1000,  # convert to milliseconds
            }
        except AttributeError:
            self._log.debug("No scrobble time found for: {}", item)
            return

        json = self.send_request(url, payload)
        if json:
            self._log.debug(f"Scrobbled {item}")
        else:
            self._log.error("Error scrobbling")
