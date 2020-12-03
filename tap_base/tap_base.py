"""TapBase abstract class."""

import abc
import json
import logging

from typing import List, Optional, Type, Dict
from pathlib import Path

from singer import Catalog, CatalogEntry
from singer.messages import StateMessage

from tap_base.plugin_base import PluginBase
from tap_base.tap_stream_base import TapStreamBase
from tap_base.connection_base import GenericConnectionBase


class TapBase(PluginBase, metaclass=abc.ABCMeta):
    """Abstract base class for taps."""

    _stream_class: Type[TapStreamBase]
    _streams: Dict[str, TapStreamBase] = {}
    _catalog: Catalog

    # Constructor

    def __init__(
        self,
        plugin_name: str,
        version: str,
        capabilities: List[str],
        accepted_options: List[str],
        option_set_requirements: List[List[str]],
        connection_class: Type[GenericConnectionBase],
        stream_class: Type[TapStreamBase],
        config: dict,
        state: dict = None,
    ) -> None:
        """Initialize the tap."""
        self._stream_class = stream_class
        self._catalog = None
        super().__init__(
            plugin_name=plugin_name,
            version=version,
            capabilities=capabilities,
            accepted_options=accepted_options,
            option_set_requirements=option_set_requirements,
            connection_class=connection_class,
            config=config,
        )

    # Abstract stream detection methods:

    def get_all_stream_ids(
        self, allow_load: bool = True, allow_discover: bool = False
    ) -> List[str]:
        self.init_catalog(allow_load=allow_load, allow_discover=allow_discover)
        return list(self._streams.keys())

    def get_stream(
        self, tap_stream_id, allow_load: bool = True, allow_discover: bool = False
    ) -> TapStreamBase:
        self.init_catalog(allow_load=allow_load, allow_discover=allow_discover)
        return self._streams[tap_stream_id]

    def get_streams(
        self, allow_load: bool = True, allow_discover: bool = False
    ) -> Dict[str, TapStreamBase]:
        self.init_catalog(allow_load=allow_load, allow_discover=allow_discover)
        return self._streams

    # Standard catalog functions

    def init_catalog(
        self, allow_load: bool = True, allow_discover: bool = False
    ) -> Catalog:
        """Return a catalog object."""
        if not self._catalog:
            catalog_path = self.get_config("catalog_path", None)
            if allow_load and catalog_path and Path(catalog_path).exists():
                self.read_catalog_file(catalog_path)
            elif allow_discover and self._conn._is_discoverable:
                print("Catalog is not yet populated. Attempting discovery...")
                self._catalog = self._conn.discover_catalog()
        self._init_streams()
        return self._catalog

    def _init_streams(self):
        if not self._catalog:
            raise RuntimeError("Catalog must be initialized before streams.")
        catalog_entry: CatalogEntry
        for catalog_entry in self._catalog.streams:
            self._init_stream(
                tap_stream_id=catalog_entry.tap_stream_id,
                catalog_entry=catalog_entry,
                state=None,
                logger=self.logger,
            )

    def _init_stream(
        self,
        tap_stream_id: str,
        catalog_entry: CatalogEntry,
        state: Optional[StateMessage],
        logger: logging.Logger,
    ) -> TapStreamBase:
        self.logger = logger
        new_stream = self._stream_class(
            tap_stream_id=tap_stream_id,
            connection=self._conn,
            catalog_entry=catalog_entry,
            state=state,
        )
        self._streams[tap_stream_id] = new_stream
        return new_stream

    def read_catalog_file(self, filepath) -> Catalog:
        """Return a list of all streams (tables)."""
        self._catalog = Catalog.load(filepath)
        return self._catalog

    def write_catalog_file(self, filepath) -> str:
        """Return a list of all streams (tables)."""
        Path(filepath).write_text(self.get_catalog_file_text())
        return filepath

    def get_catalog_file_text(self) -> str:
        """Return the catalog file text."""
        return json.dumps(self._catalog.to_dict())

    def get_catalog_entry(self, tap_stream_id: str) -> CatalogEntry:
        self._catalog.get_stream(tap_stream_id)

    # def get_selected_catalog_entries(self, tap_stream_id: str) -> List[CatalogEntry]:
    #     TODO: requires `state` arg
    #     self._catalog.get_selected_streams(state=state)

    # Standard CLI Functions:

    def handle_cli_args(self, args, cwd, environ) -> None:
        """Take necessary action in response to a CLI command."""
        pass

    def sync_one(
        self, tap_stream_id: str, allow_load: bool = True, allow_discover: bool = False
    ):
        stream = self.get_stream(tap_stream_id, allow_load, allow_discover)
        stream.sync()

    def sync_all(self, allow_load: bool = True, allow_discover: bool = False):
        for tap_stream_id, stream in self.get_streams(
            allow_load=allow_load, allow_discover=allow_discover
        ).items():
            stream.sync()