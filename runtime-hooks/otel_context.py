# PyInstaller runtime hook — seed the opentelemetry_context entry point that a frozen
# app cannot discover via importlib.metadata. Without this, opentelemetry.context
# _load_runtime_context() raises StopIteration and fastmcp import crashes.
import sys


def _install_otel_context():
    try:
        from opentelemetry.util._importlib_metadata import entry_points

        class _EP:
            def load(self):
                from opentelemetry.context.contextvars_context import ContextVarsRuntimeContext

                return ContextVarsRuntimeContext

        def _patched_entry_points(group=None, name=None):
            # Return a fresh iterator each call so `next(iter(...))` works.
            if group == "opentelemetry_context" and name in (None, "contextvars_context"):
                return iter([_EP()])
            # Fall back to real behaviour for other groups.
            real = getattr(_patched_entry_points, "_real", None)
            return real(group=group, name=name) if real else iter([])

        _patched_entry_points._real = entry_points
        entry_points = _patched_entry_points
        # Replace the reference used inside opentelemetry.context.__init__
        import opentelemetry.context as ctx

        ctx.entry_points = _patched_entry_points
    except Exception:
        pass


_install_otel_context()
