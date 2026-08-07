from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import aggregate, auth, config, db, excel_export

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _accounts():
    return auth.load_accounts(config.ACCOUNTS_FILE)


def _user(request):
    return request.session.get("user")


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    hashed = _accounts().get(username)
    if hashed and auth.verify_password(password, hashed):
        request.session["user"] = username
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request, "login.html", {"error": "Invalid credentials"}, status_code=401
    )


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/", response_class=HTMLResponse)
def index(request: Request, name: str = ""):
    if not _user(request):
        return RedirectResponse("/login", status_code=303)
    rows, unmapped = [], []
    name = name.strip()
    if name:
        conn = db.init_db(config.DB_PATH)
        try:
            rows, unmapped = aggregate.generate_report(conn, name)
        finally:
            conn.close()
    return templates.TemplateResponse(
        request, "report.html", {"name": name, "rows": rows, "unmapped": unmapped}
    )


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
    finally:
        conn.close()
    data = excel_export.rows_to_xlsx(rows)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}.xlsx"'},
    )
