"""Default locations of the evidence bundles and the private (grader-only) data.

Both live inside the installed package. In the container the package is installed
under ``/root`` (mode 0700), so neither directory is readable by the student.
Episode, evidence and scratch locations are NOT defined here: the core receives them
through :class:`environment.incident.episode.EpisodeConfig`.

``bundle/`` is the frozen MVP bundle (task ``gb-2019-electrical-disturbance``);
``bundles/system_response/`` is the manifest-v2 bundle of the widened task
``gb-2019-system-response``, whose grader-only data live in ``private/system_response/``;
``bundles/full_investigation/`` is the manifest-v2 bundle of the full investigation
``gb-2019-full-investigation`` (increment B), with ``private/full_investigation/``.
"""

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_BUNDLE_DIR = PACKAGE_DIR / "bundle"
DEFAULT_PRIVATE_DIR = PACKAGE_DIR / "private"
BUNDLES_DIR = PACKAGE_DIR / "bundles"
SYSTEM_RESPONSE_BUNDLE_DIR = BUNDLES_DIR / "system_response"
SYSTEM_RESPONSE_PRIVATE_DIR = DEFAULT_PRIVATE_DIR / "system_response"
FULL_INVESTIGATION_BUNDLE_DIR = BUNDLES_DIR / "full_investigation"
FULL_INVESTIGATION_PRIVATE_DIR = DEFAULT_PRIVATE_DIR / "full_investigation"
MANIFEST_NAME = "manifest.json"
