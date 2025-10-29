"""Outils de pagination pour la liste principale."""
from __future__ import annotations

from math import ceil
from typing import Dict, Generic, List, Optional, Sequence, Tuple, TypeVar, Union

from pydantic import BaseModel
from sqlalchemy.orm import Query

T = TypeVar("T")


class PageParams(BaseModel):
    page: int = 1
    per_page: int = 50

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page

    @property
    def limit(self) -> int:
        return self.per_page


class PageResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    per_page: int
    total_pages: int
    has_next: bool
    has_prev: bool


def paginate(query: Query, params: PageParams) -> PageResponse:
    total = query.order_by(None).count()
    total_pages = max(ceil(total / params.per_page), 1)
    page = min(max(params.page, 1), total_pages)
    items = query.offset((page - 1) * params.per_page).limit(params.per_page).all()
    return PageResponse[
        List[T]
    ](  # type: ignore[call-arg]
        items=items,
        total=total,
        page=page,
        per_page=params.per_page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )


def _page_sequence(current: int, total: int, radius: int = 2) -> List[Optional[int]]:
    pages: List[Optional[int]] = []
    for page in range(1, total + 1):
        if page == 1 or page == total or abs(page - current) <= radius:
            pages.append(page)
        elif pages and pages[-1] is not None:
            pages.append(None)
    return pages


ParamValue = Union[str, List[str]]


def build_pagination_html(
    current: int,
    total_pages: int,
    base_url: str,
    params: Optional[Dict[str, ParamValue]] = None,
) -> str:
    if total_pages <= 1:
        return ""

    params = params or {}

    def build_link(page: int) -> str:
        pairs: List[str] = []
        for key, value in params.items():
            if isinstance(value, list):
                for item in value:
                    if item != "":
                        pairs.append(f"{key}={item}")
            else:
                if value != "":
                    pairs.append(f"{key}={value}")
        pairs.append(f"page={page}")
        query = "&".join(pairs)
        sep = "?" if "?" not in base_url else "&"
        return f"{base_url}{sep}{query}" if query else base_url

    buttons: List[str] = []
    prev_class = "btn-pagination disabled" if current <= 1 else "btn-pagination"
    prev_href = build_link(max(1, current - 1))
    buttons.append(
        f'<a class="{prev_class}" href="{prev_href}" aria-label="Page précédente">«</a>'
    )

    for page in _page_sequence(current, total_pages):
        if page is None:
            buttons.append('<span class="btn-pagination disabled">…</span>')
            continue
        css = "btn-pagination"
        if page == current:
            css += " active"
        buttons.append(f'<a class="{css}" href="{build_link(page)}">{page}</a>')

    next_class = "btn-pagination disabled" if current >= total_pages else "btn-pagination"
    next_href = build_link(min(total_pages, current + 1))
    buttons.append(
        f'<a class="{next_class}" href="{next_href}" aria-label="Page suivante">»</a>'
    )

    return '<nav class="pagination">' + "".join(buttons) + "</nav>"


__all__ = ["PageParams", "PageResponse", "paginate", "build_pagination_html"]
