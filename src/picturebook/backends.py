"""Image generation backends for picturebook generate.

Each backend takes a Job and returns a Result. A Job carries the assembled
prompt, the page shape, and the filename the build already expects. A Result
carries whatever files the backend produced.

Two backends ship today:

    manual        Writes a paste-ready queue file. Calls nothing.
    replicate     Calls Replicate's official API.

To add a backend, subclass Backend, give it a `name`, and add it to BACKENDS.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

# Where a backend looks for its key, in order: the environment, then the
# macOS Keychain.
CREDENTIALS = {
    "replicate": ("REPLICATE_API_TOKEN", "replicate-api"),
}


class PredictionFailed(Exception):
    """One prediction failed or timed out. The run can go on to the next page."""


def free_path(out_dir: Path, stem: str) -> Path:
    """The next unused `stem.N.png`, so a new batch never overwrites an old one."""
    n = 1
    while (out_dir / f"{stem}.{n}.png").exists():
        n += 1
    return out_dir / f"{stem}.{n}.png"


@dataclass
class Job:
    """One image to generate."""

    page: str  # "cover", or a zero-padded page number such as "04"
    image: str  # the filename the build expects, such as page-04.png
    text: str  # the whole prompt, master style block already on the front
    aspect: str  # the page shape as a ratio, such as "2:3"
    negative: str = ""  # what to keep out of the picture; no current model takes one
    source: Path | None = None  # a drawing to work from, for --style paint


@dataclass
class Result:
    """What a backend produced for one job."""

    job: Job
    files: list[Path] = field(default_factory=list)
    job_id: str = ""
    note: str = ""


def data_uri(path: Path) -> str:
    """An image file as a data: URI, which Replicate takes in place of a URL."""
    kind = {".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp"}.get(path.suffix.lower(), "png")
    return f"data:image/{kind};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def keychain(service: str) -> str:
    """Read a generic password out of the macOS Keychain, or return ""."""
    try:
        done = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-w"],
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""
    return done.stdout.strip()


def credential(backend: str) -> str:
    """Find a backend's key. The environment wins, then the Keychain."""
    env_name, service = CREDENTIALS.get(backend, ("", ""))
    if not env_name:
        return ""
    return os.environ.get(env_name, "") or keychain(service)


class Backend:
    """A place to send prompts."""

    name = ""

    def __init__(self, extra_flags: str = "", model: str = "",
                 variants: int = 1, seed: int | None = None) -> None:
        self.extra_flags = extra_flags
        self.model = model
        self.variants = max(1, variants)
        self.seed = seed

    def line(self, job: Job) -> str:
        """The prompt exactly as this backend would send it."""
        return f"{job.text} {self.extra_flags}".strip()

    def submit(self, job: Job, out_dir: Path) -> Result:
        raise NotImplementedError

    def finish(self, results: list[Result], jobs: list[Job], out_dir: Path) -> None:
        """Called once after every job. Most backends need nothing here.

        `results` is only what was sent this run. `jobs` is every page asked
        for, cached ones included, because a queue file you can paste from
        should list the whole book however much of it was already sent.
        """


class ManualBackend(Backend):
    """Write the prompts out for you to paste in by hand.

    This calls no service and costs nothing. A prompt you can read before you
    spend money is a good idea.
    """

    name = "manual"

    def submit(self, job: Job, out_dir: Path) -> Result:
        return Result(job=job, note="queued for paste")

    def finish(self, results: list[Result], jobs: list[Job], out_dir: Path) -> None:
        out = ["# Prompt queue", ""]
        out.append("Paste one block at a time. Download each result into this")
        out.append("folder, then run picturebook import to file them by page.")
        out.append("")
        for job in jobs:
            if job.page == "cover":
                label = "Cover"
            elif job.page.isdigit():
                label = f"Page {int(job.page)}"
            else:
                label = job.page
            out.append(f"## {label} — {job.image}, {job.aspect}")
            out.append("")
            out.append("```")
            out.append(self.line(job))
            out.append("```")
            out.append("")
        path = out_dir / "_queue.md"
        path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
        print(f"  wrote {path}")


class ReplicateBackend(Backend):
    """Generate through Replicate's official API.

    Replicate hosts many models behind one key. The key is scoped, the terms
    allow automation, and every prediction returns a seed you can pin to
    regenerate the same look later.

    Aspect ratio is passed straight through as the book's own ratio string,
    so "2:3" arrives as "2:3".
    """

    name = "replicate"

    API = "https://api.replicate.com/v1"
    # Replicate validates the input against each model's own schema and rejects
    # a field the model does not declare, so nothing optional is sent blind.
    #
    #   path        the owner/name slug
    #   max         how many images one prediction can return
    #   image_key   the field carrying an input image, for --style paint
    #   supports    optional fields this model actually accepts
    #
    # These are the models the books have used. Add a new one only after a
    # run proves its fields.
    MODELS = {
        "flux-schnell": {"path": "black-forest-labs/flux-schnell", "max": 4,
                         "supports": {"output_format", "seed", "num_outputs"}},
        "flux-dev": {"path": "black-forest-labs/flux-dev", "max": 4,
                     "supports": {"output_format", "seed", "num_outputs"}},
        "flux-1.1-pro": {"path": "black-forest-labs/flux-1.1-pro", "max": 1,
                         "supports": {"output_format", "seed"}},
        # Image-to-image, for colouring a filed line drawing. These fields were
        # read from each model's schema on 4 October 2026.
        "kontext-pro": {"path": "black-forest-labs/flux-kontext-pro", "max": 1,
                        "image_key": "input_image",
                        "supports": {"output_format", "seed"}},
        "kontext-max": {"path": "black-forest-labs/flux-kontext-max", "max": 1,
                        "image_key": "input_image",
                        "supports": {"output_format", "seed"}},
        "kontext-dev": {"path": "black-forest-labs/flux-kontext-dev", "max": 1,
                        "image_key": "input_image",
                        "supports": {"output_format", "seed"}},
    }
    DEFAULT_MODEL = "flux-schnell"

    # Under $5 of credit, Replicate allows 6 predictions a minute with a burst
    # of 1, and answers 429 to the rest. Waiting it out is cheaper than a
    # failed run.
    THROTTLE_RETRIES = 6
    THROTTLE_WAIT = 10

    def _spec(self) -> dict:
        name = self.model or self.DEFAULT_MODEL
        if name not in self.MODELS:
            raise SystemExit(
                f"error: unknown model {name!r}. Known: {', '.join(sorted(self.MODELS))}\n"
                f"       Add it to ReplicateBackend.MODELS in backends.py."
            )
        return {"name": name, **self.MODELS[name]}

    def _call(self, url: str, key: str, payload: dict | None = None) -> dict:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            url, data=data, method="POST" if data else "GET",
            # Without a User-Agent, model lookups came back 403 on 4 October
            # 2026, though predictions worked. Sent always, to be safe.
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json",
                     "User-Agent": "books-generate-images/1.0"},
        )
        for attempt in range(self.THROTTLE_RETRIES + 1):
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as err:
                detail = err.read().decode("utf-8", "replace")[:500]
                if err.code == 429 and attempt < self.THROTTLE_RETRIES:
                    try:
                        wait = float(json.loads(detail).get("retry_after", 0))
                    except (ValueError, AttributeError):
                        wait = 0
                    wait = max(wait, self.THROTTLE_WAIT)
                    print(f"  throttled, waiting {wait:.0f}s")
                    time.sleep(wait)
                    continue
                raise SystemExit(f"error: {url} returned {err.code}\n       {detail}") from None
            except urllib.error.URLError as err:
                raise SystemExit(f"error: cannot reach {url} ({err.reason})") from None

    def submit(self, job: Job, out_dir: Path) -> Result:
        spec = self._spec()  # a typo in --model should not ask for a token first
        key = credential("replicate")
        if not key:
            raise SystemExit(
                "error: no Replicate token. Set REPLICATE_API_TOKEN, or add it to\n"
                "       the Keychain as the generic password 'replicate-api'.\n"
                "       Get one at replicate.com/account/api-tokens.\n"
                "       Run with --backend manual to write a paste queue instead."
            )
        supports = spec.get("supports", set())
        image_key = spec.get("image_key")
        if bool(image_key) != bool(job.source):
            raise SystemExit(
                f"error: model {spec['name']!r} "
                + ("needs --style paint, which sends it a drawing" if image_key
                   else "cannot take a drawing. Try --model kontext-pro")
            )
        payload = {"prompt": self.line(job), "aspect_ratio": job.aspect}
        if image_key:
            payload[image_key] = data_uri(job.source)
        # Everything below is optional, so it goes only to a model that takes
        # it. Sending output_format to a model without that field is a 422.
        if "output_format" in supports:
            payload["output_format"] = "png"
        if "num_outputs" in supports:
            payload["num_outputs"] = min(self.variants, spec["max"])
        if "seed" in supports and self.seed is not None:
            payload["seed"] = self.seed

        started = self._call(f"{self.API}/models/{spec['path']}/predictions",
                             key, {"input": payload})
        prediction = self._wait(started, key)

        output = prediction.get("output") or []
        if isinstance(output, str):
            output = [output]
        if not output:
            return Result(job=job, job_id=prediction.get("id", ""),
                          note=f"no image returned ({prediction.get('status')})")

        stem = Path(job.image).stem
        files = []
        for url in output:
            path = free_path(out_dir, stem)
            with urllib.request.urlopen(url, timeout=120) as response:
                path.write_bytes(response.read())
            files.append(path)
        return Result(job=job, files=files, job_id=prediction.get("id", ""),
                      note=f"{len(files)} file(s)")

    def _wait(self, prediction: dict, key: str, timeout: int = 600) -> dict:
        """Poll until the prediction settles. Replicate is asynchronous."""
        url = (prediction.get("urls") or {}).get("get", "")
        deadline = time.monotonic() + timeout
        while prediction.get("status") in ("starting", "processing"):
            if time.monotonic() > deadline:
                raise PredictionFailed(f"prediction {prediction.get('id')} timed out")
            time.sleep(2)
            if not url:
                raise SystemExit(f"error: no poll URL in the reply: {prediction}")
            prediction = self._call(url, key)
        if prediction.get("status") != "succeeded":
            raise PredictionFailed(
                f"prediction {prediction.get('id')} "
                f"{prediction.get('status')}: {prediction.get('error')}"
            )
        return prediction


BACKENDS = {
    ManualBackend.name: ManualBackend,
    ReplicateBackend.name: ReplicateBackend,
}
