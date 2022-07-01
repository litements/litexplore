# litexplore

![litexplore](https://user-images.githubusercontent.com/37962604/175427068-5df7d19d-41b2-4101-a7d6-83fd0d5ca21d.svg)

The current options to explore remote SQLite databases require running a service
on the remote and make it listen on some port. Another option is SSH'ing to the
remote instance and use the SQLite CLI to explore the database. **Litexplore** is a
Python web app that lets you explore remote SQLite databases over SSH
connections without having to copy the full DB or manually use the CLI.

It works by sending commands over an SSH connection. The connection is
multiplexed and it's reused to send commands. This reduces the overhead of
openning a new SSH connection to send each command.

> NOTE: `litexplore` is still in an early beta state. It works and it's usable,
> but there may be signficant changes happening.

## Requirements

- python 3.7 or higher
- pydantic
- fastapi
- uvicorn
- Jinja2
- python-multipart

## Installation

1. Create a virtual env

```sh
python3 -m venv .venv
```

2. Activate the venv and install the dependencies

```sh
source .venv/bin/activate
python3 -m pip install litexplore
```

3. Run the program

```sh
litexplore
```

4. Open your browser at `http://127.0.0.1:8000`

_Note_: even though the server uses `0.0.0.0` as the default host, open the browser at `127.0.0.1`. Otherwise, cookies won't work and they're used to store the user config.

Run `litexplore --help` to see other available options.

### Using `pipx`

1. Install `litexplore`

```sh
pipx install litexplore
```

2. Run it:

```sh
litexplore
```

## Usage

The main page is a form with 3 inputs.

- The first input us the SSH host name as defined in your `~/.ssh`config`
- The second input is the path to an SQLite database in the remote host
- The third (optional) input is a path to an SQLite CLI. Some pre-installed sqlite3 CLIs have not been compiled
  with support for the `-json` flag, which `litexplore` uses.

## How it works

See [this blog post](https://ricardoanderegg.com/posts/sqlite-remote-explorer-gui/)

## Roadmap

See [roadmap issues](https://github.com/litements/litexplore/labels/roadmap)

## Lincese(s)

- This Project: [MIT](https://github.com/litements/litexplore/blob/1a70c0bf6cc52ac7e9fdcaa1a22c113d9df823cc/LICENSE)

- The `arun` function was originally adapted from datasette-ripgrep: [Apache 2.0](https://github.com/simonw/datasette-ripgrep/blob/03446464420130368582022eeb5944993f64ec8f/LICENSE)

The code from Alpine JS and HTMX is also included in this repository. Those
projects are under the following licenses:

- Alpine JS: [MIT](https://github.com/alpinejs/alpine/blob/763e287842da1d9e0a32c52015cfd5c8f33dbac7/LICENSE.md)
- HTMX: [BSD 2-Clause "Simplified" License](https://github.com/bigskysoftware/htmx/blob/299a9baa1df31bcee78f52677c4444095b5b3db2/LICENSE)
