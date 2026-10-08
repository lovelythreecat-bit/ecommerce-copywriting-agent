"""Stable, safe exceptions exposed to callers."""


class AgentError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class InputError(AgentError):
    pass


class ConfigurationError(AgentError):
    pass


class ModelServiceError(AgentError):
    pass


class OutputValidationError(AgentError):
    def __init__(self, code: str, message: str, *, problems: list[str] | None = None) -> None:
        self.problems = list(problems) if problems is not None else []
        super().__init__(code, message)
