from dataclasses import field
from pathlib import Path
from typing import TYPE_CHECKING

from cyberdrop_dl.utils.utilities import sanitize_folder

if TYPE_CHECKING:
    from rich.progress import TaskID
    from yarl import URL


class MediaItem:
    def __init__(self, url: "URL", referer: "URL", download_folder: Path, filename: str, ext: str, original_filename: str):
        self.url: URL = url
        self.referer: URL = referer
        self.download_folder: Path = download_folder
        self.filename: str = filename
        self.ext: str = ext
        self.download_filename: str = field(init=False)
        self.original_filename: str = original_filename
        self.datetime: str = field(init=False)
        self.filesize: int = field(init=False)
        self.current_attempt: int = field(init=False)
        self.download_task_id: TaskID = field(init=False)


class ScrapeItem:
    def __init__(self, url: "URL", parent_title: str, part_of_album: bool = False, possible_datetime: int = None,
                 retry: bool = False, retry_path: Path = None):
        self.url: URL = url
        self.parent_title: str = parent_title
        self.part_of_album: bool = part_of_album
        self.possible_datetime: int = possible_datetime
        self.retry: bool = retry
        self.retry_path: Path = retry_path

    async def add_to_parent_title(self, title: str) -> None:
        """Adds a title to the parent title"""
        if not title or self.retry:
            return
        title = await sanitize_folder(title)
        self.parent_title = (self.parent_title + "/" + title) if self.parent_title else title
