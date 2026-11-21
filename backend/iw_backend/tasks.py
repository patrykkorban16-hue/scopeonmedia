"""Kolejka zadań (Huey – open source; SQLite lokalnie, Redis w Dockerze) + harmonogram typu CronJob.

Worker:  huey_consumer iw_backend.tasks.huey -w 4 -k thread
Priorytety: zbieranie i analiza (10) > ponowne odwiedziny (5) > ocena LLM (1, najwolniejsza).
"""
from __future__ import annotations

import json
import logging

from huey import RedisHuey, SqliteHuey, crontab
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from . import config, registry
from .db import CrawlJob, Document, Finding, init_db, put_setting, session_scope, utcnow
from .events import publish
from .pipeline import analyze_document, ingest, llm_review
from .scraper.collectors import collect_social, crawl_web, fetch_page, search_web
from .scraper.http import Fetcher

log = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
config.require_internal_token()      # worker bez sekretu nie mógłby wysyłać zdarzeń do API
huey = (RedisHuey("investwatch", url=config.REDIS_URL) if config.QUEUE_BACKEND == "redis"
        else SqliteHuey("investwatch", filename=config.QUEUE_SQLITE))
init_db()


def _cron(expr: str) -> crontab:
    m, h, d, mo, dow = expr.split()
    return crontab(minute=m, hour=h, day=d, month=mo, day_of_week=dow)


def load_seeds() -> dict:
    if config.SEEDS_FILE.exists():
        return json.loads(config.SEEDS_FILE.read_text(encoding="utf-8"))
    return {}


# ------------------------------------------------------------------------- śledzenie zadań
def _job_dict(j: CrawlJob) -> dict:
    return {"id": j.id, "kind": j.kind, "target": j.target, "status": j.status, "pages": j.pages,
            "new_documents": j.new_documents, "findings": j.findings, "error": j.error,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "finished_at": j.finished_at.isoformat() if j.finished_at else None}


class Job:
    def __init__(self, kind: str, target: str):
        with session_scope() as s:
            j = CrawlJob(kind=kind, target=target[:1000])
            s.add(j)
            s.flush()
            self.id = j.id
            publish([{"type": "job", "data": _job_dict(j)}])
        self.pages = self.new = self.findings = 0

    def page_done(self, outcome: str, n_findings: int) -> None:
        self.pages += 1
        self.new += outcome in ("new", "updated")
        self.findings += n_findings
        if self.pages % 5 == 0:
            self._save("running")

    def _save(self, status: str, error: str | None = None) -> None:
        with session_scope() as s:
            j = s.get(CrawlJob, self.id)
            j.status, j.pages, j.new_documents, j.findings, j.error = status, self.pages, self.new, self.findings, error
            if status != "running":
                j.finished_at = utcnow()
            publish([{"type": "job", "data": _job_dict(j)}])

    def finish(self, error: str | None = None) -> None:
        self._save("failed" if error else "done", error)


def _process(page: dict, job: Job) -> None:
    try:
        doc_id, outcome = ingest(page, job.id)
        events, llm_ids = analyze_document(doc_id) if doc_id and outcome in ("new", "updated") else ([], [])
    except Exception as exc:
        log.exception("przetwarzanie %s nieudane", page.get("meta", {}).get("url"))
        job.page_done("error", 0)
        raise RuntimeError(str(exc)) from exc
    publish(events)
    for fid in llm_ids:
        task_llm_review(fid)
    job.page_done(outcome, len(events))


# --------------------------------------------------------------------------------- przebiegi
def run_web(seed: dict) -> dict:
    job, err = Job("web", seed["url"]), None
    try:
        for page in crawl_web(seed["url"], max_depth=seed.get("max_depth"), max_pages=seed.get("max_pages"),
                              allow_domains=seed.get("allow_domains")):
            try:
                _process(page, job)
            except RuntimeError:
                pass
    except Exception as exc:
        err = str(exc)[:500]
    job.finish(err)
    return {"job": job.id, "pages": job.pages}


def run_urls(urls: list[str], kind: str = "urls") -> dict:
    job, fetcher = Job(kind, ", ".join(urls)[:900]), Fetcher()
    for url in urls:
        page = fetch_page(url, fetcher)
        if page and page.get("meta"):
            try:
                _process(page, job)
            except RuntimeError:
                pass
    job.finish()
    return {"job": job.id, "pages": job.pages}


def run_social(platform: str, query: str) -> dict:
    job, err = Job(platform, query), None
    try:
        for page in collect_social(platform, query):
            try:
                _process(page, job)
            except RuntimeError:
                pass
    except Exception as exc:
        err = str(exc)[:500]
    job.finish(err)
    return {"job": job.id, "items": job.pages}


def run_search(query: str) -> dict:
    try:
        urls = search_web(query, Fetcher())
    except Exception as exc:
        log.warning("wyszukiwarka niedostępna: %s", exc)
        urls = []
    return run_urls(urls, "search")


def run_recheck() -> dict:
    """Okresowa aktualizacja (Moduł 1): ponowne odwiedziny znanych reklam – last_seen / usunięte / zmienione."""
    with session_scope() as s:
        rows = s.execute(select(Document.id, Document.fetched_url, Document.source_type)
                         .join(Finding, Finding.document_id == Document.id).where(Finding.module == 1).distinct()).all()
    job, fetcher = Job("recheck", f"{len(rows)} reklam"), Fetcher()
    for doc_id, url, source in rows:
        if source != "web":
            continue           # posty z API: aktualizacja przez kolejne wywołanie kolektora
        page = fetch_page(url, fetcher, render=False)
        if page is None:
            continue
        if page.get("status", 200) in (404, 410):
            with session_scope() as s:
                d = s.get(Document, doc_id)
                d.availability, d.http_status = "removed", page["status"]
            job.page_done("removed", 0)
            continue
        if page.get("meta"):
            try:
                _process(page, job)
            except RuntimeError:
                pass
    job.finish()
    return {"job": job.id, "checked": job.pages}


def run_all() -> None:
    seeds = load_seeds()
    for seed in seeds.get("web", []):
        run_web(seed)
    if seeds.get("urls"):
        run_urls(seeds["urls"])
    soc = seeds.get("social", {})
    for p in soc.get("platforms", []):
        for q in soc.get("queries", []):
            run_social(p, q)
    if seeds.get("search", {}).get("enabled"):
        for q in seeds["search"].get("queries", []):
            run_search(q)


def reanalyze_all() -> int:
    with session_scope() as s:
        ids = [i for (i,) in s.execute(select(Document.id).where(Document.duplicate_of.is_(None)))]
    for i in ids:
        events, llm_ids = analyze_document(i)
        publish(events)
        for fid in llm_ids:
            task_llm_review(fid)
    return len(ids)


def import_registry(sources: list[str] | None = None) -> dict:
    out = {}
    for src in sources or config.REGISTRY_SOURCES:
        if src == "demo":
            out["demo"] = registry.load_demo()
        elif src == "knf":
            from .registry.knf import import_knf
            out.update(import_knf())
    publish([{"type": "registry", "data": {"version": registry.version(), "counts": out}}])
    return out


# ---------------------------------------------------------------------------- zadania kolejki
@huey.task(priority=10, retries=1, retry_delay=30)
def task_web(seed: dict):
    return run_web(seed)


@huey.task(priority=10, retries=1, retry_delay=30)
def task_urls(urls: list[str]):
    return run_urls(urls)


@huey.task(priority=10, retries=1, retry_delay=30)
def task_social(platform: str, query: str):
    return run_social(platform, query)


@huey.task(priority=10)
def task_search(query: str):
    return run_search(query)


@huey.task(priority=5)
def task_recheck():
    return run_recheck()


@huey.task(priority=8)
def task_reanalyze():
    return reanalyze_all()


@huey.task(priority=8)
def task_registry(sources: list[str] | None = None):
    return import_registry(sources)


@huey.task(priority=1, retries=200, retry_delay=15)
def task_llm_review(finding_id: int):
    # jedna ocena LLM naraz (CPU): zajęta blokada → ponowienie później, wątek wraca do zadań scrapingu
    with huey.lock_task("llm-review"):
        return llm_review(finding_id)


# ------------------------------------------------------------------------ harmonogram (cron)
@huey.periodic_task(_cron(config.CRON_WEB))
def periodic_web():
    seeds = load_seeds()
    for seed in seeds.get("web", []):
        task_web(seed)
    if seeds.get("urls"):
        task_urls(seeds["urls"])
    if seeds.get("search", {}).get("enabled"):
        for q in seeds["search"].get("queries", []):
            task_search(q)


@huey.periodic_task(_cron(config.CRON_SOCIAL))
def periodic_social():
    soc = load_seeds().get("social", {})
    for p in soc.get("platforms", []):
        for q in soc.get("queries", []):
            task_social(p, q)


@huey.periodic_task(_cron(config.CRON_RECHECK))
def periodic_recheck():
    task_recheck()


@huey.periodic_task(_cron(config.CRON_REGISTRY))
def periodic_registry():
    task_registry(["knf"] if "knf" in config.REGISTRY_SOURCES else None)


def _heartbeat():
    for _ in range(2):     # start workera i zadanie okresowe mogą wstawić wiersz równocześnie
        try:
            with session_scope() as s:
                put_setting(s, "worker_heartbeat", {"at": utcnow().isoformat()})
            return
        except IntegrityError:
            continue


@huey.periodic_task(crontab(minute="*"))
def periodic_heartbeat():
    _heartbeat()


@huey.on_startup()
def on_worker_start():
    _heartbeat()
