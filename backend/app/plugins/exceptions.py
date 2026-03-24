from __future__ import annotations


class PluginError(Exception):
    """Base exception for all plugin-related errors."""

    def __init__(self, message: str, plugin_id: str | None = None) -> None:
        self.plugin_id = plugin_id
        super().__init__(message)


class PluginNotFoundError(PluginError):
    """Raised when a requested plugin cannot be found."""
    pass


class PluginSignatureError(PluginError):
    """Raised when plugin bundle signature verification fails."""
    pass


class PluginManifestError(PluginError):
    """Raised when a plugin manifest is invalid or missing."""
    pass


class PluginCompatError(PluginError):
    """Raised when a plugin is incompatible with the current platform version."""
    pass


class PluginConflictError(PluginError):
    """Raised when a plugin conflicts with an already-installed plugin."""
    pass


class PluginImportError(PluginError):
    """Raised when a plugin's Python module cannot be imported."""
    pass


class PluginSetupError(PluginError):
    """Raised when a plugin's setup/activate routine fails."""
    pass


class PluginUpdateError(PluginError):
    """Raised when a plugin update process fails."""
    pass


class PluginPermissionError(PluginError):
    """Raised when a plugin attempts to access a scope it lacks permission for."""

    def __init__(
        self,
        message: str,
        plugin_id: str | None = None,
        scope: str | None = None,
    ) -> None:
        self.scope = scope
        super().__init__(message, plugin_id=plugin_id)
