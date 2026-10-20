"""Validate Ollama envelopes without ever treating reasoning as a final answer."""

import re

from pydantic import BaseModel, ValidationError


class ModelOutputError(ValueError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def without_reasoning(text: str) -> str:
    # Some Qwen templates supply the opening tag in the prompt. In that case
    # Ollama's content can contain a closing tag without an opening tag.
    if re.search(r"</think>", text, flags=re.IGNORECASE):
        text = re.split(r"</think>", text, flags=re.IGNORECASE)[-1]
    if re.search(r"<think>", text, flags=re.IGNORECASE):
        raise ModelOutputError("no_final_answer")
    return text.strip()


def parse_response(data: object, schema: type[BaseModel]) -> BaseModel:
    if not isinstance(data, dict):
        raise ModelOutputError("invalid_envelope")
    if data.get("done_reason") == "length":
        raise ModelOutputError("output_limit")
    message = data.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise ModelOutputError("invalid_envelope")
    # message.thinking is deliberately never read or combined with content.
    content = without_reasoning(message["content"])
    if not content:
        raise ModelOutputError("no_final_answer")
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", content, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        content = fenced[1]
    try:
        return schema.model_validate_json(content)
    except ValidationError as exc:
        raise ModelOutputError("invalid_structure") from exc


def output_schema(model: type[BaseModel]) -> dict:
    """Make the model consider every field instead of skipping optional arguments.

    API callers can still omit Pydantic defaults. For generation, unused optional
    arguments must be explicitly null, so an early closing brace cannot silently
    omit a requested group_by/chart argument. This also mirrors the response
    contract given in the system prompt.
    """
    schema = model.model_json_schema()

    def visit(node):
        if isinstance(node, dict):
            node.pop("default", None)
            if node.get("type") == "object" and "properties" in node:
                node["required"] = list(node["properties"])
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(schema)
    return schema
