# generation/agent.py - the LangGraph agent: one model node and one tool node in a loop
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition
import config
from generation import prompts
from generation.tools import all_tools

# the chat model with all five tools attached - it decides which tool to call and when
model = ChatOpenAI(model=config.LLM_MODEL, api_key=config.OPENAI_API_KEY,
                   base_url=config.OPENAI_BASE_URL, temperature=0, streaming=True)
model_with_tools = model.bind_tools(all_tools)

# what this function does: one thinking step - the model reads the chat and answers or calls a tool
def call_model(state):
  messages = state["messages"]
  # keep everything from the newest question onward, plus the last few older messages
  question_positions = [position for position, message in enumerate(messages)
                        if isinstance(message, HumanMessage)]
  current_turn_start = question_positions[-1] if question_positions else 0
  older_history = messages[:current_turn_start][-config.MEMORY_MESSAGES:]
  # a tool result cannot be the first message the model sees - drop any left dangling in front
  while older_history and isinstance(older_history[0], ToolMessage):
    older_history = older_history[1:]
  system_message = SystemMessage(content=prompts.build_system_prompt())
  answer = model_with_tools.invoke([system_message] + older_history + messages[current_turn_start:])
  return {"messages": [answer]}

# the graph: start -> agent -> (tools -> agent again) or finish
graph = StateGraph(MessagesState)
graph.add_node("agent", call_model)
graph.add_node("tools", ToolNode(all_tools))
graph.add_edge(START, "agent")
graph.add_conditional_edges("agent", tools_condition)
graph.add_edge("tools", "agent")

# the runnable app with memory - each conversation id keeps its own message history
application = graph.compile(checkpointer=MemorySaver())
