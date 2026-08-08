import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(interpolate=False, override=True)

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from . import aggregate, al, auth, config, csv_fetch, db, excel_export, mapping, remarks, sheets, sync, tab_pattern


class AlCreate(BaseModel):
    name: str
    date: str
    note: str = ""


class RemarkCreate(BaseModel):
    name: str
    date: str
    note: str = ""


class AlAction(BaseModel):
    name: str


class SheetTabsRequest(BaseModel):
    spreadsheet_id: str


class NoCacheStaticFiles(StaticFiles):
    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY)
app.mount("/static", NoCacheStaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _accounts():
    accounts_json = os.environ.get("ACCOUNTS_JSON")
    if accounts_json:
        return json.loads(accounts_json)
    return auth.load_accounts(config.ACCOUNTS_FILE)


def _user(request):
    return request.session.get("user")


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request, error: str = ""):
    if _user(request):
        return RedirectResponse("/", status_code=303)
    message = "Invalid credentials" if error else None
    response = templates.TemplateResponse(request, "login.html", {"error": message})
    response.headers["Cache-Control"] = "no-store"
    return response


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    hashed = _accounts().get(username)
    if hashed and auth.verify_password(password, hashed):
        request.session["user"] = username
        return RedirectResponse("/", status_code=303)
    return RedirectResponse("/login?error=1", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/", response_class=HTMLResponse)
def index(request: Request, name: str = ""):
    if not _user(request):
        return RedirectResponse("/login", status_code=303)
    response = templates.TemplateResponse(request, "report.html", {"name": name.strip()})
    response.headers["Cache-Control"] = "no-store"
    return response


def _merge_remarks(conn, name, rows):
    remark_by_date = remarks.get_remarks(conn, name)
    for row in rows:
        row["remark"] = remark_by_date.get(row["date"], "")
    return rows


def _report_payload(conn, name):
    rows, unmapped = aggregate.generate_report(conn, name)
    _merge_remarks(conn, name, rows)
    al_dates = al.list_al_dates(conn, name)
    return {"rows": rows, "unmapped": unmapped, "al_dates": al_dates}


@app.get("/api/report")
def api_report(request: Request, name: str = ""):
    if not _user(request):
        raise HTTPException(status_code=401)
    name = name.strip()
    if not name:
        return {"rows": [], "unmapped": [], "al_dates": []}
    conn = db.init_db(config.DB_PATH)
    try:
        return _report_payload(conn, name)
    finally:
        conn.close()


@app.post("/api/al")
def api_add_al(request: Request, payload: AlCreate):
    if not _user(request):
        raise HTTPException(status_code=401)
    name = payload.name.strip()
    if not name:
        return {"al_dates": []}
    date = payload.date.strip()
    note = payload.note.strip()
    conn = db.init_db(config.DB_PATH)
    try:
        al.add_al_date(conn, name, date, note)
        return {"al_dates": al.list_al_dates(conn, name)}
    finally:
        conn.close()


@app.post("/api/al/{al_id}/delete")
def api_delete_al(request: Request, al_id: int, payload: AlAction):
    if not _user(request):
        raise HTTPException(status_code=401)
    name = payload.name.strip()
    if not name:
        return {"al_dates": []}
    conn = db.init_db(config.DB_PATH)
    try:
        al.delete_al_date(conn, al_id)
        return {"al_dates": al.list_al_dates(conn, name)}
    finally:
        conn.close()


@app.post("/api/remarks")
def api_set_remark(request: Request, payload: RemarkCreate):
    if not _user(request):
        raise HTTPException(status_code=401)
    name = payload.name.strip()
    date = payload.date.strip()
    if not name or not date:
        raise HTTPException(status_code=400, detail="name and date are required")
    conn = db.init_db(config.DB_PATH)
    try:
        remarks.set_remark(conn, name, date, payload.note.strip())
    finally:
        conn.close()
    return {"ok": True}


@app.get("/report.xlsx")
def report_xlsx(request: Request, name: str = ""):
    if not _user(request):
        return RedirectResponse("/login", status_code=303)
    name = name.strip()
    if not name:
        return RedirectResponse("/", status_code=303)
    conn = db.init_db(config.DB_PATH)
    try:
        rows, _ = aggregate.generate_report(conn, name)
        _merge_remarks(conn, name, rows)
    finally:
        conn.close()
    data = excel_export.rows_to_xlsx(rows)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}.xlsx"'},
    )


@app.get("/sheets", response_class=HTMLResponse)
def sheets_page(request: Request):
    if not _user(request):
        return RedirectResponse("/login", status_code=303)
    conn = db.init_db(config.DB_PATH)
    try:
        docs = mapping.list_docs(conn)
        pending = mapping.pending_tabs(conn)
    finally:
        conn.close()
    return templates.TemplateResponse(request, "sheets.html", {"docs": docs, "pending": pending})


@app.post("/sheets/{spreadsheet_id}/operation-hours")
def set_operation_hours(request: Request, spreadsheet_id: str, hours: str = Form(...)):
    if not _user(request):
        raise HTTPException(status_code=401)
    conn = db.init_db(config.DB_PATH)
    try:
        mapping.set_operation_hours(conn, spreadsheet_id, hours)
    finally:
        conn.close()
    return RedirectResponse("/sheets", status_code=303)


@app.post("/sheets/{spreadsheet_id}/delete")
def delete_doc(request: Request, spreadsheet_id: str):
    if not _user(request):
        raise HTTPException(status_code=401)
    conn = db.init_db(config.DB_PATH)
    try:
        mapping.delete_doc(conn, spreadsheet_id)
    finally:
        conn.close()
    return RedirectResponse("/sheets", status_code=303)


@app.post("/api/sheets/tabs")
def api_sheets_tabs(request: Request, payload: SheetTabsRequest):
    if not _user(request):
        raise HTTPException(status_code=401)
    tabs = sheets.list_tabs(payload.spreadsheet_id.strip(), config.GOOGLE_API_KEY)
    for t in tabs:
        t["pattern"] = tab_pattern.infer_pattern(t["title"])
    return {"tabs": tabs}


@app.get("/sheets/{spreadsheet_id}/configure", response_class=HTMLResponse)
def configure_form(request: Request, spreadsheet_id: str, gid: str, tab_pattern: str = ""):
    if not _user(request):
        return RedirectResponse("/login", status_code=303)
    grid = csv_fetch.fetch_csv(spreadsheet_id, gid)
    conn = db.init_db(config.DB_PATH)
    try:
        doc = mapping.get_doc(conn, spreadsheet_id)
        default_header_row = mapping.default_header_row(conn, doc["id"]) if doc else None
    finally:
        conn.close()
    previews = [", ".join(cell.strip() for cell in row if cell.strip()) for row in grid[:15]]
    return templates.TemplateResponse(
        request,
        "configure.html",
        {
            "spreadsheet_id": spreadsheet_id,
            "gid": gid,
            "previews": previews,
            "default_header_row": default_header_row,
            "error": None,
            "tab_pattern": tab_pattern or (doc["tab_pattern"] if doc else "") or "",
            "label": doc["label"] if doc else "",
        },
    )


@app.post("/sheets/{spreadsheet_id}/configure")
def configure_submit(
    request: Request,
    spreadsheet_id: str,
    gid: str = Form(...),
    label: str = Form(...),
    header_row: int = Form(...),
    tab_pattern: str = Form(""),
):
    if not _user(request):
        return RedirectResponse("/login", status_code=303)
    grid = csv_fetch.fetch_csv(spreadsheet_id, gid)
    detected = mapping.detect_date_range(grid, header_row)
    if detected is None:
        previews = [", ".join(cell.strip() for cell in row if cell.strip()) for row in grid[:15]]
        return templates.TemplateResponse(
            request,
            "configure.html",
            {
                "spreadsheet_id": spreadsheet_id,
                "gid": gid,
                "previews": previews,
                "default_header_row": header_row,
                "error": "Could not auto-detect a date column from that row.",
                "tab_pattern": tab_pattern,
                "label": label,
            },
            status_code=400,
        )
    conn = db.init_db(config.DB_PATH)
    try:
        doc_id = mapping.save_mapping(conn, spreadsheet_id, label, tab_pattern=tab_pattern.strip() or None)
        tabs = {t["gid"]: t["title"] for t in sheets.list_tabs(spreadsheet_id, config.GOOGLE_API_KEY)}
        mapping.mark_tab_known(conn, doc_id, gid, tabs.get(gid, gid))
        mapping.configure_tab(
            conn, doc_id, gid, header_row, detected["date_col"], detected["row_start"], detected["row_end"]
        )
    finally:
        conn.close()
    return RedirectResponse("/sheets", status_code=303)


@app.post("/api/sync")
def api_sync(request: Request):
    if not _user(request):
        raise HTTPException(status_code=401)
    conn = db.init_db(config.DB_PATH)
    try:
        return {"new_tabs": sync.check_new_tabs_all(conn, config.GOOGLE_API_KEY)}
    finally:
        conn.close()


@app.get("/codes", response_class=HTMLResponse)
def codes_page(request: Request):
    if not _user(request):
        return RedirectResponse("/login", status_code=303)
    conn = db.init_db(config.DB_PATH)
    try:
        docs = []
        for doc in mapping.list_docs(conn):
            hours_map = aggregate.get_code_hours(conn, doc["id"])
            period_map = aggregate.get_branch_operation_hours(conn, doc["id"])
            codes = {
                code: {"hours": hours_map.get(code), "operation_hours": period_map.get(code)}
                for code in hours_map.keys() | period_map.keys()
            }
            docs.append({"doc": doc, "codes": codes})
    finally:
        conn.close()
    return templates.TemplateResponse(request, "codes.html", {"docs": docs})


@app.post("/codes")
def codes_submit(
    request: Request,
    spreadsheet_id: str = Form(...),
    code: str = Form(...),
    hours: str = Form(""),
    operation_hours: str = Form(""),
):
    if not _user(request):
        return RedirectResponse("/login", status_code=303)
    conn = db.init_db(config.DB_PATH)
    try:
        doc = mapping.get_doc(conn, spreadsheet_id)
        if doc is not None:
            code_upper = code.strip().upper()
            if hours.strip():
                aggregate.set_code_hours(conn, doc["id"], code_upper, float(hours))
            if operation_hours.strip():
                aggregate.set_branch_operation_hours(conn, doc["id"], code_upper, operation_hours.strip())
    finally:
        conn.close()
    return RedirectResponse("/codes", status_code=303)


class CodeHoursCreate(BaseModel):
    spreadsheet_id: str
    code: str
    hours: float | None = None  # None marks the code ignored


@app.post("/api/codes")
def api_set_code_hours(request: Request, payload: CodeHoursCreate):
    if not _user(request):
        raise HTTPException(status_code=401)
    conn = db.init_db(config.DB_PATH)
    try:
        doc = mapping.get_doc(conn, payload.spreadsheet_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="Unknown spreadsheet_id")
        aggregate.set_code_hours(conn, doc["id"], payload.code.strip().upper(), payload.hours)
    finally:
        conn.close()
    return {"ok": True}
