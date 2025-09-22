# mlsysops_cli/utils/response.py
from __future__ import annotations
import json, difflib
import click
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .ui import ok, err, warn, table_kv


def _safe_json(resp):
    try:
        return resp.json()
    except Exception:
        return None


def _format_loc(loc):
    if not isinstance(loc, list):
        return ""
    parts = [p for p in loc if p != "body"]
    out = []
    for p in parts:
        if isinstance(p, int) and out:
            out[-1] = f"{out[-1]}[{p}]"
        else:
            out.append(str(p))
    return ".".join(out)


def _suggest_key(missing_key: Optional[str], present_keys: Iterable[str]) -> Optional[str]:
    if not missing_key:
        return None
    matches = difflib.get_close_matches(missing_key, list(present_keys), n=1, cutoff=0.6)
    return matches[0] if matches else None


def _print_problem_json(resp, data: Dict[str, Any], *, payload: Optional[Dict] = None) -> None:
    # If someday your API returns application/problem+json, we'll render it nicely.
    if "status" in data and data["status"] != resp.status_code:
        warn(f"⚠️ Status mismatch: HTTP {resp.status_code} but body.status={data['status']}")
    title = data.get("title") or "Error"
    code = data.get("error_code")
    click.secho(f"❌ {title}  [{resp.status_code}{' / ' + code if code else ''}]", fg="red", bold=True)

    if data.get("detail"):
        click.secho(f"   ↳ {data['detail']}", fg="yellow")

    errs = data.get("errors")
    if isinstance(errs, list):
        click.secho("   Details:", fg="red")
        for i, e in enumerate(errs, 1):
            msg = e.get("msg", "Invalid input")
            typ = e.get("type", "")
            loc = _format_loc(e.get("loc", []))
            line = f"   {i}. {msg}"
            if typ: line += f"  [{typ}]"
            click.secho(line, fg="red")
            if loc: click.secho(f"      at: {loc}", fg="yellow")

            # typo hint
            if e.get("type") == "missing":
                missing = None
                for item in reversed(e.get("loc") or []):
                    if isinstance(item, str) and item != "body":
                        missing = item;
                        break
                present = []
                if isinstance(e.get("input"), dict):
                    present = list(e["input"].keys())
                elif isinstance(payload, dict):
                    present = list(payload.keys())
                hint = _suggest_key(missing, present)
                if hint and hint != missing:
                    click.secho(f"      💡 did you mean: '{hint}' ?", fg="cyan")

    if data.get("doc"):        click.secho(f"   🔗 docs: {data['doc']}", fg="cyan")
    if data.get("request_id"): click.secho(f"   🆔 request-id: {data['request_id']}", fg="cyan")


def _print_fastapi_detail(resp, data: Any) -> None:
    """
    Handle common non-problem+json error shapes:
      - {"detail": "..."} or {"detail":[{...}]}
      - {"error": "..."} or {"error": {...}}
      - {"message": "..."} on error codes
    """
    # 1) Standard FastAPI
    if isinstance(data, dict) and "detail" in data:
        det = data["detail"]
        if isinstance(det, str):
            click.secho(f"❌ {det}  [{resp.status_code}]", fg="red", bold=True);
            return
        if isinstance(det, list):
            click.secho(f"❌ Error  [{resp.status_code}]", fg="red", bold=True)
            for i, e in enumerate(det, 1):
                if isinstance(e, dict):
                    msg = e.get("msg") or str(e)
                    typ = e.get("type", "")
                    loc = _format_loc(e.get("loc", []))
                    line = f"   {i}. {msg}"
                    if typ: line += f"  [{typ}]"
                    click.secho(line, fg="red")
                    if loc: click.secho(f"      at: {loc}", fg="yellow")
                else:
                    click.secho(f"   {i}. {e}", fg="red")
            return
        # unknown detail type -> fallthrough

    # 2) Ad-hoc {"error": "..."} or {"message": "..."}
    if isinstance(data, dict):
        msg = data.get("error") or data.get("message")
        if msg:
            click.secho(f"❌ {msg}  [{resp.status_code}]", fg="red", bold=True)
            extras = {k: v for k, v in data.items() if k not in ("error", "message")}
            if extras:
                try:
                    click.echo(json.dumps(extras, indent=2, ensure_ascii=False))
                except Exception:
                    pass
            return

    # 3) Fallback: show JSON or raw text
    click.secho(f"❌ HTTP {resp.status_code}", fg="red", bold=True)
    try:
        click.echo(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception:
        click.echo(str(data))


def handle_response(
        resp,
        *,
        success_title: Optional[str] = None,
        success_fields: Optional[List[Tuple[str, str]]] = None,
        payload: Optional[Dict] = None,
        exit_on_error: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Generic response handler for the CLI.

    - Prints success (2xx) with optional table of fields.
    - Prints errors (>=400) for either problem+json or FastAPI/detail/error/message shapes.
    - Returns parsed JSON on success, else None.
    """
    ctype = (resp.headers.get("content-type") or "").lower()
    data = _safe_json(resp)

    if 200 <= resp.status_code < 300:
        if success_title: ok(success_title)
        if isinstance(data, dict) and success_fields:
            rows = [(label, data.get(key)) for key, label in success_fields]
            table_kv(rows, title=success_title or "OK")
        else:
            if isinstance(data, (dict, list)):
                click.echo(json.dumps(data, indent=2, ensure_ascii=False))
            else:
                click.echo(resp.text)
        return data

    # error paths
    if "application/problem+json" in ctype and isinstance(data, dict):
        _print_problem_json(resp, data, payload=payload)
    elif isinstance(data, (dict, list)):
        _print_fastapi_detail(resp, data)
    else:
        click.secho(f"❌ HTTP {resp.status_code}", fg="red", bold=True)
        click.echo(resp.text)

    if exit_on_error:
        if 400 <= resp.status_code < 500: raise SystemExit(2)
        if resp.status_code >= 500:       raise SystemExit(3)
        raise SystemExit(1)
    return None
