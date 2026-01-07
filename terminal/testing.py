from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import DirectoryTree, Footer, Header, Input, ListItem, ListView, Static


@dataclass(frozen=True)
class PathItem:
    path: Path
    is_dir: bool


class PathRow(ListItem):
    """One row in the search results list."""
    def __init__(self, item: PathItem) -> None:
        self.item = item
        super().__init__(Static(str(item.path)))


class FileSelected(Message):
    """Emitted when the user selects a file."""
    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path


def walk_paths(root: Path, *, follow_symlinks: bool = False) -> List[PathItem]:
    """
    Fast-ish path indexing: collect file + dir paths under root.
    This does NOT read file contents.
    """
    out: List[PathItem] = []
    root = root.resolve()

    # os.walk is usually faster than pure Path.rglob for large trees.
    for dirpath, dirnames, filenames in os.walk(root, followlinks=follow_symlinks):
        d = Path(dirpath)

        # record dirs
        for dn in dirnames:
            out.append(PathItem(d / dn, True))

        # record files
        for fn in filenames:
            out.append(PathItem(d / fn, False))

    return out


def simple_match(haystack: str, needle: str) -> bool:
    """Simple case-insensitive substring match."""
    return needle in haystack


class FilePickerApp(App):
    CSS = """
    Screen { layout: vertical; }
    #body { height: 1fr; }
    #left { width: 1fr; min-width: 40; }
    #right { width: 1fr; min-width: 40; }
    #status { height: 3; }
    """

    # reactive state: when these change, we can update UI in watchers
    indexed_count: int = reactive(0)
    indexing_done: bool = reactive(False)
    query: str = reactive("")

    def __init__(self, root: str | Path = ".") -> None:
        super().__init__()
        self.root = Path(root).resolve()
        self._index: List[PathItem] = []          # all indexed paths
        self._filtered: List[PathItem] = []       # current search results

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal(id="body"):
            with Vertical(id="left"):
                yield Static(f"Directory: {self.root}")
                yield DirectoryTree(str(self.root), id="tree")

            with Vertical(id="right"):
                yield Input(placeholder="Search paths (type to filter)…", id="search")
                yield ListView(id="results")
                yield Static("", id="status")

        yield Footer()

    async def on_mount(self) -> None:
        # kick off background indexing without blocking UI
        self.set_focus(self.query_one("#search", Input))
        self.run_worker(self._build_index(), name="build-index", exclusive=True)

    async def _build_index(self) -> None:
        self.indexing_done = False
        self.indexed_count = 0
        self._index.clear()

        # Run indexing off the main event loop
        items = await asyncio.to_thread(walk_paths, self.root)

        # Store and mark done
        self._index = items
        self.indexed_count = len(items)
        self.indexing_done = True

        # Apply current query once index is ready
        self._apply_filter()

    def watch_indexed_count(self, count: int) -> None:
        status = self.query_one("#status", Static)
        if not self.indexing_done:
            status.update(f"Indexing… (found {count} paths so far)")
        else:
            status.update(f"Indexed {count} paths. Ready.")

    def watch_indexing_done(self, done: bool) -> None:
        # Trigger status refresh
        self.watch_indexed_count(self.indexed_count)

    def watch_query(self, q: str) -> None:
        self._apply_filter()

    def _apply_filter(self) -> None:
        """Filter index -> populate results list (cap size to keep UI snappy)."""
        results = self.query_one("#results", ListView)
        results.clear()

        q = self.query.strip().lower()
        if not q:
            # show nothing by default; or show a few recent/roots if you prefer
            self._filtered = []
            return

        # Filter (cap to avoid rendering thousands of rows)
        matched: List[PathItem] = []
        for item in self._index:
            # search on string path
            if simple_match(str(item.path).lower(), q):
                if not item.is_dir:  # only files in results; change if you want dirs too
                    matched.append(item)
                if len(matched) >= 200:
                    break

        self._filtered = matched

        for item in matched:
            results.append(PathRow(item))

        status = self.query_one("#status", Static)
        if self.indexing_done:
            status.update(f"{len(matched)} matches (showing up to 200). Indexed {self.indexed_count} total.")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search":
            self.query = event.value

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        # User selected a search result
        row = event.item
        if isinstance(row, PathRow):
            self.post_message(FileSelected(row.item.path))

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        # User selected a file from the tree
        self.post_message(FileSelected(Path(event.path)))

    async def on_file_selected(self, event: FileSelected) -> None:
        # Do something with the selected file
        # (e.g., open it, load into context, display preview, etc.)
        path = event.path
        status = self.query_one("#status", Static)
        status.update(f"Selected: {path}")
        # Example: exit with the path
        # self.exit(str(path))


if __name__ == "__main__":
    FilePickerApp(root=".").run()
