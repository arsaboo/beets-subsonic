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


class SubsonicPlugin(BeetsPlugin):

    data_source = "Subsonic"

    def __init__(self):
        super().__init__()
        # Set default configuration values
        config["subsonic"].add(
            {
                "user": "admin",
                "pass": "admin",
                "url": "http://localhost:4040",
                "auth": "token",
            }
        )
        config["subsonic"]["pass"].redact = True
        self.register_listener("database_change", self.db_change)
        self.register_listener("smartplaylist_update", self.spl_update)

    def db_change(self, lib, model):
        self.register_listener("cli_exit", self.start_scan)

    def spl_update(self):
        self.register_listener("cli_exit", self.start_scan)

    def commands(self):
        """Add beet UI commands to interact with Subsonic."""

        # Subsonic update command
        subsonicupdate_cmd = ui.Subcommand(
            "subsonicupdate", help=f"Update {self.data_source} library"
        )

        def func(lib, opts, args):
            self.start_scan()

        subsonicupdate_cmd.func = func

        # Subsonic rating update command
        subsonicaddrating_cmd = ui.Subcommand(
            "subsonicaddrating", help=f"Add ratings to {self.data_source} library"
        )

        def func_add_rating(lib, opts, args):
            items = lib.items(ui.decargs(args))
            self.subsonic_add_rating(items)

        subsonicaddrating_cmd.func = func_add_rating

        # get subsonic ids
        subsonic_get_ids_cmd = ui.Subcommand(
            "subsonicgetids", help=f"Get Subsonic ids for items"
        )

        def func_get_ids(lib, opts, args):
            items = lib.items(ui.decargs(args))
            self.subsonic_get_ids(items)

        subsonic_get_ids_cmd.func = func_get_ids

        return [subsonicupdate_cmd, subsonicaddrating_cmd, subsonic_get_ids_cmd]

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
            return None

        return payload

    def start_scan(self):
        url = self.__format_url("startScan")
        self._log.debug("URL is {0}", url)
        self._log.debug("auth type is {0}", config["subsonic"]["auth"])

        payload = self.authenticate()
        if payload is None:
            return

        try:
            response = requests.get(url, params=payload)
            json = response.json()

            if (
                response.status_code == 200
                and json["subsonic-response"]["status"] == "ok"
            ):
                count = json["subsonic-response"]["scanStatus"]["count"]
                self._log.info(f"Updating Subsonic; scanning {count} tracks")
            elif (
                response.status_code == 200
                and json["subsonic-response"]["status"] == "failed"
            ):
                error_message = json["subsonic-response"]["error"]["message"]
                self._log.error(f"Error: {error_message}")
            else:
                self._log.error("Error: {0}", json)
        except Exception as error:
            self._log.error(f"Error: {error}")

    def subsonic_get_ids(self, items):
        for item in items:
            if not hasattr(item, 'subsonic_id'):
                item.subsonic_id = self.get_song_id(item)
                # item.store()

    def get_song_id(self, item):
        url = self.__format_url("search3")
        payload = self.authenticate()
        if payload is None:
            return None
        if item.album == item.title:
            query = f"{item.title} {item.artist}"
        else:
            query = f"{item.album} {item.title}"
        try:
            response = requests.get(
                url, params={**payload, "query": query, "songCount": 1}
            )
            json = response.json()
            if (
                response.status_code == 200
                and json["subsonic-response"]["status"] == "ok"
            ):
                id = json["subsonic-response"]["searchResult3"]["song"][0]["id"]
                album = json["subsonic-response"]["searchResult3"]["song"][0]["album"]
                artist = json["subsonic-response"]["searchResult3"]["song"][0]["artist"]
                title = json["subsonic-response"]["searchResult3"]["song"][0]["title"]
                self._log.debug(
                    f"{item.album} - {item.artist} - {item.title} matched with {id}: {album} - {artist} - {title}"
                )
            else:
                self._log.error("Error: {0}", json)
        except Exception as error:
            self._log.error(f"Error: {error}")
