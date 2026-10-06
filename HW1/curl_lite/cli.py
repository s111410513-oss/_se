"""Command line entry point: wires parsing, transport and output together."""

from __future__ import annotations

import sys
from typing import Sequence, TextIO

from .args import Options, help_text, parse, version_text
from .errors import EXIT_OK, CurlLiteError
from .output import Output, ProgressMeter, flush_stdout, format_write_out
from .transport import Response, Session
from .verbose import VerboseLog


def run(opts: Options, stderr: TextIO | None = None) -> int:
    """Execute every requested URL and return the process exit code."""
    stderr = stderr or sys.stderr
    session = Session(opts)
    output = Output(opts, stderr=stderr)
    log = VerboseLog(opts.verbose, stderr)
    exit_code = EXIT_OK

    try:
        for raw_url in opts.urls:
            exit_code = exit_code or _run_one(session, output, log, opts, raw_url)
    finally:
        output.close()
        session.store_cookies(opts.cookie_jar)
    return exit_code


def _run_one(
    session: Session,
    output: Output,
    log: VerboseLog,
    opts: Options,
    raw_url: str,
) -> int:
    target, method, headers, body = session.prepare(raw_url)
    log.connection(target, insecure=opts.insecure)
    log.request(target, method, headers, body)

    output.open_target(target)

    if opts.head:
        # -I: print the header block and nothing else, exactly like curl.
        response = session.fetch(raw_url)
        log.response(response)
        output.write_headers(response)
        output.write_header_block()
        if opts.verbose:
            log.redirects(response.redirects)
        if opts.write_out:
            _write_out(opts, response)
        flush_stdout()
        return EXIT_OK

    if opts.verbose:
        meter = ProgressMeter(
            _content_length(headers), target[:40], enabled=not opts.quiet, stream=output.stderr
        )
        response = session.fetch(raw_url)
        log.response(response)
        log.redirects(response.redirects)
        log.timings(response, len(body or b""))
        meter.update(response.size)
        meter.finish()
    else:
        meter = None
        response = session.fetch(raw_url)

    output.write_headers(response)
    _emit_body(output, response, meter)

    if opts.write_out:
        _write_out(opts, response)
    flush_stdout()
    return EXIT_OK


def _emit_body(output: Output, response: Response, meter: ProgressMeter | None) -> None:
    if meter is not None:
        meter.update(response.size)
    output.write_response(response)


def _write_out(opts: Options, response: Response) -> None:
    text = format_write_out(opts.write_out or "", response)
    sys.stdout.write(text if text.endswith("\n") or not text else text + "\n")
    flush_stdout()


def _content_length(headers: dict[str, str]) -> int:
    for name, value in headers.items():
        if name.lower() == "content-length" and value.isdigit():
            return int(value)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    program = "curl-lite"
    raw_args = list(sys.argv[1:] if argv is None else argv)

    try:
        opts = parse(raw_args)
    except CurlLiteError as exc:
        _report(program, exc)
        return exc.exit_code

    if opts.show_help:
        sys.stdout.write(help_text(program) + "\n")
        return EXIT_OK
    if opts.show_version:
        sys.stdout.write(version_text() + "\n")
        return EXIT_OK

    try:
        return run(opts)
    except CurlLiteError as exc:
        _report(program, exc, quiet=opts.quiet)
        return exc.exit_code
    except KeyboardInterrupt:
        sys.stderr.write(f"{program}: interrupted\n")
        return 130


def _report(program: str, exc: CurlLiteError, quiet: bool = False) -> None:
    """Print a curl-style diagnostic line on stderr."""
    if quiet:
        return
    if exc.exit_code == 2:
        sys.stderr.write(f"{program}: error: {exc.message}\n")
    else:
        sys.stderr.write(f"{program}: ({exc.exit_code}) {exc.message}\n")
    if exc.hint:
        sys.stderr.write(f"{program}: hint: {exc.hint}\n")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())