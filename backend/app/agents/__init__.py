"""The conversational layer: a LangGraph workflow that turns a question into a structured
intent, runs the deterministic services, and explains the structured result.

The language model (or the mock parser) never calculates: it only fills in an `Intent`,
and phrases an explanation from figures the engine already produced.
"""
