"""
RAG Agent factory — creates domain-filtered LangGraph node functions.

Usage:
    from app.agents.knowledge_agent import make_rag_agent
    my_node = make_rag_agent(role_prompt="...", agent_name="my_agent", domain="admissions")

When domain is provided, retrieval is filtered to chunks tagged with that domain
in ChromaDB (set during ingestion). Pass domain=None to search all sections.
"""

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI  # DeepSeek 走 OpenAI 兼容接口
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from app.rag.retriever import retrieve

load_dotenv()

_BASE_SYSTEM_PROMPT = """\
{role_prompt}

Answer the user's question using ONLY the context provided below.
- Be accurate, concise, and professional.
- If the context contains the answer, provide it clearly.
- If the context does not contain enough information, say so honestly and \
suggest the user visit the official NUS website or contact the admissions \
office at msc-dft-admissions@nus.edu.sg.
- Do NOT invent or assume facts that are not present in the context.

Context:
{context}
"""


def _build_llm() -> ChatOpenAI:
    # 从 Groq 换成 DeepSeek(走 common.config,自动优先 NVIDIA 免费通道、回退 DeepSeek 官方)
    from common import config
    return ChatOpenAI(
        model=config.get_model(),
        api_key=config.get_api_key(),
        base_url=config.get_base_url(),
        temperature=0.2,
        max_tokens=1024,
    )


def make_rag_agent(role_prompt: str, agent_name: str, domain: str = None):
    """
    Returns a LangGraph node function for a domain-specific RAG agent.

    Each returned node:
      1. Extracts the latest user message.
      2. Retrieves top-3 chunks from ChromaDB, filtered by domain if provided.
      3. Injects chunks into a domain-specific system prompt.
      4. Calls Groq LLM and returns the grounded answer.
    """
    def node(state: dict) -> dict:
        last_user_message = ""
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                last_user_message = msg.content
                break

        if not last_user_message:
            fallback = "I couldn't identify your question. Could you please rephrase it?"
            return {
                "messages": [AIMessage(content=fallback)],
                "agent_used": agent_name,
                "reply": fallback,
            }

        chunks = retrieve(last_user_message, top_k=3, domain=domain)
        context = "\n\n---\n\n".join(chunks) if chunks else (
            "No specific programme information is currently available in the "
            "knowledge base. Please contact the admissions office directly."
        )

        system_prompt = _BASE_SYSTEM_PROMPT.format(
            role_prompt=role_prompt,
            context=context,
        )
        messages = [SystemMessage(content=system_prompt)] + list(state["messages"])
        response = _build_llm().invoke(messages)

        return {
            "messages": [response],
            "agent_used": agent_name,
            "reply": response.content,
        }

    node.__name__ = agent_name
    return node
