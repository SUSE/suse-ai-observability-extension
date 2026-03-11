# suse_ai_filter.py - Known Pitfalls

## Provider Variable Race Condition (Fixed)

The filter tracks which provider (e.g., "openai", "ollama") is used for each chat via `self.chat_model_provider`.

**Bug pattern**: If the `provider` variable is re-fetched from `chat_model_provider` AFTER the cleanup block (which deletes entries for the chat_id), it will always return the default value "default". The provider must be read BEFORE cleanup.

**Correct order in `outlet()`**:
1. Read `provider` from `self.chat_model_provider`
2. Set span attributes and end span
3. Clean up `self.chat_model_provider` entries for the chat_id
4. Use `provider` for metrics (already captured in step 1)

## OTel Span Attribute Hygiene

Do NOT set these as span attributes (they are not part of OTel GenAI semconv):
- `gen_ai.usage.total_tokens` — not a standard attribute
- `gen_ai.output.type` — not a standard attribute

DO set these:
- `gen_ai.usage.input_tokens` — standard
- `gen_ai.usage.output_tokens` — standard
- `gen_ai.response.finish_reasons` — standard (list)

The `finish_reason` should be included inside the output message object in `gen_ai.output.messages`, not as a separate span attribute.

## Message Formatting

Output messages for `gen_ai.output.messages` should include `finish_reason`:
```python
formatted_output = format_message_for_otel(assistant_message_obj)
formatted_output["finish_reason"] = finish_reason
span.set_attribute(
    SemanticConvention.GEN_AI_OUTPUT_MESSAGES,
    json.dumps([formatted_output])
)
```
