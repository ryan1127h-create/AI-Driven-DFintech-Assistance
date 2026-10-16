"""
Fetches the official MSc DFT web pages and turns them into the text the
knowledge base keeps: Markdown per page (headings, paragraphs with link
targets in brackets, lists, tables), and the FAQ page's questions and
answers one by one.

Only the WordPress entry content is read (div.entry-content) — menus,
footers and scripts are left out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx
from lxml import html

USER_AGENT = "Mozilla/5.0 (compatible; MSc-DFT-assistant knowledge refresh)"

_SKIP_TAGS = {"script", "style", "noscript", "svg", "button", "form", "iframe", "img", "figure", "i"}
_BLOCK_TAGS = {"p", "div", "section", "article", "li", "ul", "ol", "table", "blockquote",
               "h1", "h2", "h3", "h4", "h5", "h6", "tr", "header", "footer"}


@dataclass(frozen=True)
class FaqItem:
    section: str
    question: str
    answer: str


def fetch(url: str) -> html.HtmlElement:
    response = httpx.get(url, headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=30)
    response.raise_for_status()
    # Parse the bytes: the page is UTF-8, and decoding it as Latin-1 garbles
    # curly quotes.
    return html.fromstring(response.content)


def _with_class(root: html.HtmlElement, name: str) -> list[html.HtmlElement]:
    return root.xpath(f".//*[contains(concat(' ', normalize-space(@class), ' '), ' {name} ')]")


def entry_content(page: html.HtmlElement) -> html.HtmlElement:
    """The page body: its main column(s) when the page has a sidebar (the
    side-box holds the programme's navigation menu), else the whole entry
    content."""
    found = _with_class(page, "entry-content")
    if not found:
        raise ValueError("no entry-content on the page")
    content = found[0]
    mains = _with_class(content, "main-box")
    if not mains:
        return content
    body = html.Element("div")
    for main in mains:
        body.append(main)
    return body


def _clean(text: str) -> str:
    text = text.replace("\xa0", " ").replace("​", "")
    return re.sub(r"[ \t]+", " ", text).strip()


def _inline(el: html.HtmlElement) -> str:
    """Text of an element with links as 'text (url)'."""
    if el.tag in _SKIP_TAGS:
        return ""
    parts = [el.text or ""]
    for child in el:
        if child.tag == "br":
            parts.append("\n")
        elif child.tag == "a":
            label = _clean(_inline(child))
            href = (child.get("href") or "").strip()
            if href.startswith(("http://", "https://")) and href.rstrip("/") not in label:
                parts.append(f"{label} ({href})" if label else href)
            else:
                parts.append(label)
        else:
            parts.append(_inline(child))
        parts.append(child.tail or "")
    return "".join(parts)


def _table(el: html.HtmlElement) -> str:
    rows = []
    for tr in el.iter("tr"):
        cells = [_clean(_inline(td)).replace("\n", " ").replace("|", "/") for td in tr if td.tag in ("td", "th")]
        if any(cells):
            rows.append(cells)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join(["---"] * width) + " |"]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(lines)


def _has_block_child(el: html.HtmlElement) -> bool:
    return any(child.tag in _BLOCK_TAGS for child in el)


def _blocks(el: html.HtmlElement, out: list[str]) -> None:
    for child in el:
        tag = child.tag
        if not isinstance(tag, str) or tag in _SKIP_TAGS:
            continue
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = _clean(_inline(child))
            if text:
                out.append("#" * int(tag[1]) + " " + text)
        elif tag == "table":
            table = _table(child)
            if table:
                out.append(table)
        elif tag in ("ul", "ol"):
            links = [a.get("href") or "" for a in child.iter("a")]
            if links and all(h.startswith("#") for h in links):
                continue  # an in-page contents list
            items = [_clean(_inline(li)) for li in child if li.tag == "li"]
            items = [i for i in items if i]
            if items:
                out.append("\n".join(f"- {i}" for i in items))
        elif tag == "p" or not _has_block_child(child):
            text = _clean(_inline(child))
            if text:
                out.append(text)
        else:
            _blocks(child, out)


def to_markdown(content: html.HtmlElement) -> str:
    out: list[str] = []
    _blocks(content, out)
    headings = {re.sub(r"^#+ ", "", b) for b in out if b.startswith("#")}
    seen, kept = set(), []
    for block in out:
        # Repeated blocks (Elementor renders some widgets twice, for mobile
        # and desktop) are kept once; an in-page contents list (items that
        # are just the page's own headings) is dropped.
        items = [line[2:] for line in block.split("\n")] if block.startswith("- ") else []
        if block in seen or (items and set(items) <= headings):
            continue
        seen.add(block)
        kept.append(block)
    return "\n\n".join(kept)


def faq_items(content: html.HtmlElement) -> list[FaqItem]:
    """The FAQ page's accordions, each under the heading above it."""
    items: list[FaqItem] = []
    section = ""
    for el in content.iter():
        if not isinstance(el.tag, str):
            continue
        classes = (el.get("class") or "").split()
        if "elementor-heading-title" in classes:
            section = _clean(el.text_content())
        elif "eael-accordion-list" in classes:
            title = el.xpath(".//*[contains(@class,'eael-accordion-tab-title')]")
            body = el.xpath(".//*[contains(@class,'eael-accordion-content')]")
            if not title or not body:
                continue
            out: list[str] = []
            _blocks(body[0], out)
            answer = "\n".join(out) or _clean(_inline(body[0]))
            items.append(FaqItem(section, _clean(title[0].text_content()), answer))
    return items
