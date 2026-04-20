import os
import json
from typing import TypedDict, Annotated
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END

load_dotenv()

llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model="llama-3.3-70b-versatile",
    temperature=0.7
)


@tool(description="Mock web search that returns news headlines based on keywords in the query.")
def mock_searxng_search(query: str) -> str:
    query_lower = query.lower()

    if any(k in query_lower for k in ["crypto", "bitcoin", "ethereum", "web3"]):
        return (
            "HEADLINES: "
            "1. Bitcoin hits new all-time high amid regulatory ETF approvals. "
            "2. Ethereum layer-2 solutions cut transaction fees by 90%. "
            "3. SEC approves first spot crypto ETFs for retail investors."
        )
    elif any(k in query_lower for k in ["ai", "openai", "llm", "model", "gpt"]):
        return (
            "HEADLINES: "
            "1. OpenAI releases GPT-5 with human-level reasoning capabilities. "
            "2. Google DeepMind announces AI that codes better than 95% of engineers. "
            "3. AI startups raise $50B in Q1 2026 amid productivity boom."
        )
    elif any(k in query_lower for k in ["market", "stocks", "fed", "rate", "finance"]):
        return (
            "HEADLINES: "
            "1. Fed signals two rate cuts in 2026 as inflation cools to 2.1%. "
            "2. S&P 500 hits record high on strong earnings season. "
            "3. Hedge funds rotate into tech as bond yields fall."
        )
    elif any(k in query_lower for k in ["privacy", "surveillance", "monopoly", "regulation"]):
        return (
            "HEADLINES: "
            "1. EU fines Meta $1.3B for GDPR violations in data transfers. "
            "2. New surveillance law grants governments access to encrypted messages. "
            "3. Big Tech lobbying spend hits record $500M to block antitrust bills."
        )
    elif any(k in query_lower for k in ["space", "elon", "tesla", "musk"]):
        return (
            "HEADLINES: "
            "1. SpaceX Starship completes first Mars trajectory test successfully. "
            "2. Tesla Robotaxi launches in 10 cities with zero safety incidents. "
            "3. Elon Musk announces plan to put 1 million people on Mars by 2040."
        )
    else:
        return (
            "HEADLINES: "
            "1. Global tech layoffs hit 200,000 in Q1 2026. "
            "2. Climate tech startups attract record venture capital. "
            "3. Remote work becomes permanent at 60% of Fortune 500 companies."
        )


class BotState(TypedDict):
    bot_id:         str
    bot_name:       str
    persona:        str
    search_query:   str
    search_results: str
    post_content:   str
    topic:          str
    final_output:   dict


def node_decide_search(state: BotState) -> BotState:
    print(f"\n[Node 1] Deciding search query for {state['bot_name']}...")

    messages = [
        SystemMessage(content=(
            f"You are {state['bot_name']}. Your persona: {state['persona']}\n\n"
            "Based on your personality, decide ONE specific topic you want to "
            "post about today. Return ONLY a short search query (5-8 words max). "
            "No explanation, just the search query."
        )),
        HumanMessage(content="What do you want to search and post about today?")
    ]

    response = llm.invoke(messages)
    search_query = response.content.strip().strip('"').strip("'")

    print(f"  → Search query: '{search_query}'")

    return {**state, "search_query": search_query}


def node_web_search(state: BotState) -> BotState:
    
    print(f"\n[Node 2] Searching for: '{state['search_query']}'...")

    results = mock_searxng_search.invoke({"query": state["search_query"]})

    print(f"  → Results: {results[:80]}...")

    return {**state, "search_results": results}


# ── Node 3: Draft Post ────────────────────────────────────────
def node_draft_post(state: BotState) -> BotState:
    
    print(f"\n[Node 3] Drafting post for {state['bot_name']}...")

    messages = [
        SystemMessage(content=(
            f"You are {state['bot_name']}. Your persona: {state['persona']}\n\n"
            "You must respond with ONLY a valid JSON object. No markdown, "
            "no explanation, no code blocks. Just raw JSON.\n\n"
            "Format:\n"
            '{"bot_id": "bot_a", "topic": "one word topic", '
            '"post_content": "your opinionated post under 280 chars"}'
        )),
        HumanMessage(content=(
            f"Write an opinionated post based on this news:\n{state['search_results']}\n\n"
            f"Use bot_id: {state['bot_id']}\n"
            "Remember: under 280 characters, very opinionated, in character."
        ))
    ]

    response = llm.invoke(messages)
    raw = response.content.strip()

    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        parsed = json.loads(raw)
        parsed["bot_id"] = state["bot_id"]
        topic = parsed.get("topic", "general")
        post  = parsed.get("post_content", "")
        print(f"  → Topic: {topic}")
        print(f"  → Post ({len(post)} chars): {post}")
        return {**state, "topic": topic, "post_content": post, "final_output": parsed}
    except json.JSONDecodeError:
        print(f"   JSON parse failed, using raw: {raw[:100]}")
        fallback = {
            "bot_id":       state["bot_id"],
            "topic":        "general",
            "post_content": raw[:280]
        }
        return {**state, "final_output": fallback}


# ── Build LangGraph ───────────────────────────────────────────
def build_content_engine():
    graph = StateGraph(BotState)

    # Add nodes
    graph.add_node("decide_search", node_decide_search)
    graph.add_node("web_search",    node_web_search)
    graph.add_node("draft_post",    node_draft_post)

    # Add edges (linear flow)
    graph.set_entry_point("decide_search")
    graph.add_edge("decide_search", "web_search")
    graph.add_edge("web_search",    "draft_post")
    graph.add_edge("draft_post",    END)

    return graph.compile()


def generate_bot_post(bot_id: str, bot_name: str, persona: str) -> dict:
    engine = build_content_engine()

    initial_state = BotState(
        bot_id         = bot_id,
        bot_name       = bot_name,
        persona        = persona,
        search_query   = "",
        search_results = "",
        post_content   = "",
        topic          = "",
        final_output   = {}
    )

    result = engine.invoke(initial_state)
    return result["final_output"]