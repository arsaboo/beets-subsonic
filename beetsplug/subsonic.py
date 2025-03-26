"""
Adds Subsonic support to Beets.
"""

import hashlib
import random
import string
from binascii import hexlify

import requests
import enlighten

from beets import config, ui
from beets.plugins import BeetsPlugin
from concurrent.futures import ThreadPoolExecutor, as_completed


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
                "auto_scan": True,
            }
        )
        config["subsonic"]["pass"].redact = True
        self.session = requests.Session()
        self.register_listener("database_change", self.db_change)
        self.register_listener("smartplaylist_update", self.spl_update)

    def db_change(self, lib, model):
        if self.config["auto_scan"].get(bool):
            self.register_listener("cli_exit", self.start_scan)

    def spl_update(self):
        if self.config["auto_scan"].get(bool):
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
            "subsonic_addrating",
            help=f"Add ratings to {self.data_source} library",
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

            # Check if we got a valid response
            if "subsonic-response" not in json:
                self._log.error(
                    "Invalid response from server: missing subsonic-response"
                )
                return None

            if json["subsonic-response"]["status"] == "ok":
                return json
            else:
                error = json["subsonic-response"].get("error", {})
                error_message = error.get("message", "Unknown error")
                error_code = error.get("code", "Unknown code")
                if str(error_code) == "70":
                    self._log.warning(
                        f"Server returned error 70 (data not found): {error_message}"
                    )
                    return None
                self._log.error(f"Server returned error {error_code}: {error_message}")
                return None
        except requests.exceptions.RequestException as error:
            self._log.error(f"RequestException occurred while sending request: {error}")
            return None
        except ValueError as error:
            self._log.error(f"Invalid JSON response from server: {error}")
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
        manager = enlighten.get_manager()
        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            counter = manager.counter(total=len(items), desc='Getting IDs', unit='items')
            for item in items:
                if not force and hasattr(item, "subsonic_id"):
                    self._log.debug("subsonic_id already present for: {}", item)
                    counter.update()
                    continue
                future = executor.submit(self.get_song_id, item)
                item.subsonic_id = future.result()
                item.store()
                counter.update()
            counter.close()

    def get_song_id(self, item):
        """
        Retrieves the ID of a song from the Subsonic server using multiple search strategies.
        """
        url = self.__format_url("search3")
        payload = self.authenticate()
        if payload is None:
            return None

        # Clean artist name to handle featuring artists and multiple artists
        artist = item.artist.split(",")[0].strip() if "," in item.artist else item.artist

        # Since title-only searches work well, start with the simplest strategy
        search_strategies = [
            lambda: item.title.strip(),                           # just the title (most successful)
            lambda: f'"{item.title.strip()}"',                    # exact title only
            lambda: f'{item.title.strip()} {item.album.strip()}', # title and album
            lambda: f'{artist.strip()} {item.title.strip()}',     # artist and title without quotes
            lambda: item.album.strip(),                           # just the album (fallback)
        ]

        # Store all songs found for lenient matching later
        all_potential_matches = []

        for strategy in search_strategies:
            query = strategy()
            self._log.debug(f"Trying search query: {query}")

            search_payload = {**payload, "query": query, "songCount": 20}
            json = self.send_request(url, search_payload)

            if not json:
                continue

            search_result = json["subsonic-response"].get("searchResult3", {})
            if "song" not in search_result:
                self._log.debug(f"No results found for query: {query}")
                continue

            # Process the results
            for song in search_result["song"]:
                all_potential_matches.append(song)

                # Try for exact match first
                if item.title.lower() == song["title"].lower():
                    self._log.debug(
                        f"Exact title match found:\n"
                        f"Beets:    {item.artist} - {item.title} ({item.album})\n"
                        f"Subsonic: {song.get('artist', 'Unknown')} - {song['title']} ({song.get('album', 'Unknown')})"
                    )
                    return song["id"]

        # If we haven't found an exact match, try lenient matching on all potential matches
        if all_potential_matches:
            # Sort by normalized edit distance to find closest match
            self._log.debug(f"Trying lenient matching on {len(all_potential_matches)} potential matches")

            for song in all_potential_matches:
                title_normalized = item.title.lower().strip()
                song_title_normalized = song["title"].lower().strip()

                # Check for title substring in either direction
                if title_normalized in song_title_normalized or song_title_normalized in title_normalized:
                    self._log.debug(
                        f"Lenient match found:\n"
                        f"Beets:    {item.artist} - {item.title} ({item.album})\n"
                        f"Subsonic: {song.get('artist', 'Unknown')} - {song['title']} ({song.get('album', 'Unknown')})"
                    )
                    return song["id"]

        # Try album search as final fallback
        album_id = self.get_album_id_by_name(item.album, artist, payload)
        if album_id:
            song_id = self.find_song_in_album(album_id, item.title, payload)
            if song_id:
                return song_id

        self._log.warning(
            f"Could not find match for:\n"
            f"Title: {item.title}\n"
            f"Artist: {item.artist}\n"
            f"Album: {item.album}"
        )
        return None

    def get_album_id_by_name(self, album_name, artist_name, payload):
        """
        Try to find an album ID by name and artist
        """
        url = self.__format_url("search3")
        search_payload = {**payload, "query": album_name, "albumCount": 10}
        json = self.send_request(url, search_payload)

        if not json:
            return None

        search_result = json["subsonic-response"].get("searchResult3", {})
        if "album" not in search_result:
            return None

        for album in search_result["album"]:
            if album_name.lower() in album["name"].lower():
                self._log.debug(f"Found album match: {album['name']}")
                return album["id"]

        return None

    def find_song_in_album(self, album_id, song_title, payload):
        """
        Find a song within an album by title
        """
        url = self.__format_url("getAlbum")
        album_payload = {**payload, "id": album_id}
        json = self.send_request(url, album_payload)

        if not json:
            return None

        album_data = json["subsonic-response"].get("album", {})
        if "song" not in album_data:
            return None

        for song in album_data["song"]:
            if song_title.lower() in song["title"].lower():
                self._log.debug(f"Found song in album: {song['title']}")
                return song["id"]

        return None

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
            self._log.debug(f"No subsonic_id found for {item}, attempting to fetch it")
            id = self.get_song_id(item)
            if id is None:
                self._log.error(
                    f"Could not find song ID for {item}, skipping rating update"
                )
                return

        try:
            rating = getattr(item, rating_field)
        except AttributeError:
            self._log.debug(f"No {rating_field} found for: {item}")
            return

        rating = self.transform_rating(rating, rating_field)
        if rating is None:
            self._log.error(f"Invalid rating value for {item}")
            return

        request_payload = payload.copy()
        request_payload.update(
            {
                "id": id,
                "rating": rating,
            }
        )

        self._log.debug(f"Updating rating for {item} (ID: {id}) to {rating}")
        json = self.send_request(url, request_payload)
        if json:
            self._log.debug(f"Successfully updated rating for {item}: {rating}")
        else:
            self._log.error(f"Failed to update rating for {item}")

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

        manager = enlighten.get_manager()
        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            counter = manager.counter(total=len(items), desc='Updating ratings', unit='items')
            futures = []
            for item in items:
                future = executor.submit(self.update_rating, item, url, payload, rating_field)
                futures.append(future)

            for future in as_completed(futures):
                counter.update()
            counter.close()

    def subsonic_scrobble(self, items):
        url = self.__format_url("scrobble")
        payload = self.authenticate()
        if payload is None:
            return

        manager = enlighten.get_manager()
        counter = manager.counter(total=len(items), desc='Scrobbling', unit='items')

        for item in items:
            self.scrobble(item, url, payload)
            counter.update()
        counter.close()

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
