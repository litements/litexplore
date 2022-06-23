from uuid import uuid4
import tempfile
import urllib.parse
import json
import logging
import logging.config
import os
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from fastapi import (
    Cookie,
    Depends,
    FastAPI,
    Form,
    Request,
    Response,
    status,
    Header,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import (
    BaseModel as _BaseModel,
    BaseSettings,
    Field,
    validator,
    PrivateAttr,
    UUID4,
)


class BaseModel(_BaseModel):
    class Config:
        frozen = True


class Settings(BaseSettings):
    COOKIE_CONF: str = "ltx_conf"
    IN_TEST: str = "false"
    LOG_LEVEL: str = "info"

    # current module's path
    BASE_DIR: Path = Path(os.path.abspath(__file__)).parent
    STATIC_DIR: Path = BASE_DIR / "static"
    TEMPLATES_DIR: Path = BASE_DIR / "templates"

    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost",
        "https://localhost",
        "https://localhost:8000",
        "http://localhost:8000",
    ]


settings = Settings()


_APP_LOGGER_INITIALIZED = False


def get_logger() -> logging.Logger:

    global _APP_LOGGER_INITIALIZED

    if _APP_LOGGER_INITIALIZED:
        log = logging.getLogger("app")
        return log

    if settings.LOG_LEVEL == "debug":
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    LOGGING_CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn._logging.DefaultFormatter",
                "fmt": 'level=%(levelname)s message="%(message)s"',
                "use_colors": None,
            },
            "access": {
                "()": "uvicorn._logging.AccessFormatter",
                "fmt": 'level=%(levelname)s address=%(client_addr)s request="%(request_line)s" status_code=%(status_code)s',
            },
            "app": {
                "()": "logging.Formatter",
                "fmt": "level=%(levelname)s time=%(created)f %(message)s location=%(pathname)s:%(lineno)d",
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
            "access": {
                "formatter": "access",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
            "app": {
                "formatter": "app",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
        },
        "loggers": {
            "app": {"handlers": ["app"], "level": log_level},
            "uvicorn": {"handlers": ["default"], "level": log_level},
            "uvicorn.error": {"level": "INFO"},
            "uvicorn.access": {
                "handlers": ["access"],
                "level": log_level,
                "propagate": False,
            },
        },
    }

    logging.config.dictConfig(LOGGING_CONFIG)

    class EndpointFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return record.getMessage().find("healthz") == -1

    # Filter out /healthz
    logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

    _APP_LOGGER_INITIALIZED = True

    log = logging.getLogger("app")

    return log


log = get_logger()
templates = Jinja2Templates(directory=str(settings.TEMPLATES_DIR))
static = StaticFiles(directory=str(settings.STATIC_DIR))


# TODO:
# Enable multiple users at the same time using the same server
# USERS = {}

# ¡¡func


def pp(*args, **kwargs):
    print(">" * 5, *args, **kwargs)


SQLiteValue = Union[str, int, float, bytes]


class _SQLiteName(BaseModel):
    name: str
    _escaped_name: str = PrivateAttr()

    def __init__(self, **data):
        super().__init__(**data)
        # this could also be done with default_factory
        self._escaped_name = f"[{self.name}]"

    @validator("name", pre=True, always=True)
    def validate_name(cls, v):
        v = v.strip("[]")
        invalid_chars = ("[", "]", '"', "'")
        if any(x in v for x in invalid_chars):
            raise ValueError(f"Invalid table name: '{v}'")
        return v


class TableName(_SQLiteName):
    ...


class ColumnName(_SQLiteName):
    ...


class ForeignKey(BaseModel):
    src_table: TableName
    src_column: ColumnName
    ref_table: TableName
    ref_column: ColumnName

    @validator("ref_column")
    def default_ref_column(cls, v):
        """
        Set default reference column if not defined
        """
        if not v:
            return cls.src_column
        return v


class GlobalUserConfig(_BaseModel):
    user_id: UUID4 = Field(default_factory=uuid4)
    ssh_host: str
    remote_sqlite_path: str
    remote_sqlite_bin: str = Field(default="sqlite3")
    num_rows_display: int = Field(default=50)

    class Config:
        validate_assignment = True


class MissingConf(Exception):
    pass


class RemoteSqliteBinError(Exception):
    pass


class NoContent(Exception):
    pass


SSH_SOCKET_DIR = tempfile.TemporaryDirectory(prefix="ltx", suffix="tmp-confs")

# print(SSH_SOCKET_DIR.name)


def get_params_cmd(query_params: Dict[str, SQLiteValue]) -> str:
    cmd = [".param clear", ".param init"]

    for param_name, value in query_params.items():
        _c = f'.param set :{param_name} "{value!r}"'
        cmd.append(_c)

    return "\n".join(cmd)


def p_query(query: str, query_params: Dict[str, SQLiteValue]) -> str:
    return get_params_cmd(query_params) + "\n" + query


def get_table_fks(
    tname: TableName, *, ssh_host: str, remote_sqlite_path: str, remote_sqlite_bin: str
) -> Optional[Tuple[ForeignKey, ...]]:

    fks = run(
        ssh_host=ssh_host,
        cmd=f"PRAGMA foreign_key_list({tname._escaped_name})",
        remote_sqlite_db=remote_sqlite_path,
        remote_sqlite_bin=remote_sqlite_bin,
    )

    if not fks:
        return None

    return tuple(
        ForeignKey(
            src_table=tname,
            src_column=ColumnName(name=x["from"]),
            ref_table=TableName(name=x["table"]),
            ref_column=ColumnName(name=x["to"]),
        )
        for x in fks
    )


def validate_remote_sqlite_cli(ssh_host: str, remote_sqlite_bin: str):

    p = subprocess.run(
        [
            "ssh",
            "-o",
            "ControlPersist=5m",
            "-o",
            "ControlMaster=auto",
            "-o",
            f"ControlPath={SSH_SOCKET_DIR.name}/{ssh_host}.socket",
            ssh_host,
            f"{remote_sqlite_bin} -json -version",
        ],
        text=True,
        capture_output=True,
    )

    if p.returncode == 0:
        return

    if "Error: unknown option: -json" in p.stderr:
        raise RemoteSqliteBinError(
            f"The remote SQLite binary '{remote_sqlite_bin}' doesn't support the -json flag. "
            "Please choose or install a version of the SQLite CLI which supports the -json flag."
        )

    else:
        print(p.stderr)
        print(p.stdout)
        raise RemoteSqliteBinError(
            f"An unexpected error happened while trying to validate the remote "
            f"SQLite binary '{remote_sqlite_bin}'."
        )


def run(ssh_host: str, cmd: str, remote_sqlite_db: str, remote_sqlite_bin: str):

    pp(cmd)

    p = subprocess.run(
        [
            "ssh",
            "-o",
            "ControlPersist=5m",
            "-o",
            "ControlMaster=auto",
            "-o",
            f"ControlPath={SSH_SOCKET_DIR.name}/{ssh_host}.socket",
            ssh_host,
            f"{remote_sqlite_bin} -json file://{remote_sqlite_db}?mode=ro",
        ],
        text=True,
        capture_output=True,
        input=cmd,
        check=True,
    )

    if not p.stdout.strip():
        return None

    return json.loads(p.stdout.strip())


def run_write(ssh_host: str, cmd: str, remote_sqlite_db: str, remote_sqlite_bin: str):

    p = subprocess.run(
        [
            "ssh",
            "-o",
            "ControlPersist=5m",
            "-o",
            "ControlMaster=auto",
            "-o",
            f"ControlPath={SSH_SOCKET_DIR.name}/{ssh_host}.socket",
            ssh_host,
            f"{remote_sqlite_bin} -json file://{remote_sqlite_db}",
        ],
        text=True,
        capture_output=True,
        input=cmd,
        check=True,
    )

    if not p.stdout.strip():
        return None

    return json.loads(p.stdout.strip())


# ¡¡app


async def conf_cookie(
    ltx_conf: Optional[str] = Cookie(default=None),
) -> GlobalUserConfig:
    if not ltx_conf:
        raise MissingConf

    return GlobalUserConfig.parse_raw(ltx_conf)


app = FastAPI(title="litexplore")
app.mount("/static", static, name="static")


@app.exception_handler(MissingConf)
async def missing_conf_exception_handler(
    request: Request, exc: MissingConf
) -> RedirectResponse:
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(settings.COOKIE_CONF)
    return response


@app.exception_handler(RemoteSqliteBinError)
async def remote_sqlite_exception_handler(
    request: Request, exc: MissingConf
) -> HTMLResponse:
    response = HTMLResponse(content=str(exc) + "<br></br><a href='/'>Home page</a>")
    response.delete_cookie(settings.COOKIE_CONF)
    return response


@app.exception_handler(NoContent)
async def no_content_exception_handler(request: Request, exc: NoContent) -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    return response


# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/")
async def index(request: Request):

    response = templates.TemplateResponse("index.html", {"request": request})
    response.headers["Cache-Control"] = "public, max-age=600"
    return response


@app.post("/start")
async def start_form(
    ssh_host: str = Form(),
    sqlite_remote_path: str = Form(),
    sqlite_remote_bin: str = Form(default="sqlite3"),
):

    validate_remote_sqlite_cli(ssh_host=ssh_host, remote_sqlite_bin=sqlite_remote_bin)

    new_user_conf = GlobalUserConfig(
        ssh_host=ssh_host,
        remote_sqlite_path=sqlite_remote_path,
        remote_sqlite_bin=sqlite_remote_bin,
    )

    response = RedirectResponse(url="/tables", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key=settings.COOKIE_CONF,
        value=new_user_conf.json(),
        expires=24 * 60 * 60 * 7,
        secure=True,
        httponly=True,
        samesite="strict",
    )

    return response


@app.head("/healthz/", status_code=200)
async def health(response: Response) -> Any:
    response.status_code = status.HTTP_200_OK
    return


@app.get("/tables")
async def tables(request: Request, conf: GlobalUserConfig = Depends(conf_cookie)):

    data = run(
        ssh_host=conf.ssh_host,
        cmd="select name from sqlite_master where type = 'table' and tbl_name != 'sqlite_sequence'",
        remote_sqlite_db=conf.remote_sqlite_path,
        remote_sqlite_bin=conf.remote_sqlite_bin,
    )

    tables = [x["name"] for x in data] if data else []

    response = templates.TemplateResponse(
        "tables.html", {"request": request, "tables": tables}
    )
    return response


def generate_fk_link(ref_table: TableName, ref_column: ColumnName, value: SQLiteValue):
    # {escape(value)}
    _filt = f"{ref_column._escaped_name} = :value"
    filt = urllib.parse.quote(_filt)
    q = f"/view-table?tname={urllib.parse.quote(ref_table.name)}&q={filt}&qp_value={value!r}"
    return q


@app.get("/view-table")
async def view_table(
    request: Request,
    tname: str,
    page: Optional[int] = 0,
    q: Optional[str] = None,
    conf: GlobalUserConfig = Depends(conf_cookie),
    hx_request: Optional[str] = Header(None, include_in_schema=False),
):

    table = TableName(name=tname)

    query_params = {
        pname.lstrip("qp_"): pvalue
        for pname, pvalue in request.query_params.items()
        if pname.startswith("qp_")
    }

    query_params["limit"] = (
        page * conf.num_rows_display if page else conf.num_rows_display
    )
    query_params["offset"] = 0
    if hx_request:
        query_params["limit"] = conf.num_rows_display
        query_params["offset"] = page * conf.num_rows_display if page else 0

    filt = ""
    if q:
        filt = f"where {q} "
    _cmd = f"select _rowid_ as rowid, * from {table.name} {filt} limit :limit offset :offset"

    table_fks = get_table_fks(
        table,
        ssh_host=conf.ssh_host,
        remote_sqlite_path=conf.remote_sqlite_path,
        remote_sqlite_bin=conf.remote_sqlite_bin,
    )
    fks_data = {}

    if table_fks:
        fks_data = {
            foreign_key.src_column.name: foreign_key for foreign_key in table_fks
        }

    cmd = p_query(_cmd, query_params)

    data = run(
        ssh_host=conf.ssh_host,
        cmd=cmd,
        remote_sqlite_db=conf.remote_sqlite_path,
        remote_sqlite_bin=conf.remote_sqlite_bin,
    )

    if not data:
        data = [{}]

    table_dict = defaultdict(list)
    nrows = 0

    fks = {}

    for res in data:
        if not res:
            continue
        for k, v in res.items():
            table_dict[k].append(v)
            if k in fks_data:
                fk: ForeignKey = fks_data[k]
                fks[(nrows, k)] = generate_fk_link(fk.ref_table, fk.ref_column, v)
        nrows += 1

    pp(str(request.query_params))

    next_page = page + 1 if page else 1

    u = request.url
    u = u.replace_query_params(page=next_page, tname=tname)
    if q:
        u = u.replace_query_params(page=next_page, tname=tname, q=q)

    context = {
        "table_name": table.name,
        "request": request,
        "table_dict": table_dict,
        "nrows": nrows,
        "fks": fks,
        "fks_data": fks_data,
        "next_page": next_page,
        "new_query": u.query,
    }

    if nrows == 0:
        raise NoContent

    if hx_request:
        return templates.TemplateResponse("table-rows.html", context=context)

    return templates.TemplateResponse("view-table.html", context=context)


@app.get("/disconnect")
async def rm_conf():
    global SSH_SOCKET_DIR
    SSH_SOCKET_DIR.cleanup()
    SSH_SOCKET_DIR = tempfile.TemporaryDirectory(prefix="ltx", suffix="tmp-confs")
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(settings.COOKIE_CONF)
    return response


@app.on_event("startup")
async def app_startup():
    log.info("Setting up application")
    # webbrowser.open_new_tab("http://127.0.0.1:8000")


@app.on_event("shutdown")
async def app_shutdown():
    log.info("Shutting down application")
    global SSH_SOCKET_DIR
    SSH_SOCKET_DIR.cleanup()
