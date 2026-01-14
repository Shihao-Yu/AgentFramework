"""ContextForge Exception Hierarchy"""


class ContextForgeError(Exception):
    """Base exception for all ContextForge errors."""
    
    def __init__(self, message: str, code: str | None = None):
        self.message = message
        self.code = code or self.__class__.__name__
        super().__init__(message)


class ConfigurationError(ContextForgeError):
    """Invalid or missing configuration."""
    
    def __init__(self, message: str, config_key: str | None = None):
        super().__init__(message)
        self.config_key = config_key


class DatabaseError(ContextForgeError):
    """Database connection or query error."""
    
    def __init__(self, message: str, operation: str | None = None):
        super().__init__(message)
        self.operation = operation


class TenantNotFoundError(ContextForgeError):
    """Requested tenant does not exist."""
    
    def __init__(self, message: str = "Tenant not found", tenant_id: str | None = None):
        super().__init__(message)
        self.tenant_id = tenant_id


class NodeNotFoundError(ContextForgeError):
    """Requested node does not exist."""
    
    def __init__(self, message: str = "Node not found", node_id: str | None = None):
        super().__init__(message)
        self.node_id = node_id


class EdgeNotFoundError(ContextForgeError):
    """Requested edge does not exist."""
    
    def __init__(self, message: str = "Edge not found", edge_id: str | None = None):
        super().__init__(message)
        self.edge_id = edge_id


class EmbeddingError(ContextForgeError):
    """Embedding generation failed."""
    
    def __init__(
        self,
        message: str,
        provider: str | None = None,
        model: str | None = None,
    ):
        super().__init__(message)
        self.provider = provider
        self.model = model


class LLMError(ContextForgeError):
    """LLM generation failed."""
    
    def __init__(
        self,
        message: str,
        provider: str | None = None,
        model: str | None = None,
    ):
        super().__init__(message)
        self.provider = provider
        self.model = model


class AuthenticationError(ContextForgeError):
    """Authentication failed - invalid or missing credentials."""
    pass


class AuthorizationError(ContextForgeError):
    """Authorization failed - user lacks permission."""
    
    def __init__(self, message: str = "Access denied", tenant_id: str | None = None):
        super().__init__(message)
        self.tenant_id = tenant_id


class ValidationError(ContextForgeError):
    """Input validation failed."""
    
    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.field = field
