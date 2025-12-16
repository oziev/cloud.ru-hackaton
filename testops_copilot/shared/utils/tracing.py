
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.celery import CeleryInstrumentor
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    trace = None
from shared.utils.logger import api_logger
import os
if OPENTELEMETRY_AVAILABLE:
    resource = Resource.create({
        "service.name": "testops-copilot",
        "service.version": "1.0.0"
    })
    trace.set_tracer_provider(TracerProvider(resource=resource))
    console_exporter = ConsoleSpanExporter()
    trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(console_exporter))
    tracer = trace.get_tracer(__name__)
else:
    tracer = None
def setup_tracing(app=None, celery_app=None):
    if not OPENTELEMETRY_AVAILABLE:
        api_logger.warning("OpenTelemetry not available, tracing disabled")
        return
    try:
        if app:
            FastAPIInstrumentor.instrument_app(app)
            api_logger.info("FastAPI tracing enabled")
        if celery_app:
            CeleryInstrumentor().instrument()
            api_logger.info("Celery tracing enabled")
    except Exception as e:
        api_logger.warning(f"Tracing setup failed (non-critical): {e}")
def get_trace_id() -> str:
    if not OPENTELEMETRY_AVAILABLE or trace is None:
        return ""
    span = trace.get_current_span()
    if span:
        context = span.get_span_context()
        return format(context.trace_id, '032x')
    return ""
def get_span_id() -> str:
    if not OPENTELEMETRY_AVAILABLE or trace is None:
        return ""
    span = trace.get_current_span()
    if span:
        context = span.get_span_context()
        return format(context.span_id, '016x')
    return ""