"""TapBase abstract class."""

import abc
import json
from logging import Logger

from singer.catalog import Catalog
from tap_base.helpers import classproperty

from typing import Any, List, Optional, Type, Dict
from pathlib import Path

import click

from tap_base.plugin_base import PluginBase
from tap_base.streams.core import TapStreamBase


class TapBase(PluginBase, metaclass=abc.ABCMeta):
    """Abstract base class for taps."""

    # TODO: Remove (Should be object-level, not class-level)
    # _streams: Dict[str, TapStreamBase] = {}

    default_stream_class: Optional[Type[TapStreamBase]] = None
    # Constructor

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        catalog: Optional[Dict[str, Any]] = None,
        state: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize the tap."""
        self._state = state or {}
        self._streams: Dict[str, TapStreamBase] = {}
        super().__init__(config=config)
        if catalog:
            self.logger.info("loading catalog streams...")
            self.load_catalog_streams(
                catalog=catalog, config=self._config, state=self._state,
            )
        else:
            self.logger.info("discovering catalog streams...")
            self.discover_catalog_streams()

    @classmethod
    def get_stream_class(cls, stream_name: str) -> Type[TapStreamBase]:
        if not cls.default_stream_class:
            raise ValueError(
                "No stream class detected for '{cls.name}' stream '{stream_name}'"
                "and no default_stream_class defined."
            )
        return cls.default_stream_class

    @property
    def streams(self) -> Dict[str, TapStreamBase]:
        return self._streams

    @property
    def capabilities(self) -> List[str]:
        """Return a list of supported capabilities."""
        result = ["sync", "catalog", "state"]
        if self.discoverable:
            result.append("discover")
        return result

    # Abstract stream detection methods:

    def load_catalog_streams(self, catalog: dict, state: dict, config: dict) -> None:
        streams: List[Dict] = catalog["streams"]
        for stream in streams:
            stream_name = stream["tap_stream_id"]
            new_stream = self.get_stream_class(stream_name).from_stream_dict(
                stream_dict=stream, state=state, config=config
            )
            self._streams[stream_name] = new_stream

    def discover_catalog_streams(self) -> None:
        raise NotImplementedError(
            f"Tap '{self.name}' does not support discovery. "
            "Please set the '--catalog' command line argument and try again."
        )

    def run_discovery(self) -> str:
        """Write the catalog json to STDOUT and return the same as a string."""
        catalog_json = self.get_catalog_json()
        print(catalog_json)
        return catalog_json

    def get_singer_catalog(self) -> Catalog:
        """Return a Catalog object."""
        catalog_entries = [
            stream.singer_catalog_entry for stream in self.streams.values()
        ]
        return Catalog(catalog_entries)

    def get_catalog_json(self) -> str:
        return json.dumps(self.get_singer_catalog().to_dict(), indent=2)

    # Sync methods

    def sync_one(self, tap_stream_id: str):
        """Sync a single stream."""
        if tap_stream_id not in self.streams:
            raise ValueError(
                f"Could not find stream '{tap_stream_id}' in streams list: "
                f"{sorted(self.streams.keys())}"
            )
        stream = self.streams[tap_stream_id]
        stream.sync()

    def sync_all(self):
        """Sync all streams."""
        for stream in self.streams.values():
            stream.sync()

    # Command Line Execution

    @classmethod
    def cli(
        cls,
        version: bool = False,
        discover: bool = False,
        config: str = None,
        state: str = None,
        catalog: str = None,
    ):
        """Handle command line execution."""

        def read_optional_json(path: Optional[str]) -> Optional[Dict[str, Any]]:
            if not path:
                return None
            return json.loads(Path(path).read_text())

        if version:
            cls.print_version()
            return
        config_dict = read_optional_json(config)
        state_dict = read_optional_json(state)
        catalog_dict = read_optional_json(catalog)
        tap = cls(config=config_dict, state=state_dict, catalog=catalog_dict)
        if discover:
            tap.run_discovery()
        else:
            tap.sync_all()


@click.option("--version", is_flag=True)
@click.option("--discover", is_flag=True)
@click.option("--config")
@click.option("--catalog")
@click.command()
def cli(
    discover: bool = False,
    config: str = None,
    catalog: str = None,
    version: bool = False,
):
    TapBase.cli(version=version, discover=discover, config=config, catalog=catalog)
