"""Image checks for the full investigation (task ``gb-2019-full-investigation``).

``environment.check_permissions`` imports every ``environment.*_checks`` module during the
image build (``karotte check``) and calls its ``check()``; module names are visited in
sorted order, so this runs after ``environment.incident_checks``. The checks only make
sense inside the container, so ``check()`` returns immediately elsewhere.

The read protections of ``bundles/full_investigation`` and ``private/full_investigation``
are part of ``incident_checks.protected_paths`` (the bash check as the student and every
task's ``run_python`` probe). This module adds increment B's runner checks
(``incident_checks.full_investigation_checks``): the bundle loads and verifies (fail
closed), an episode under the task's tool configuration is driven like the other tasks',
and only obtained evidence is materialised. They live here, not in
``incident_checks.check()``, so that increment A's frozen image checks are unchanged.
"""

from __future__ import annotations

import os


def check() -> None:
    """Container-only image checks for the full investigation (no-op elsewhere)."""
    if "KAROTTE_CONTAINERIZED" not in os.environ:
        return
    from environment import incident_checks

    incident_checks.full_investigation_checks()
