"""PDF certificate generation (Cedar-derived data).

Renders wipe (erasure) and audit (asset) certificates to PDF via WeasyPrint.

Locked data shapes (verified against live Cedar + DB rows):

DataWipeRecord
    json_data: {"erasure_results": [<cert>]}
    erasure cert top-level: standard, level, result, operative_name,
        reference_number, asset_number, model_number, serial_number,
        vendor, media, interface, bytes, duration, software_product
    erasure cert metadata.report.process: standard, level, result,
        comments, erasure_rounds, firmware_rounds, verification_rounds,
        total_rounds, erasure.rounds.technique, verification.technique/mode
    erasure cert metadata.report.timestamps: started, ended, duration
    erasure cert metadata.hash: integrity checksum

AuditRecord
    test_results: full asset cert:
        top-level: serial_number (device), asset_number, operative_name,
            result ("Pass"/"Fail"), standard, battery_health,
            memory_total, storage_total, display_size, processor_model_number
        tests: dict of components -> {name, result ("Pass"/"Fail"/"Skipped"), comments}
        metadata.report.timestamps / metadata.hash
"""

from pathlib import Path

from django.template import Context, Engine
from weasyprint import HTML

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "template" / "pdf"
LOGO_PATH = Path("/app/core/static/core/Logo.svg")


def _load_template(template_name):
    return (TEMPLATE_DIR / template_name).read_text(encoding="utf-8")


def _render_html(template_name, context):
    engine = Engine(dirs=[str(TEMPLATE_DIR)])
    template = engine.from_string(_load_template(template_name))
    return template.render(Context(context))


def _render_pdf(template_name, context, output_path):
    html_string = _render_html(template_name, context)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_string, base_url=str(TEMPLATE_DIR)).write_pdf(str(output_path))
    return str(output_path)


def _fmt_dt(value):
    if not value:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M")
    s = str(value)
    if "T" in s:
        s = s.replace("T", " ")[:16]
    return s


def _fmt_bytes(value):
    if value in (None, ""):
        return ""
    try:
        v = int(value)
    except (TypeError, ValueError):
        return str(value)
    if v >= 1_000_000_000:
        return f"{v / 1_000_000_000:.0f} GB"
    if v >= 1_000_000:
        return f"{v / 1_000_000:.0f} MB"
    return f"{v} B"


def _fmt_gib(value):
    if value in (None, ""):
        return ""
    try:
        v = int(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{v / (2**30):.0f} GB"


def _fmt_duration(value):
    if value in (None, ""):
        return ""
    if isinstance(value, str) and ":" in value:
        return value
    try:
        secs = int(value)
    except (TypeError, ValueError):
        return str(value)
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _fieldfile_path(value):
    """Return a filesystem path for a FileField, or None if empty.

    FieldFile.path raises ValueError (not AttributeError) when no file is
    attached, so hasattr() is unsafe here.
    """
    if value is None:
        return None
    name = getattr(value, "name", None)
    if name:
        try:
            return value.path
        except (ValueError, NotImplementedError):
            return None
    return str(value) if value else None


def _resolve_output_path(record, subdir, suffix, fallback_id):
    """Return a usable PDF output path for a certificate record.

    Records created by the Cedar sync often have an empty
    certificate_file, so derive a deterministic filename (mirroring
    workbench/order_views.py) instead of raising.
    """
    path = _fieldfile_path(record.certificate_file)
    if not path:
        from django.conf import settings as _settings
        rel = "%s/%s_%s.pdf" % (subdir, fallback_id, suffix)
        record.certificate_file.name = rel
        record.save(update_fields=["certificate_file"])
        path = str(Path(_settings.MEDIA_ROOT) / rel)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return path


def _logo_url():
    return LOGO_PATH.as_uri() if LOGO_PATH.exists() else ""


def _pick(*values):
    for v in values:
        if v not in (None, ""):
            return v
    return ""


def _first_cert(json_data):
    items = (json_data or {}).get("erasure_results", [])
    return items[0] if items and isinstance(items[0], dict) else {}


def _comments_str(value):
    if isinstance(value, list):
        return " ".join(str(x) for x in value if x)
    return str(value) if value else ""


def _device_identity(device):
    spec = getattr(device, "device_specification", None)
    return {
        "serial_number": device.serial_number or "",
        "device_type": device.device_type or "",
        "manufacturer": spec.manufacturer if spec else "",
        "model_name": spec.model_name if spec else "",
        "model_number": spec.model_number if spec else "",
    }


def _extract_wipe_summary(json_data):
    cert = _first_cert(json_data)
    metadata = cert.get("metadata") or {}
    report = metadata.get("report") or {}
    process = report.get("process") or {}
    timestamps = report.get("timestamps") or {}
    erasure = process.get("erasure") or {}
    verification = process.get("verification") or {}

    erasure_technique = ""
    erasure_rounds = erasure.get("rounds") or {}
    if isinstance(erasure_rounds, dict):
        for rnd in erasure_rounds.values():
            if isinstance(rnd, dict):
                erasure_technique = rnd.get("technique", "")
                break

    verification_technique = verification.get("technique", "")
    verification_mode = verification.get("mode", "")

    software = _pick(report.get("software_product"), cert.get("software_product")) or "Drive Eraser"
    if not software.lower().startswith("cedar"):
        software = f"Cedar {software}"

    return {
        "standard": _pick(cert.get("standard"), process.get("standard")),
        "level": _pick(cert.get("level"), process.get("level")),
        "result": _pick(cert.get("result"), process.get("result")),
        "software_product": software,
        "operative": _pick(report.get("operative_name"), cert.get("operative_name")),
        "reference_number": _pick(report.get("reference_number"), cert.get("reference_number")),
        "asset_number": _pick(report.get("asset_number"), cert.get("asset_number")),
        "started": timestamps.get("started", ""),
        "ended": timestamps.get("ended", ""),
        "duration": timestamps.get("duration", ""),
        "rounds": {
            "firmware": process.get("firmware_rounds", ""),
            "verification": process.get("verification_rounds", ""),
            "total": process.get("total_rounds", ""),
        },
        "erasure_technique": erasure_technique,
        "verification_technique": verification_technique,
        "verification_mode": verification_mode,
        "hash": metadata.get("hash", ""),
        "comments": process.get("comments", []) or [],
    }


def _extract_drive_details(json_data):
    drives = []
    for item in (json_data or {}).get("erasure_results", []):
        if not isinstance(item, dict):
            continue
        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        drives.append({
            "model": _pick(item.get("model_number"), data.get("model")),
            "serial_number": _pick(item.get("serial_number"), data.get("serial_number")),
            "capacity": _fmt_bytes(item.get("bytes")) or _pick(data.get("capacity")),
            "status": str(_pick(item.get("result"), data.get("status"))).strip().upper(),
            "standard": _pick(item.get("standard"), data.get("standard")),
            "duration": _fmt_duration(item.get("duration")) or _pick(data.get("duration")),
            "media": _pick(item.get("media"), data.get("media")),
            "interface": _pick(item.get("interface"), data.get("interface")),
        })
    return drives


def _extract_audit_tests(test_results):
    cert = test_results or {}
    tests = []

    raw = cert.get("tests") or {}
    if not raw:
        report = cert.get("metadata", {}).get("report") or {}
        raw = report.get("audit") or {}

    if isinstance(raw, dict):
        for key, comp in raw.items():
            if not isinstance(comp, dict):
                continue
            tests.append({
                "name": comp.get("name") or key or "",
                "result": str(comp.get("result", "")).strip().upper(),
                "details": _comments_str(comp.get("comments")),
            })
        return tests

    # Older stored shape: data.tests as a list
    data = cert.get("data") or {}
    for item in data.get("tests", []):
        if isinstance(item, dict):
            tests.append({
                "name": item.get("name", ""),
                "result": str(item.get("result", "")).strip().upper(),
                "details": _comments_str(item.get("details") or item.get("comments")),
            })
    return tests


def _extract_audit_summary(test_results):
    cert = test_results or {}
    metadata = cert.get("metadata") or {}
    report = metadata.get("report") or {}
    timestamps = report.get("timestamps") or {}

    return {
        "operative": _pick(report.get("operative_name"), cert.get("operative_name")),
        "reference_number": _pick(report.get("reference_number"), cert.get("reference_number")),
        "asset_number": _pick(report.get("asset_number"), cert.get("asset_number")),
        "standard": _pick(report.get("standard"), cert.get("standard")),
        "result": _pick(report.get("result"), cert.get("result")),
        "started": timestamps.get("started", ""),
        "ended": timestamps.get("ended", ""),
        "hash": metadata.get("hash", ""),
        "comments": report.get("comments", []) or [],
        "battery_health": cert.get("battery_health", ""),
        "display_size": cert.get("display_size", ""),
        "memory_total": cert.get("memory_total", ""),
        "storage_total": cert.get("storage_total", ""),
        "processor": cert.get("processor_model_number", ""),
    }


def generate_wipe_certificate(device, wipe_record):
    identity = _device_identity(device)
    drives = _extract_drive_details(wipe_record.json_data)
    summary = _extract_wipe_summary(wipe_record.json_data)

    notes = wipe_record.notes or ""
    if notes.startswith("Synced from Cedar"):
        notes = ""

    context = {
        "logo_url": _logo_url(),
        "identity": identity,
        "result": _pick(wipe_record.result, summary["result"]),
        "wipe_software": summary["software_product"],
        "wipe_standard": _pick(wipe_record.wipe_standard, summary["standard"]),
        "wipe_level": summary["level"],
        "operative": summary["operative"],
        "reference_number": summary["reference_number"],
        "asset_number": summary["asset_number"],
        "started_at": _fmt_dt(summary["started"]),
        "ended_at": _fmt_dt(summary["ended"]),
        "duration": summary["duration"],
        "rounds": summary["rounds"],
        "erasure_technique": summary["erasure_technique"],
        "verification_technique": summary["verification_technique"],
        "verification_mode": summary["verification_mode"],
        "hash": summary["hash"],
        "comments": summary["comments"],
        "wiped_by": wipe_record.wiped_by or "",
        "wiped_at": _fmt_dt(wipe_record.wiped_at or wipe_record.uploaded_at),
        "drives": drives,
        "drive_count": len(drives),
        "notes": notes,
    }

    output_path = _resolve_output_path(
        wipe_record, "wipe_certificates", "wipe",
        getattr(device, "inventory_number", None) or device.pk,
    )
    return _render_pdf("wipe_certificate.html", context, output_path)


def generate_audit_certificate(device, audit_record):
    identity = _device_identity(device)
    tests = _extract_audit_tests(audit_record.test_results)
    summary = _extract_audit_summary(audit_record.test_results)

    notes = audit_record.notes or ""
    if notes.startswith("Synced from Cedar") or notes.startswith("Drive:"):
        notes = ""

    result = _pick(audit_record.result, summary["result"])
    result = str(result).strip().upper() if result else ""

    context = {
        "logo_url": _logo_url(),
        "identity": identity,
        "result": result,
        "operative": summary["operative"],
        "reference_number": summary["reference_number"],
        "asset_number": summary["asset_number"],
        "standard": summary["standard"],
        "started_at": _fmt_dt(summary["started"]),
        "ended_at": _fmt_dt(summary["ended"]),
        "hash": summary["hash"],
        "comments": summary["comments"],
        "battery_health": summary["battery_health"],
        "display_size": summary["display_size"],
        "memory_total": _fmt_gib(summary["memory_total"]),
        "storage_total": summary["storage_total"],
        "processor": summary["processor"],
        "tests": tests,
        "notes": notes,
    }

    output_path = _resolve_output_path(
        audit_record, "audit_certificates", "audit",
        getattr(device, "inventory_number", None) or device.pk,
    )
    return _render_pdf("audit_certificate.html", context, output_path)

