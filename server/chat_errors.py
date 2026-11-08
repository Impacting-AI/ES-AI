import logging
from uuid import uuid4


def chat_error(operation, exc):
    reference = uuid4().hex[:12]
    # Log the exception location and type without chat text, SQL values or credentials.
    trace = exc.__traceback__
    while trace and trace.tb_next:
        trace = trace.tb_next
    location = ""
    if trace:
        location = f"{trace.tb_frame.f_code.co_name}:{trace.tb_lineno}"
    logging.getLogger(__name__).error("Chat error %s operation=%s exception=%s location=%s sqlstate=%s",
        reference, operation, type(exc).__name__, location, getattr(exc, "sqlstate", None))
    return f"Chat could not complete the request. Check the app logs for reference {reference}."
