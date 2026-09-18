# Browser tests

These press the buttons. Everything that has gone wrong in this app recently
went wrong in the browser, and the browser had nothing that could click
anything — the engine has a test suite, the page had a syntax parser. So the
resume card was wired into the wrong function, three of the four routes into a
session skipped the knee question, and the walk showed in the planner but not
in the session. Each was found by the person using the app.

No backend is needed. Every request is answered from a dictionary in
`harness.py`, which makes each test a statement about the page rather than
about the server.

## Setup

```bash
uv venv .uivenv
uv pip install --python .uivenv/bin/python playwright
.uivenv/bin/python -m playwright install chromium
```

Chromium needs four system libraries. With root:

```bash
sudo apt install libnss3 libnspr4 libasound2t64
```

Without root, fetch and point at them — no install required:

```bash
mkdir -p .uilibs && cd .uilibs
apt-get download libnss3 libnspr4 libasound2t64
for d in *.deb; do dpkg-deb -x "$d" extracted; done
export LD_LIBRARY_PATH=$PWD/extracted/usr/lib/x86_64-linux-gnu
```

## Running

```bash
.uivenv/bin/python tests/ui/test_ui.py
```

## Adding a test

Each one names the bug it exists for. Keep that: a test whose reason has been
forgotten is the first thing deleted when it becomes inconvenient.

And check a new test can fail — remove the fix it guards and watch it go red
before trusting it. The morning-score test was verified that way: with the
gate taken out it failed three checks, one of them a crash nobody had noticed.
