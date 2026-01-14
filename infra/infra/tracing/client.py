import logging
import os
import random
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from infra.settings.ssl import get_ssl_settings
from infra.tracing.context import TraceContext

if TYPE_CHECKING:
    from infra.auth.context import RequestContext

logger = logging.getLogger(__name__)


class TracingClient:
    def __init__(
        self,
        public_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        host: Optional[str] = None,
        enabled: bool = True,
        sample_rate: float = 1.0,
    ):
        self._public_key = public_key or os.environ.get("LANGFUSE_PUBLIC_KEY", "")
        self._secret_key = secret_key or os.environ.get("LANGFUSE_SECRET_KEY", "")
        self._host = host or os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
        self._enabled = enabled
        self._sample_rate = sample_rate
        self._langfuse = None
        self._http_client = None

        if self._enabled and self._public_key and self._secret_key:
            try:
                from langfuse import Langfuse
            except ImportError:
                logger.warning("langfuse package not installed")
                return

            try:
                import httpx
            except ImportError:
                logger.warning("httpx package not installed")
                return

            try:
                ssl_settings = get_ssl_settings()
                ca_cert = ssl_settings.get_ca_cert()

                self._http_client = httpx.Client(verify=ca_cert)
                self._langfuse = Langfuse(
                    public_key=self._public_key,
                    secret_key=self._secret_key,
                    host=self._host,
                    httpx_client=self._http_client,
                )
                logger.info("Langfuse tracing initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Langfuse: {e}")

    @property
    def enabled(self) -> bool:
        return self._langfuse is not None and self._enabled

    def _should_sample(self) -> bool:
        return random.random() < self._sample_rate

    def start_trace(
        self,
        ctx: "RequestContext",
        name: str,
        agent_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> TraceContext:
        trace_metadata = {
            "user_id": str(ctx.user.user_id),
            "username": ctx.user.username,
            "session_id": ctx.session_id,
            "request_id": ctx.request_id,
            **(metadata or {}),
        }

        trace_ctx = TraceContext.create(
            session_id=ctx.session_id,
            user_id=str(ctx.user.user_id),
            agent_id=agent_id,
            metadata=trace_metadata,
        )

        if self.enabled and self._should_sample():
            try:
                trace = self._langfuse.trace(
                    id=trace_ctx.trace_id,
                    name=name,
                    session_id=ctx.session_id,
                    user_id=str(ctx.user.user_id),
                    metadata=trace_metadata,
                )
                trace_ctx._langfuse = self._langfuse
                trace_ctx._trace = trace
            except Exception as e:
                logger.warning(f"Failed to create Langfuse trace: {e}")

        return trace_ctx

    def end_trace(
        self,
        trace_ctx: TraceContext,
        output: Optional[str] = None,
        level: str = "DEFAULT",
    ) -> None:
        trace_ctx.end()

        if trace_ctx._trace is not None:
            try:
                trace_ctx._trace.update(
                    output=output,
                    level=level,
                    metadata={
                        **trace_ctx.metadata,
                        "summary": trace_ctx.to_summary(),
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to end Langfuse trace: {e}")

        trace_ctx.clear()

    def span(
        self,
        trace_ctx: TraceContext,
        name: str,
        input_data: Optional[Any] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "SpanContextManager":
        return SpanContextManager(
            client=self,
            trace_ctx=trace_ctx,
            name=name,
            input_data=input_data,
            metadata=metadata,
        )

    def generation(
        self,
        trace_ctx: TraceContext,
        name: str,
        model: str,
        input_messages: list[dict[str, Any]],
        model_parameters: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "GenerationContextManager":
        return GenerationContextManager(
            client=self,
            trace_ctx=trace_ctx,
            name=name,
            model=model,
            input_messages=input_messages,
            model_parameters=model_parameters,
            metadata=metadata,
        )

    def log_event(
        self,
        trace_ctx: TraceContext,
        name: str,
        metadata: Optional[dict[str, Any]] = None,
        level: str = "DEFAULT",
    ) -> None:
        if trace_ctx._trace is not None:
            try:
                parent = trace_ctx.current_span or trace_ctx._trace
                parent.event(name=name, metadata=metadata, level=level)
            except Exception as e:
                logger.warning(f"Failed to log event: {e}")

    def flush(self) -> None:
        if self._langfuse is not None:
            try:
                self._langfuse.flush()
            except Exception as e:
                logger.warning(f"Failed to flush Langfuse: {e}")

    def shutdown(self) -> None:
        if self._langfuse is not None:
            try:
                self._langfuse.shutdown()
            except Exception as e:
                logger.warning(f"Failed to shutdown Langfuse: {e}")
        if self._http_client is not None:
            try:
                self._http_client.close()
            except Exception as e:
                logger.warning(f"Failed to close HTTP client: {e}")


class SpanContextManager:
    def __init__(
        self,
        client: TracingClient,
        trace_ctx: TraceContext,
        name: str,
        input_data: Optional[Any] = None,
        metadata: Optional[dict[str, Any]] = None,
    ):
        self._client = client
        self._trace_ctx = trace_ctx
        self._name = name
        self._input_data = input_data
        self._metadata = metadata or {}
        self._span: Optional[Any] = None
        self._output: Optional[Any] = None
        self._level: str = "DEFAULT"
        self._start_time: datetime = datetime.now(timezone.utc)

    def __enter__(self) -> "SpanContextManager":
        if self._trace_ctx._trace is not None:
            try:
                parent = self._trace_ctx.current_span or self._trace_ctx._trace
                self._span = parent.span(
                    name=self._name,
                    input=str(self._input_data) if self._input_data else None,
                    metadata=self._metadata,
                )
                self._trace_ctx.push_span(self._span)
            except Exception as e:
                logger.warning(f"Failed to create span: {e}")
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._span is not None:
            try:
                self._trace_ctx.pop_span()
                level = "ERROR" if exc_type is not None else self._level
                self._span.end(
                    output=str(self._output) if self._output else None,
                    level=level,
                    metadata={
                        **self._metadata,
                        "duration_ms": (datetime.now(timezone.utc) - self._start_time).total_seconds() * 1000,
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to end span: {e}")

    def set_output(self, output: Any) -> None:
        self._output = output

    def set_level(self, level: str) -> None:
        self._level = level

    def add_metadata(self, key: str, value: Any) -> None:
        self._metadata[key] = value


class GenerationContextManager:
    def __init__(
        self,
        client: TracingClient,
        trace_ctx: TraceContext,
        name: str,
        model: str,
        input_messages: list[dict[str, Any]],
        model_parameters: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ):
        self._client = client
        self._trace_ctx = trace_ctx
        self._name = name
        self._model = model
        self._input_messages = input_messages
        self._model_parameters = model_parameters or {}
        self._metadata = metadata or {}
        self._generation: Optional[Any] = None
        self._output: Optional[Any] = None
        self._usage: Optional[dict[str, int]] = None
        self._level: str = "DEFAULT"
        self._start_time: datetime = datetime.now(timezone.utc)

    def __enter__(self) -> "GenerationContextManager":
        if self._trace_ctx._trace is not None:
            try:
                parent = self._trace_ctx.current_span or self._trace_ctx._trace
                self._generation = parent.generation(
                    name=self._name,
                    model=self._model,
                    input=self._input_messages,
                    model_parameters=self._model_parameters,
                    metadata=self._metadata,
                )
            except Exception as e:
                logger.warning(f"Failed to create generation: {e}")
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._generation is not None:
            try:
                level = "ERROR" if exc_type is not None else self._level

                if self._usage:
                    self._trace_ctx.record_inference(
                        input_tokens=self._usage.get("input", 0),
                        output_tokens=self._usage.get("output", 0),
                    )
                else:
                    self._trace_ctx.record_inference()

                self._generation.end(
                    output=self._output,
                    level=level,
                    usage=self._usage,
                    metadata={
                        **self._metadata,
                        "duration_ms": (datetime.now(timezone.utc) - self._start_time).total_seconds() * 1000,
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to end generation: {e}")

    def set_output(self, output: Any, usage: Optional[dict[str, int]] = None) -> None:
        self._output = output
        self._usage = usage

    def set_level(self, level: str) -> None:
        self._level = level
