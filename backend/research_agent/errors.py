class ResearchError(Exception):
    """Safe base error without provider data or secrets."""


class TaskValidationError(ResearchError):
    pass


class UnsupportedTaskError(ResearchError):
    pass


class ContextLimitError(ResearchError):
    pass
