import os
import uuid
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.document_loaders import PyPDFLoader, TextLoader, UnstructuredURLLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Environment safety
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Initialize Core AI Models
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.1)

# --- SAFE LIVE SEARCH INITIALIZATION ---
try:
    from langchain_community.tools import DuckDuckGoSearchRun

    web_search = DuckDuckGoSearchRun()
except Exception:
    web_search = None


# --- Schemas ---
class ChartDataSchema(BaseModel):
    labels: List[str] = Field(description="X-axis categories (months, years, or risk names)")
    values: List[float] = Field(description="Y-axis numerical values")


class DashboardSchema(BaseModel):
    market_summary: str = Field(description="Exactly ONE concise sentence summarizing the market.")
    trend_chart: ChartDataSchema = Field(description="Data for a line chart showing mortgage rate trends over time.")
    risk_chart: ChartDataSchema = Field(
        description="Data for a bar chart showing top 3 market risks and their severity (1-10).")


class StructuredAnswerSchema(BaseModel):
    executive_brief: str = Field(description="ONE sentence maximum direct answer.")
    key_insights: List[str] = Field(description="Exactly 3 extremely short bullet points. No paragraphs.")


def get_vector_store(tenant_id: str):
    return Chroma(
        collection_name=f"tenant_{tenant_id.replace('-', '_')}",
        embedding_function=embeddings,
        persist_directory="./resources/vectorstore"
    )


def ingest_file_bytes(bytes_data: bytes, filename: str, tenant_id: str) -> Dict[str, Any]:
    temp_path = f"temp_{uuid.uuid4()}_{filename}"
    with open(temp_path, "wb") as f:
        f.write(bytes_data)
    loader = PyPDFLoader(temp_path) if filename.endswith(".pdf") else TextLoader(temp_path)
    docs = loader.load_and_split(RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200))
    get_vector_store(tenant_id).add_documents(docs)
    if os.path.exists(temp_path): os.remove(temp_path)
    return {"success": True}


def process_urls(urls: List[str], tenant_id: str) -> Dict[str, Any]:
    loader = UnstructuredURLLoader(urls=urls)
    docs = loader.load_and_split(RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200))
    get_vector_store(tenant_id).add_documents(docs)
    return {"success": True}


def execute_structured_query(query: str, tenant_id: str) -> Dict[str, Any]:
    vector_store = get_vector_store(tenant_id)
    docs = vector_store.as_retriever(search_kwargs={"k": 3}).invoke(query)
    local_context = "\n".join([d.page_content for d in docs])

    # Defensive live web context fetching
    live_context = "Live search package missing or disabled."
    if web_search is not None:
        try:
            live_context = web_search.invoke(f"latest news real estate {query}")
        except Exception:
            live_context = "Live search temporarily rate-limited. Falling back to local data."

    sources = [{"index": i + 1, "source": d.metadata.get("source", "Local Document")} for i, d in enumerate(docs)]
    sources.append({"index": len(sources) + 1, "source": "Live Web Search Context"})

    prompt_text = """You are a strictly data-driven quantitative analyst. NO PARAGRAPHS. Keep answers extremely short.
    Local Database: {context}
    Live Web Data: {live_context}
    User Query: {input}"""

    chain = ChatPromptTemplate.from_messages([("system", prompt_text)]) | llm.with_structured_output(
        StructuredAnswerSchema)
    result = chain.invoke({"context": local_context, "live_context": live_context, "input": query})

    return {"executive_brief": result.executive_brief, "key_insights": result.key_insights, "sources": sources}


def generate_visual_dashboard(tenant_id: str) -> Dict[str, Any]:
    vector_store = get_vector_store(tenant_id)
    docs = vector_store.as_retriever(search_kwargs={"k": 4}).invoke("current market rates and macro risks")
    local_context = "\n".join([d.page_content for d in docs])

    # Defensive live web data fetching for dashboard
    live_context = "Live data unavailable."
    if web_search is not None:
        try:
            live_context = web_search.invoke("current US mortgage rates and housing market risks today")
        except Exception:
            pass

    chain = llm.with_structured_output(DashboardSchema)
    try:
        res = chain.invoke(
            f"Synthesize local data: {local_context} and live data: {live_context} into a dashboard schema.")
        return res.dict()
    except Exception:
        return {
            "market_summary": "Data synthesis required. Ingest documents or complete environment sync to build visualization.",
            "trend_chart": {"labels": ["N/A"], "values": [0]},
            "risk_chart": {"labels": ["N/A"], "values": [0]}
        }