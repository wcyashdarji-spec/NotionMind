from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Set, Tuple

import httpx

from src.config import NOTION_TOKEN, logger

_API_BASE = "https://api.notion.com/v1"
_API_VERSION = "2022-06-28"
_MAX_RETRIES = 5


class NotionService:
    """
    Service class for the Notion REST API.

    Attributes:
        token: Bearer token used for authentication.
        headers: HTTP headers sent with every request.
    """

    def __init__(self, token: str = NOTION_TOKEN) -> None:
        """
        Initialise the service and create a persistent HTTP client.

        Args:
            token: Notion integration bearer token.
        """
        self.token = token
        self.headers: Dict[str, str] = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": _API_VERSION,
            "Content-Type": "application/json",
        }
        self._http = httpx.AsyncClient(headers=self.headers, timeout=30.0)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.aclose()

    async def __aenter__(self) -> NotionService:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()


    async def _request(self, method: str, url: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Execute an HTTP request with exponential back-off on rate-limit errors.

        Args:
            method: HTTP verb (``"GET"``, ``"POST"``, …).
            url: Fully qualified request URL.
            **kwargs: Extra arguments forwarded to :meth:`httpx.AsyncClient.request`.

        Returns:
            Parsed JSON response dictionary.

        Raises:
            httpx.HTTPStatusError: On non-429 HTTP errors after exhausting retries.
            httpx.RequestError: On network connectivity failures.
        """
        backoff = 1.0
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = await self._http.request(method, url, **kwargs)

                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", backoff))
                    logger.warning(
                        f"Rate-limited (429). Retrying in {retry_after}s "
                        f"(attempt {attempt}/{_MAX_RETRIES})."
                    )
                    await asyncio.sleep(retry_after)
                    backoff *= 2
                    continue

                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue
                if exc.response.status_code not in (400, 404):
                    logger.error(
                        f"Notion API HTTP error {exc.response.status_code}: {exc.response.text}"
                    )
                raise

            except httpx.RequestError as exc:
                logger.error(f"Notion API network error: {exc}")
                if attempt == _MAX_RETRIES:
                    raise
                await asyncio.sleep(backoff)
                backoff *= 2

        raise httpx.RequestError(f"Notion API: max retries ({_MAX_RETRIES}) exceeded.")


    async def get_page(self, page_id: str) -> Dict[str, Any]:
        """
        Retrieve metadata for a single Notion page.

        Args:
            page_id: UUID of the target page.

        Returns:
            Page object dictionary as returned by the Notion API.

        Raises:
            httpx.HTTPStatusError: On API errors.
        """
        try:
            return await self._request("GET", f"{_API_BASE}/pages/{page_id}")
        except Exception as exc:
            logger.error(f"get_page({page_id}) failed: {exc}")
            raise


    async def get_database(self, database_id: str) -> Dict[str, Any]:
        """
        Retrieve metadata for a Notion database.

        Args:
            database_id: UUID of the target database.

        Returns:
            Database object dictionary as returned by the Notion API.

        Raises:
            httpx.HTTPStatusError: On API errors.
        """
        try:
            return await self._request("GET", f"{_API_BASE}/databases/{database_id}")
        except Exception as exc:
            logger.error(f"get_database({database_id}) failed: {exc}")
            raise


    async def query_database(self, database_id: str) -> List[Dict[str, Any]]:
        """
        Return all page entries belonging to a database, handling pagination.

        Args:
            database_id: UUID of the target database.

        Returns:
            Flat list of page-object dictionaries.

        Raises:
            httpx.HTTPStatusError: On API errors.
        """
        url = f"{_API_BASE}/databases/{database_id}/query"
        results: List[Dict[str, Any]] = []
        start_cursor: str | None = None

        try:
            while True:
                payload: Dict[str, Any] = {"page_size": 100}
                if start_cursor:
                    payload["start_cursor"] = start_cursor

                data = await self._request("POST", url, json=payload)
                results.extend(data.get("results", []))

                if not data.get("has_more"):
                    break
                start_cursor = data.get("next_cursor")

        except Exception as exc:
            logger.error(f"query_database({database_id}) failed: {exc}")
            raise

        return results


    async def get_block_children(self, block_id: str) -> List[Dict[str, Any]]:
        """
        Return all children of a block, handling pagination.

        Args:
            block_id: UUID of the parent block (or page).

        Returns:
            Flat list of block-object dictionaries.

        Raises:
            httpx.HTTPStatusError: On API errors.
        """
        url = f"{_API_BASE}/blocks/{block_id}/children"
        results: List[Dict[str, Any]] = []
        start_cursor: str | None = None

        try:
            while True:
                params: Dict[str, Any] = {"page_size": 100}
                if start_cursor:
                    params["start_cursor"] = start_cursor

                data = await self._request("GET", url, params=params)
                results.extend(data.get("results", []))

                if not data.get("has_more"):
                    break
                start_cursor = data.get("next_cursor")

        except Exception as exc:
            logger.error(f"get_block_children({block_id}) failed: {exc}")
            raise

        return results


    async def search_workspace(self, query: str = "") -> List[Dict[str, Any]]:
        """
        Search the workspace for pages the integration can access.

        Args:
            query: Optional full-text search string.

        Returns:
            Flat list of page/database result objects.

        Raises:
            httpx.HTTPStatusError: On API errors.
        """
        url = f"{_API_BASE}/search"
        results: List[Dict[str, Any]] = []
        start_cursor: str | None = None

        try:
            while True:
                payload: Dict[str, Any] = {
                    "page_size": 100,
                    "filter": {"property": "object", "value": "page"},
                }
                if query:
                    payload["query"] = query
                if start_cursor:
                    payload["start_cursor"] = start_cursor

                data = await self._request("POST", url, json=payload)
                results.extend(data.get("results", []))

                if not data.get("has_more"):
                    break
                start_cursor = data.get("next_cursor")

        except Exception as exc:
            logger.error(f"search_workspace failed: {exc}")
            raise

        return results


    def extract_rich_text(self, rich_text: List[Dict[str, Any]]) -> str:
        """
        Concatenate the ``plain_text`` values from a Notion rich-text array.

        Args:
            rich_text: List of rich-text run objects.

        Returns:
            Single plain-text string.
        """
        try:
            return "".join(run.get("plain_text", "") for run in (rich_text or []))
        except Exception as exc:
            logger.error(f"extract_rich_text failed: {exc}")
            return ""


    def get_page_title(self, page_data: Dict[str, Any]) -> str:
        """
        Extract the human-readable title from page metadata.

        Args:
            page_data: Page object as returned by :meth:`get_page`.

        Returns:
            Title string, or ``"Untitled Page"`` when none is found.
        """
        try:
            for prop in page_data.get("properties", {}).values():
                if prop.get("type") == "title":
                    return self.extract_rich_text(prop.get("title", []))
            return "Untitled Page"
        
        except Exception as exc:
            logger.error(f"get_page_title failed: {exc}")
            return "Untitled Page"
            
    async def download_image(self, url: str, block_id: str) -> str | None:
        """
        Download and store an image from a remote source.

        This method retrieves an image from the provided URL, detects its
        format, saves it to the local ``static/images`` directory using the
        associated block identifier as the filename, and returns the
        corresponding static file path for later access.

        Args:
            url: URL of the image to download.
            block_id: Unique identifier used to generate the local filename.

        Returns:
            str | None:
                The local static image path if the download succeeds,
                otherwise ``None``.

        Raises:
            None:
                Any exceptions are logged internally, and the method
                returns ``None`` if the image cannot be downloaded or
                saved.
        """
        try:
            import os
            import io
            from PIL import Image

            os.makedirs("static/images", exist_ok=True)

            logger.info(f"Downloading image for block {block_id} ...")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                image_data = response.content

            img = Image.open(io.BytesIO(image_data))
            img_format = img.format.lower() if img.format else "png"
            if img_format == "jpeg":
                img_format = "jpg"

            filename = f"{block_id}.{img_format}"
            local_path = os.path.join("static/images", filename)
            
            if img.mode in ("RGBA", "LA") and img_format == "jpg":
                img = img.convert("RGB")
                
            img.save(local_path)
            logger.info(f"Saved image to {local_path}")
            return f"/static/images/{filename}"
        except Exception as exc:
            logger.error(f"Failed to download and save image {block_id}: {exc}")
            return None

    async def _block_to_markdown(
        self,
        block: Dict[str, Any],
        indent: int = 0,
    ) -> Tuple[str, List[str], List[str], List[Dict[str, Any]]]:
        """
        Convert a single Notion block to Markdown and surface any nested page/
        database IDs and extracted images for recursive processing.

        Args:
            block: Notion block object dictionary.
            indent: Current indentation level (number of 4-space groups).

        Returns:
            A four-tuple of:
            - ``markdown``: Markdown string for this block.
            - ``child_page_ids``: IDs of child-page blocks discovered.
            - ``child_database_ids``: IDs of child-database blocks discovered.
            - ``images``: Extracted image metadata dictionaries.
        """
        block_type: str = block.get("type", "")
        block_id: str = block.get("id", "")
        has_children: bool = block.get("has_children", False)
        pad = "    " * indent

        markdown = ""
        child_pages: List[str] = []
        child_databases: List[str] = []
        images: List[Dict[str, Any]] = []

        try:
            rt = lambda key: self.extract_rich_text(block.get(key, {}).get("rich_text", []))  # noqa: E731

            _block_map = {
                "paragraph": lambda: f"{pad}{rt('paragraph')}\n\n",
                "heading_1": lambda: f"{pad}# {rt('heading_1')}\n\n",
                "heading_2": lambda: f"{pad}## {rt('heading_2')}\n\n",
                "heading_3": lambda: f"{pad}### {rt('heading_3')}\n\n",
                "bulleted_list_item": lambda: f"{pad}- {rt('bulleted_list_item')}\n",
                "numbered_list_item": lambda: f"{pad}1. {rt('numbered_list_item')}\n",
                "to_do": lambda: (
                    f"{pad}- {'[x]' if block['to_do'].get('checked') else '[ ]'} {rt('to_do')}\n"
                ),
                "quote": lambda: f"{pad}> {rt('quote')}\n\n",
                "callout": lambda: f"{pad}> [!NOTE]\n{pad}> {rt('callout')}\n\n",
                "code": lambda: (
                    f"{pad}```{block['code'].get('language', '')}\n"
                    f"{rt('code')}\n{pad}```\n\n"
                ),
                "divider": lambda: f"{pad}---\n\n",
                "toggle": lambda: f"{pad}- {rt('toggle')}\n",
            }

            if block_type in _block_map:
                markdown = _block_map[block_type]()

            elif block_type == "image":
                image_info = block.get("image", {})
                img_type = image_info.get("type", "")
                img_url = ""
                if img_type == "external":
                    img_url = image_info.get("external", {}).get("url", "")
                elif img_type == "file":
                    img_url = image_info.get("file", {}).get("url", "")

                if img_url:
                    caption = self.extract_rich_text(image_info.get("caption", []))
                    local_path = await self.download_image(img_url, block_id)
                    if local_path:
                        markdown = f"{pad}![{caption}]({local_path})\n\n"
                        images.append({
                            "block_id": block_id,
                            "local_path": local_path,
                            "caption": caption,
                            "original_url": img_url,
                        })
                    else:
                        markdown = f"{pad}![{caption}]({img_url})\n\n"

            elif block_type == "child_page":
                title = block["child_page"].get("title", "Untitled Sub-page")
                child_pages.append(block_id)
                markdown = f"{pad}*[Sub-page: {title}]*\n\n"

            elif block_type == "child_database":
                title = block["child_database"].get("title", "Untitled Sub-database")
                child_databases.append(block_id)
                markdown = f"{pad}*[Sub-database: {title}]*\n\n"

            if has_children and block_type not in ("child_page", "child_database"):
                for child in await self.get_block_children(block_id):
                    child_md, sub_pages, sub_dbs, sub_images = await self._block_to_markdown(child, indent + 1)
                    markdown += child_md
                    child_pages.extend(sub_pages)
                    child_databases.extend(sub_dbs)
                    images.extend(sub_images)

        except Exception as exc:
            logger.error(f"_block_to_markdown({block_id}, type={block_type}) failed: {exc}")

        return markdown, child_pages, child_databases, images


    async def fetch_page_as_document(
        self, page_id: str
    ) -> Tuple[str, str, List[str], List[str], str, List[Dict[str, Any]]]:
        """
        Fetch a page and render its content as Markdown.

        Args:
            page_id: UUID of the target Notion page.

        Returns:
            A six-tuple of:
            - ``title``: Page title string.
            - ``content``: Full Markdown string.
            - ``child_page_ids``: IDs of embedded child pages.
            - ``child_database_ids``: IDs of embedded child databases.
            - ``url``: Canonical Notion page URL.
            - ``images``: Extracted image metadata list.

        Raises:
            Exception: Propagates errors from underlying API calls.
        """
        try:
            logger.info(f"Fetching page {page_id} …")
            page_data = await self.get_page(page_id)
            title = self.get_page_title(page_data)
            url = page_data.get("url") or f"https://notion.so/{page_id.replace('-', '')}"
            logger.info(f"  → '{title}'")

            blocks = await self.get_block_children(page_id)
            lines = [f"# {title}\n\n"]
            all_child_pages: List[str] = []
            all_child_dbs: List[str] = []
            all_images: List[Dict[str, Any]] = []

            for block in blocks:
                md, cp, cd, imgs = await self._block_to_markdown(block)
                lines.append(md)
                all_child_pages.extend(cp)
                all_child_dbs.extend(cd)
                all_images.extend(imgs)

            return title, "".join(lines), all_child_pages, all_child_dbs, url, all_images

        except Exception as exc:
            logger.error(f"fetch_page_as_document({page_id}) failed: {exc}")
            raise


    async def crawl(
        self,
        root_id: str,
        visited: Set[str] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Recursively crawl pages and databases from a root node.

        The method auto-detects whether *root_id* refers to a database or a
        page, handles databases by enumerating their entries, and recurses into
        child pages and databases discovered in each page's content.

        Args:
            root_id: UUID of the starting page or database.
            visited: Set of already-processed IDs (used to prevent cycles).

        Returns:
            List of document dicts with keys ``page_id``, ``title``,
            ``content``, ``url``, and ``images``.
        """
        if visited is None:
            visited = set()

        if root_id in visited:
            return []

        visited.add(root_id)
        documents: List[Dict[str, Any]] = []

        is_database = False
        try:
            await self.get_page(root_id)
            logger.info(f"{root_id} detected as PAGE")

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                try:
                    db_meta = await self.get_database(root_id)
                    is_database = True

                    db_title = self.extract_rich_text(db_meta.get("title", []))
                    logger.info(f"{root_id} detected as DATABASE '{db_title}'")

                except httpx.HTTPStatusError:
                    logger.warning(f"{root_id} is neither a page nor a database.")
                    return []
            else:
                raise

        if is_database:
            try:
                entries = await self.query_database(root_id)
                logger.info(f"Database {root_id}: found {len(entries)} entries.")
                for entry in entries:
                    documents.extend(await self.crawl(entry["id"], visited))
            except Exception as exc:
                logger.error(f"crawl – database traversal failed for {root_id}: {exc}")

        else:
            try:
                title, content, child_pages, child_dbs, url, images = await self.fetch_page_as_document(root_id)
                documents.append(
                    {
                        "page_id": root_id,
                        "title": title,
                        "content": content,
                        "url": url,
                        "images": images
                    }
                )
                for pid in child_pages:
                    documents.extend(await self.crawl(pid, visited))
                for did in child_dbs:
                    documents.extend(await self.crawl(did, visited))

            except Exception as exc:
                logger.error(f"crawl – page traversal failed for {root_id}: {exc}")

        return documents

    async def fetch_workspace(self) -> List[Dict[str, Any]]:
        """
        Discover and crawl all root-level pages shared with the integration.

        A page is considered *root-level* if its parent is the workspace, or
        if its parent page/database was not itself returned by the Search API
        (i.e. it was shared directly rather than being a descendant of another
        shared page).

        Returns:
            List of document dicts (same schema as :meth:`crawl`).
        """
        try:
            logger.info("Scanning workspace for shared root pages …")
            search_results = await self.search_workspace()
            found_ids = {item["id"] for item in search_results}

            root_ids: List[str] = []
            for item in search_results:
                parent = item.get("parent", {})
                parent_type = parent.get("type")
                if parent_type == "workspace":
                    root_ids.append(item["id"])
                elif parent_type == "page_id" and parent.get("page_id") not in found_ids:
                    root_ids.append(item["id"])
                elif parent_type == "database_id" and parent.get("database_id") not in found_ids:
                    root_ids.append(item["id"])

            logger.info(f"Identified {len(root_ids)} root entities.")

            visited: Set[str] = set()
            documents: List[Dict[str, Any]] = []
            for entity_id in root_ids:
                documents.extend(await self.crawl(entity_id, visited))

            return documents

        except Exception as exc:
            logger.error(f"fetch_workspace failed: {exc}")
            raise
