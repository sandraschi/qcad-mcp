"""Typed bindings for ezdxf names pyright stubs cannot see.

ezdxf 1.4 exposes ``readfile``, ``new``, ``__version__`` and the
``addons.drawing`` / ``addons`` helpers through module-level ``__getattr__``
lazy loading. They exist at runtime (the test-suite proves it) but the
shipped stubs do not declare them, so direct ``from ezdxf import readfile``
fails pyright with ``reportPrivateImportUsage``. Import from here instead:
each binding is resolved once via ``getattr`` and typed honestly.
"""

from typing import Any

import ezdxf
import ezdxf.addons
import ezdxf.addons.drawing

readfile: Any = getattr(ezdxf, "readfile")
new: Any = getattr(ezdxf, "new")


def ezdxf_version() -> str:
    """Return the installed ezdxf version string, ``"unknown"`` when absent."""
    return str(getattr(ezdxf, "__version__", "unknown"))


Importer: Any = getattr(ezdxf.addons, "Importer")
Frontend: Any = getattr(ezdxf.addons.drawing, "Frontend")
RenderContext: Any = getattr(ezdxf.addons.drawing, "RenderContext")
