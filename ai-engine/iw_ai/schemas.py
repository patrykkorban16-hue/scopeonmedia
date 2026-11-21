"""Kontrakt API silnika AI (backend ⇄ ai-engine). Wersjonowany prefiksem /v1."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ------------------------------------------------------------------ preprocessing
class RenderBlock(BaseModel):
    """Blok tekstu wyrenderowany przez Playwright (style obliczone przez przeglądarkę)."""
    text: str
    tag: str = "div"
    font_px: float | None = None
    color: str | None = None
    bg: str | None = None
    bold: bool = False
    hidden: bool = False
    hidden_reason: str | None = None       # display_none | details_closed | aria_hidden | zero_size | transparent
    top: float = 0.0
    page_h: float = 1.0
    clipped: bool = False                  # tekst ucięty (overflow / ellipsis)
    occluded: bool = False                 # przesłonięty innym elementem
    footer: bool = False
    legal: bool = False
    footnote: bool = False


class RenderViewport(BaseModel):
    width: int
    blocks: list[RenderBlock] = Field(default_factory=list)
    horizontal_scroll: bool = False


class RenderReport(BaseModel):
    viewports: dict[str, RenderViewport] = Field(default_factory=dict)   # desktop | tablet | phone
    viewport_meta: bool = True


class PreprocessRequest(BaseModel):
    url: str
    source_type: str = "web"
    html: str | None = None
    text: str | None = None
    render: RenderReport | None = None


class Block(BaseModel):
    i: int
    text: str
    tag: str = "p"
    font_px: float = 16.0
    color: str = "#222222"
    bg: str = "#ffffff"
    contrast: float = 21.0
    bold: bool = False
    heading: bool = False
    hidden: bool = False
    hidden_reason: str | None = None
    footer: bool = False
    legal: bool = False
    footnote: bool = False
    clipped: bool = False
    occluded: bool = False
    pos: float = 0.0                          # 0 = góra strony, 1 = dół
    language: str = "und"
    viewports: dict[str, dict] = Field(default_factory=dict)   # tablet/phone: {font_px, hidden, clipped}


class PreprocessResponse(BaseModel):
    text: str
    normalized: str
    tokens: list[str]
    token_count: int
    content_hash: str
    simhash: str
    language: str
    embedding: list[float]
    embedding_model: str
    blocks: list[Block]
    style_source: Literal["render", "static_css", "text"]
    responsive_checked: bool = False
    viewport_meta: bool = True


# ------------------------------------------------------------------ analiza
class DocumentMeta(BaseModel):
    id: int
    url: str
    domain: str
    source_type: str = "web"
    title: str | None = None
    author: str | None = None
    author_url: str | None = None
    site_name: str | None = None
    published_at: str | None = None
    links: list[str] = Field(default_factory=list)
    metrics: dict = Field(default_factory=dict)


class AnalyzeRequest(BaseModel):
    document: DocumentMeta
    pre: PreprocessResponse
    registry_version: str | None = None


class RuleResult(BaseModel):
    id: str
    name: str
    status: Literal["pass", "fail", "warn", "na"]
    weight: float = 0.0
    evidence: str | None = None
    basis: str = ""


class Reason(BaseModel):
    rule: str
    label: str
    evidence: str | None = None
    weight: float = 0.0


class FirmRef(BaseModel):
    id: int | None = None
    name: str
    category: str | None = None
    country: str | None = None
    register_id: str | None = None
    authorized: bool | None = None
    matched_by: str | None = None


class Advertiser(BaseModel):
    name: str | None = None
    url: str | None = None
    platform: str | None = None
    is_labeled_ad: bool | None = None
    reach: dict = Field(default_factory=dict)


class EntityData(BaseModel):
    name: str | None = None
    nip: list[str] = Field(default_factory=list)
    krs: list[str] = Field(default_factory=list)
    regon: list[str] = Field(default_factory=list)
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    addresses: list[str] = Field(default_factory=list)


class UnifiedFinding(BaseModel):
    """Ujednolicony obiekt wyniku – wspólny format dla modułów 1, 2, 3."""
    module: int
    module_name: str
    category: str
    score: float
    rule_score: float
    firm: FirmRef | None = None
    advertiser: Advertiser | None = None
    entity: EntityData | None = None
    excerpt: str
    reasons: list[Reason] = Field(default_factory=list)
    rules: list[RuleResult] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)
    llm_eligible: bool = True


class AnalyzeResponse(BaseModel):
    document_id: int
    findings: list[UnifiedFinding]
    max_score: float
    engine_version: str


class LLMReviewRequest(BaseModel):
    module: int
    text: str
    context: str = ""
    rule_score: float


class LLMReviewResponse(BaseModel):
    available: bool
    probability: float | None = None
    score: float | None = None
    weight: float | None = None
    max_decrease: float | None = None
    injection_suspected: bool = False
    reasons: list[str] = Field(default_factory=list)
    model: str | None = None
    error: str | None = None
