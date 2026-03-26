"""
Test script for the --dump-failures + replay pipeline.
Uses a real LangChain WikipediaQueryRun tool.
"""
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from toolguard.integrations.langchain import guard_langchain_tool

# Import the REAL LangChain tool and wrap it with ToolGuard
wiki = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
wiki_tool = guard_langchain_tool(wiki)
