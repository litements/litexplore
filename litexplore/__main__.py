import argparse
import uvicorn


parser = argparse.ArgumentParser()
parser.add_argument("--dev", help="run in DEV mode", action="store_true")
parser.add_argument("--host", required=False, default="0.0.0.0")
parser.add_argument("--port", type=int, required=False, default=8000)

args = parser.parse_args()

if args.dev:
    uvicorn.run(
        "litexplore.app:app",
        host=args.host,
        port=args.port,
        reload=True,
        log_level="debug",
        workers=1,
    )

else:
    uvicorn.run(
        "litexplore.app:app",
        host=args.host,
        port=args.port,
        reload=False,
        log_level="info",
        workers=2,
        proxy_headers=True,
        access_log=True,
        timeout_keep_alive=120,
        loop="auto",
        forwarded_allow_ips="*",
    )
raise SystemExit
