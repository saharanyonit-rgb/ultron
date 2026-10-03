"""Structured-data parsing and single-shot web fetching.

These fill a gap the rest of the toolset leaves open: the browser tools are
session-based and interactive, and the file tools move bytes around, but nothing
could turn a CSV/JSON/XML/HTML payload into something the model can reason about.
Parsing is done with the standard library (`csv`, `json`, `xml.etree`,
`html.parser`) so the frozen build needs no extra dependency.

Every `parse_*`/`query_*` tool is READ: it inspects text and returns structure,
and never writes. `download_file` is the one exception, because it writes to
disk.

All parsers accept either inline `text` or a `path`, so the same tool works on
a pasted snippet and on a file the agent just fetched.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import statistics
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ultron.network_security import NetworkSecurityGuard
from ultron.risk import RiskLevel
from ultron.tools.base import Tool

_GUARD = NetworkSecurityGuard()

# Cap returned rows/cells so a large file cannot blow up the context window.
_MAX_ROWS = 200
_MAX_CELL_CHARS = 400
_FETCH_TIMEOUT = 30.0
_MAX_FETCH_BYTES = 5 * 1024 * 1024


def _read_source(text: str | None, path: str | None, limit: int = _MAX_FETCH_BYTES) -> tuple[str, str]:
    """Return `(content, origin)` from inline text or a file path."""
    if text:
        return text[:limit], "inline"
    if not path:
        return "", ""
    target = Path(path).expanduser()
    if not target.is_file():
        return "", f"error: not a file: {target}"
    try:
        if target.stat().st_size > limit:
            with target.open("r", encoding="utf-8", errors="replace") as fh:
                return fh.read(limit), f"file:{target} (truncated)"
        return target.read_text(encoding="utf-8", errors="replace"), f"file:{target}"
    except OSError as exc:
        return "", f"error: could not read {target}: {exc}"


def _clip(value: Any) -> Any:
    if isinstance(value, str) and len(value) > _MAX_CELL_CHARS:
        return value[:_MAX_CELL_CHARS] + "..."
    return value


class _TextExtractor(HTMLParser):
    """Collect visible text, links, tables and metadata from HTML."""

    _SKIP = {"script", "style", "noscript", "template", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.meta: dict[str, str] = {}
        self.links: list[dict[str, str]] = []
        self.tables: list[dict[str, Any]] = []
        self._text: list[str] = []
        self._skip_depth = 0
        self._in_title = False
        self._link: dict[str, str] | None = None
        self._table: dict[str, Any] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attr = {k.lower(): (v or "") for k, v in attrs}

        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = (attr.get("name") or attr.get("property") or "").lower()
            if key:
                self.meta[key] = attr.get("content", "")
        elif tag == "a":
            self._link = {"href": attr.get("href", ""), "text": ""}
        elif tag == "table":
            self._table = {"headers": [], "rows": []}
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
            if tag == "th" and self._table is not None and not self._table["headers"]:
                self._table["headers"] = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self._SKIP:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag == "title":
            self._in_title = False
        elif tag == "a" and self._link is not None:
            if self._link["href"]:
                self.links.append({"href": self._link["href"], "text": self._link["text"].strip()})
            self._link = None
        elif tag in ("td", "th") and self._cell is not None:
            value = " ".join("".join(self._cell).split())
            if self._row is not None:
                self._row.append(value)
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            if self._row and any(self._row):
                self._table["rows"].append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_title:
            self.title += data.strip()
            return
        if self._cell is not None:
            self._cell.append(data)
        elif self._link is not None:
            self._link["text"] += data
        if data.strip():
            self._text.append(data.strip())

    @property
    def text(self) -> str:
        joined = " ".join(self._text)
        return re.sub(r"\s+", " ", joined).strip()


def _fetch(url: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Validate and fetch a URL. Returns `(response_dict, error_dict)`."""
    import httpx

    target = url if "://" in url else f"https://{url}"
    verdict = _GUARD.validate_url(target)
    if not verdict.allowed:
        return None, {"error": f"URL blocked: {verdict.reason}"}
    try:
        with httpx.Client(follow_redirects=True, timeout=_FETCH_TIMEOUT) as client:
            response = client.get(target, headers={"User-Agent": "ultron/1.0"})
    except Exception as exc:  # noqa: BLE001 - network failures are expected
        return None, {"error": f"fetch failed for {target}: {type(exc).__name__}: {exc}"}
    return response, None


class ParseCsv(Tool):
    name = "parse_csv"
    risk = RiskLevel.READ
    category = "data"
    keywords = (
        "parse csv",
        "read csv",
        "load csv",
        "csv to rows",
        "parse spreadsheet",
        "read table data",
    )
    description = (
        "Parse CSV text or a .csv file into headers and row objects. Returns "
        "at most 200 rows."
    )
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Inline CSV content."},
            "path": {"type": "string", "description": "Path to a .csv file."},
            "delimiter": {"type": "string", "description": "Field delimiter (default ',')."},
            "limit": {"type": "integer", "description": "Max rows to return."},
        },
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "headers": {"type": "array"},
            "rows": {"type": "array"},
            "row_count": {"type": "integer"},
            "truncated": {"type": "boolean"},
        },
    }

    def run(
        self,
        text: str | None = None,
        path: str | None = None,
        delimiter: str = ",",
        limit: int = _MAX_ROWS,
        **_: Any,
    ) -> dict[str, Any]:
        content, origin = _read_source(text, path)
        if content.startswith("error:"):
            return {"error": content[6:].strip()}
        if not content.strip():
            return {"error": "no CSV content supplied", "origin": origin}

        sep = (delimiter or ",")[0]
        reader = csv.reader(io.StringIO(content), delimiter=sep)
        try:
            raw = list(reader)
        except csv.Error as exc:
            return {"error": f"could not parse CSV: {exc}"}
        if not raw:
            return {"error": "CSV contained no rows", "origin": origin}

        headers = [h.strip() for h in raw[0]]
        cap = max(1, min(int(limit), _MAX_ROWS))
        body = raw[1:]
        rows = []
        for record in body[:cap]:
            padded = list(record) + [""] * (len(headers) - len(record))
            rows.append({h: _clip(v) for h, v in zip(headers, padded[: len(headers)], strict=False)})
        return {
            "origin": origin,
            "headers": headers,
            "rows": rows,
            "row_count": len(body),
            "truncated": len(body) > cap,
        }


class SummarizeCsv(Tool):
    name = "summarize_csv"
    risk = RiskLevel.READ
    category = "data"
    keywords = (
        "summarize csv",
        "csv summary",
        "column statistics",
        "analyze csv",
        "data summary",
        "average of column",
        "stats for csv",
    )
    description = (
        "Compute per-column statistics for a CSV: value counts, and min/max/"
        "mean/median for numeric columns. Use `column` to restrict it."
    )
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "path": {"type": "string"},
            "column": {"type": "string", "description": "Only summarize this column."},
            "delimiter": {"type": "string"},
            "sample": {
                "type": "integer",
                "description": "Rows to sample (default 5000).",
            },
        },
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {"columns": {"type": "object"}, "row_count": {"type": "integer"}},
    }

    def run(
        self,
        text: str | None = None,
        path: str | None = None,
        column: str = "",
        delimiter: str = ",",
        sample: int = 5000,
        **_: Any,
    ) -> dict[str, Any]:
        content, origin = _read_source(text, path)
        if content.startswith("error:"):
            return {"error": content[6:].strip()}
        if not content.strip():
            return {"error": "no CSV content supplied", "origin": origin}

        sep = (delimiter or ",")[0]
        reader = csv.reader(io.StringIO(content), delimiter=sep)
        rows = list(reader)
        if not rows:
            return {"error": "CSV contained no rows", "origin": origin}

        headers = [h.strip() for h in rows[0]]
        body = rows[1:][: max(1, min(int(sample), 100_000))]
        if column:
            if column not in headers:
                return {"error": f"column {column!r} not found", "headers": headers}
            targets = [column]
        else:
            targets = headers

        summary: dict[str, Any] = {}
        for header in targets:
            index = headers.index(header)
            values = [r[index] if index < len(r) else "" for r in body]
            present = [v for v in values if v not in ("", None)]
            entry: dict[str, Any] = {
                "non_empty": len(present),
                "empty": len(values) - len(present),
                "distinct": len(set(present)),
            }
            numbers: list[float] = []
            for value in present:
                try:
                    numbers.append(float(str(value).replace(",", "")))
                except (TypeError, ValueError):
                    pass
            if present and len(numbers) == len(present):
                entry["numeric"] = True
                entry["min"] = min(numbers)
                entry["max"] = max(numbers)
                entry["mean"] = round(statistics.fmean(numbers), 4)
                entry["median"] = round(statistics.median(numbers), 4)
            else:
                entry["numeric"] = False
                top = sorted({v: present.count(v) for v in set(present)}.items(),
                             key=lambda kv: -kv[1])[:5]
                entry["most_common"] = [{"value": _clip(v), "count": c} for v, c in top]
            summary[header] = entry
        return {"origin": origin, "row_count": len(body), "columns": summary}


_SEGMENT_RE = re.compile(r"^([^\[\]]*)((?:\[\d+\]|\[\*\])*)$")


def _resolve_path(data: Any, path: str) -> tuple[Any, str | None]:
    """Walk a dotted path with `[n]` indexes and a `[*]` wildcard.

    A bare numeric segment indexes a list but is a dict key on a dict, so
    `{"1": ...}` still resolves. `[*]` flattens a list and applies the rest of
    the path to each element, which is why `items[*].id` works.
    """
    segments = [s.strip() for s in str(path).split(".") if s.strip()]
    if not segments:
        return data, None
    value, failure = _walk(data, segments)
    return value, failure


def _walk(current: Any, segments: list[str]) -> tuple[Any, str | None]:
    segment, rest = segments[0], segments[1:]

    match = _SEGMENT_RE.match(segment)
    if not match:
        return None, f"invalid path segment {segment!r}"
    name, brackets = match.group(1), match.group(2)

    indexes = re.findall(r"\[(\d+)\]", brackets)
    wildcard = "[*]" in brackets

    # Step into the container.
    if name:
        if isinstance(current, list) and name.isdigit():
            position = int(name)
            if position >= len(current):
                return None, f"index {position} out of range (length {len(current)})"
            current = current[position]
        elif isinstance(current, dict):
            if name not in current:
                return None, f"no key {name!r} at this level"
            current = current[name]
        else:
            return None, f"cannot look up {name!r} inside a {type(current).__name__}"

    for index in indexes:
        if not isinstance(current, list):
            return None, f"cannot index a {type(current).__name__}"
        position = int(index)
        if position >= len(current):
            return None, f"index {position} out of range (length {len(current)})"
        current = current[position]

    if not rest:
        return current, None

    if wildcard:
        if not isinstance(current, list):
            return None, f"'[*]' needs a list, found {type(current).__name__}"
        collected: list[Any] = []
        for item in current:
            value, failure = _walk(item, rest)
            if failure:
                continue  # partial results beat failing the whole wildcard
            collected.append(value)
        if not collected:
            return None, "wildcard matched no elements"
        return collected, None

    return _walk(current, rest)


class QueryJson(Tool):
    name = "query_json"
    risk = RiskLevel.READ
    category = "data"
    keywords = (
        "query json",
        "extract from json",
        "read json field",
        "json path",
        "get value from json",
        "parse json field",
    )
    description = (
        "Query a JSON document with a dotted path such as "
        "'results.0.title' or 'items[*].id'. Accepts inline text or a file."
    )
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Inline JSON."},
            "path_file": {"type": "string", "description": "Path to a .json file."},
            "path": {"type": "string", "description": "Dotted path to extract."},
        },
        "required": ["path"],
    }
    output_schema = {
        "type": "object",
        "properties": {"value": {"type": "object"}, "type": {"type": "string"}},
    }

    def run(
        self,
        text: str | None = None,
        path_file: str | None = None,
        path: str = "",
        **_: Any,
    ) -> dict[str, Any]:
        content, origin = _read_source(text, path_file)
        if content.startswith("error:"):
            return {"error": content[6:].strip()}
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            return {"error": f"invalid JSON: {exc}"}
        value, failure = _resolve_path(data, path)
        if failure:
            return {"error": failure, "origin": origin, "path": path}
        return {
            "origin": origin,
            "path": path,
            "type": type(value).__name__,
            "value": value if isinstance(value, (dict, list, int, float, bool, type(None)))
            else _clip(value),
        }


class ParseJson(Tool):
    name = "parse_json"
    risk = RiskLevel.READ
    category = "data"
    keywords = (
        "parse json",
        "validate json",
        "json structure",
        "json keys",
        "inspect json",
        "json schema",
    )
    description = (
        "Validate JSON and describe its structure: top-level keys with types, "
        "plus array lengths. `depth` controls how deep the outline goes."
    )
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "path_file": {"type": "string"},
            "depth": {"type": "integer", "description": "Outline depth (default 2)."},
        },
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {"valid": {"type": "boolean"}, "outline": {"type": "object"}},
    }

    def run(
        self,
        text: str | None = None,
        path_file: str | None = None,
        depth: int = 2,
        **_: Any,
    ) -> dict[str, Any]:
        content, origin = _read_source(text, path_file)
        if content.startswith("error:"):
            return {"error": content[6:].strip()}
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            return {"error": f"invalid JSON: {exc}", "valid": False}
        return {"valid": True, "origin": origin, "outline": _outline(data, max(1, int(depth)))}


def _outline(value: Any, depth: int) -> Any:
    if depth <= 0:
        return type(value).__name__
    if isinstance(value, dict):
        return {k: _outline(v, depth - 1) for k, v in list(value.items())[:50]}
    if isinstance(value, list):
        head = [_outline(v, depth - 1) for v in value[:3]]
        return {"__list_len__": len(value), "__items__": head if head else []}
    if isinstance(value, str):
        return f"str({len(value)})"
    return type(value).__name__


class ParseXml(Tool):
    name = "parse_xml"
    risk = RiskLevel.READ
    category = "data"
    keywords = (
        "parse xml",
        "read xml",
        "xml to elements",
        "extract xml",
        "parse rss",
        "parse sitemap",
    )
    description = (
        "Parse XML and return elements as JSON. Use `xpath`-like `tag` to "
        "extract matching elements (namespace prefix stripped), e.g. 'item' "
        "for an RSS feed."
    )
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "path_file": {"type": "string"},
            "tag": {"type": "string", "description": "Only return elements with this tag."},
            "limit": {"type": "integer", "description": "Max elements (default 100)."},
        },
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {"count": {"type": "integer"}, "elements": {"type": "array"}},
    }

    def run(
        self,
        text: str | None = None,
        path_file: str | None = None,
        tag: str = "",
        limit: int = 100,
        **_: Any,
    ) -> dict[str, Any]:
        content, origin = _read_source(text, path_file)
        if content.startswith("error:"):
            return {"error": content[6:].strip()}
        try:
            root = ET.fromstring(content)
        except ET.ParseError as exc:
            return {"error": f"invalid XML: {exc}"}

        cap = max(1, min(int(limit), 2000))
        found: list[Any] = []
        wanted = tag.strip().lower()
        for element in root.iter():
            local = element.tag.rsplit("}", 1)[-1].lower()
            if wanted and local != wanted:
                continue
            entry: dict[str, Any] = {}
            if element.attrib:
                entry["attributes"] = {k.rsplit("}", 1)[-1]: _clip(v)
                                       for k, v in element.attrib.items()}
            text_value = (element.text or "").strip()
            if text_value:
                entry["text"] = _clip(text_value)
            children = list(element)
            if children:
                entry["children"] = [
                    {"tag": c.tag.rsplit("}", 1)[-1], "text": _clip((c.text or "").strip())}
                    for c in children[:20]
                ]
            found.append(entry if entry else {"tag": local})
            if len(found) >= cap:
                break
        return {"origin": origin, "count": len(found), "elements": found}


class ParseHtml(Tool):
    name = "parse_html"
    risk = RiskLevel.READ
    category = "data"
    keywords = (
        "parse html",
        "extract page text",
        "html to text",
        "read html",
        "page metadata",
        "extract meta tags",
        "html title",
    )
    description = (
        "Extract the readable text, title, meta tags and links from HTML, "
        "dropping script/style content."
    )
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "path_file": {"type": "string"},
            "include_links": {"type": "boolean", "description": "Default true."},
            "limit": {"type": "integer", "description": "Max characters of text."},
        },
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "text": {"type": "string"},
            "meta": {"type": "object"},
            "links": {"type": "array"},
        },
    }

    def run(
        self,
        text: str | None = None,
        path_file: str | None = None,
        include_links: bool = True,
        limit: int = 20000,
        **_: Any,
    ) -> dict[str, Any]:
        content, origin = _read_source(text, path_file)
        if content.startswith("error:"):
            return {"error": content[6:].strip()}
        if not content.strip():
            return {"error": "no HTML supplied", "origin": origin}
        parser = _TextExtractor()
        try:
            parser.feed(content)
            parser.close()
        except Exception as exc:  # noqa: BLE001 - malformed markup is common
            return {"error": f"could not parse HTML: {type(exc).__name__}: {exc}"}

        body = parser.text[: max(1, int(limit))]
        out: dict[str, Any] = {
            "origin": origin,
            "title": parser.title,
            "text": body,
            "text_length": len(parser.text),
            "meta": parser.meta,
        }
        if include_links:
            out["links"] = parser.links[:200]
            out["link_count"] = len(parser.links)
        return out


class ExtractTables(Tool):
    name = "extract_tables"
    risk = RiskLevel.READ
    category = "data"
    keywords = (
        "extract tables",
        "html table",
        "get table from page",
        "scrape table",
        "table data from html",
    )
    description = "Extract every HTML table as headers plus row arrays."
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "path_file": {"type": "string"},
            "index": {"type": "integer", "description": "Only return this table index."},
            "limit": {"type": "integer", "description": "Max rows per table."},
        },
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {"count": {"type": "integer"}, "tables": {"type": "array"}},
    }

    def run(
        self,
        text: str | None = None,
        path_file: str | None = None,
        index: int | None = None,
        limit: int = _MAX_ROWS,
        **_: Any,
    ) -> dict[str, Any]:
        content, origin = _read_source(text, path_file)
        if content.startswith("error:"):
            return {"error": content[6:].strip()}
        parser = _TextExtractor()
        try:
            parser.feed(content)
            parser.close()
        except Exception as exc:  # noqa: BLE001
            return {"error": f"could not parse HTML: {type(exc).__name__}: {exc}"}

        cap = max(1, min(int(limit), _MAX_ROWS))
        tables = [
            {"rows": t["rows"][:cap], "row_count": len(t["rows"]), "truncated": len(t["rows"]) > cap}
            for t in parser.tables
        ]
        if index is not None:
            position = int(index)
            if position < 0 or position >= len(tables):
                return {"error": f"table index {position} out of range (have {len(tables)})"}
            tables = [tables[position]]
        return {"origin": origin, "count": len(tables), "tables": tables}


class FetchWebpage(Tool):
    name = "fetch_webpage"
    risk = RiskLevel.READ
    category = "browser"
    keywords = (
        "fetch webpage",
        "get page source",
        "download page html",
        "fetch url content",
        "retrieve web page",
        "get raw html",
    )
    description = (
        "Fetch a URL over HTTP and return status, content type and body text. "
        "Stateless, unlike the session-based browser tools. Use "
        "`parse_html` on the returned `html` to pull out structured content."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Absolute http/https URL."},
            "include_body": {
                "type": "boolean",
                "description": "Include the response body (default true).",
            },
            "max_chars": {"type": "integer", "description": "Body cap (default 50000)."},
        },
        "required": ["url"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "status": {"type": "integer"},
            "content_type": {"type": "string"},
            "html": {"type": "string"},
            "final_url": {"type": "string"},
        },
    }

    def run(
        self,
        url: str = "",
        include_body: bool = True,
        max_chars: int = 50000,
        **_: Any,
    ) -> dict[str, Any]:
        if not url.strip():
            return {"error": "url is required"}
        response, failure = _fetch(url)
        if failure:
            return failure
        body = response.content[:_MAX_FETCH_BYTES]
        result: dict[str, Any] = {
            "status": response.status_code,
            "content_type": response.headers.get("content-type", ""),
            "final_url": str(response.url),
            "bytes": len(body),
        }
        if include_body:
            text = body.decode(response.encoding or "utf-8", errors="replace")
            result["html" if "html" in result["content_type"] else "body"] = text[: int(max_chars)]
        return result


class DownloadFile(Tool):
    name = "download_file"
    risk = RiskLevel.MEDIUM
    mutates = True
    category = "browser"
    keywords = (
        "download file",
        "download url",
        "save from web",
        "download to disk",
        "fetch and save",
    )
    description = (
        "Download a URL to a local file. Writes to disk, overwriting the "
        "target if it already exists."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Absolute http/https URL."},
            "destination": {"type": "string", "description": "Target file path."},
            "overwrite": {"type": "boolean", "description": "Default true."},
        },
        "required": ["url"],
    }
    output_schema = {
        "type": "object",
        "properties": {"path": {"type": "string"}, "bytes": {"type": "integer"}},
    }

    def run(
        self,
        url: str = "",
        destination: str = "",
        overwrite: bool = True,
        **_: Any,
    ) -> dict[str, Any]:
        if not url.strip():
            return {"error": "url is required"}
        response, failure = _fetch(url)
        if failure:
            return failure
        if response.status_code >= 400:
            return {"error": f"HTTP {response.status_code} for {url}"}

        parsed = urlparse(str(response.url))
        default_name = os.path.basename(parsed.path) or "download.bin"
        target = (
            Path(destination).expanduser()
            if destination
            else Path.cwd() / default_name
        )
        if target.exists() and not overwrite:
            return {"error": f"{target} already exists and overwrite is false"}
        if target.is_dir():
            target = target / default_name

        body = response.content
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
        except OSError as exc:
            return {"error": f"could not write {target}: {exc}"}
        return {
            "path": str(target),
            "bytes": len(body),
            "content_type": response.headers.get("content-type", ""),
            "source_url": str(response.url),
        }


__all__ = [
    "DownloadFile",
    "ExtractTables",
    "FetchWebpage",
    "ParseCsv",
    "ParseHtml",
    "ParseJson",
    "ParseXml",
    "QueryJson",
    "SummarizeCsv",
]
