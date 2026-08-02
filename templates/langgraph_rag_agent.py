#!/usr/bin/env python3
"""
🧠 AI-HomeLab: Corrective RAG Agent (LangGraph + Qdrant)
=========================================================
Автономний циклічний агент, що реалізує паттерн Corrective RAG (CRAG).

Архітектура:
    Запит → Пошук у Qdrant → Оцінка релевантності → [Переформулювання | Генерація]
                                    ↑__________________________|

Вимоги:
    - Python 3.11+
    - Ollama з моделлю gemma3:4b (або будь-якою іншою)
    - Qdrant (Docker або Qdrant Cloud)
    - Embedding-модель через Ollama (nomic-embed-text)

Встановлення залежностей:
    pip install langgraph langchain-ollama langchain-qdrant qdrant-client pydantic

Запуск:
    1. Запустіть Ollama:   ollama serve
    2. Завантажте моделі:  ollama pull gemma3:4b && ollama pull nomic-embed-text
    3. Запустіть Qdrant:   docker run -p 6333:6333 qdrant/qdrant
    4. Запустіть агента:   python langgraph_rag_agent.py

Автор: AI-HomeLab (https://github.com/weby-homelab/AI-HOMELAB)
Ліцензія: MIT
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Literal

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_qdrant import QdrantVectorStore
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

# =============================================================================
# 📋 Конфігурація (через змінні середовища або значення за замовчуванням)
# =============================================================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentConfig:
    """Конфігурація агента. Всі параметри можна перевизначити через ENV."""

    # --- LLM ---
    llm_model: str = field(default_factory=lambda: os.getenv("AGENT_LLM_MODEL", "gemma3:4b"))
    llm_temperature: float = field(
        default_factory=lambda: float(os.getenv("AGENT_LLM_TEMPERATURE", "0.1"))
    )
    llm_base_url: str = field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )

    # --- Embedding ---
    embedding_model: str = field(
        default_factory=lambda: os.getenv("AGENT_EMBEDDING_MODEL", "nomic-embed-text")
    )
    embedding_dimensions: int = field(
        default_factory=lambda: int(os.getenv("AGENT_EMBEDDING_DIM", "768"))
    )

    # --- Qdrant ---
    qdrant_url: str = field(
        default_factory=lambda: os.getenv("QDRANT_URL", "http://localhost:6333")
    )
    qdrant_collection: str = field(
        default_factory=lambda: os.getenv("QDRANT_COLLECTION", "ai_homelab_docs")
    )

    # --- Agent Behavior ---
    relevance_threshold: float = field(
        default_factory=lambda: float(os.getenv("AGENT_RELEVANCE_THRESHOLD", "0.6"))
    )
    max_rewrite_attempts: int = field(
        default_factory=lambda: int(os.getenv("AGENT_MAX_REWRITES", "2"))
    )
    top_k_results: int = field(default_factory=lambda: int(os.getenv("AGENT_TOP_K", "4")))


# =============================================================================
# 📦 Стан графу (State) — Pydantic-модель для type-safe передачі даних
# =============================================================================


class RelevanceGrade(BaseModel):
    """Оцінка релевантності документа до запиту."""

    score: Literal["relevant", "irrelevant"] = Field(
        description="Чи є документ релевантним до запиту: 'relevant' або 'irrelevant'"
    )
    reasoning: str = Field(default="", description="Коротке пояснення оцінки")


class AgentState(BaseModel):
    """
    Стан циклічного агента.

    Кожен вузол графу читає та оновлює цей стан,
    забезпечуючи прозорий потік даних.
    """

    # Вхідні дані
    question: str = Field(description="Оригінальний запит користувача")

    # Робочі дані
    rewritten_question: str = Field(default="", description="Переформульований запит")
    documents: list[Document] = Field(default_factory=list, description="Знайдені документи")
    relevant_documents: list[Document] = Field(
        default_factory=list, description="Документи, що пройшли фільтрацію"
    )

    # Лічильники
    rewrite_count: int = Field(default=0, description="Кількість спроб переформулювання")

    # Результат
    generation: str = Field(default="", description="Фінальна відповідь агента")


# =============================================================================
# 🏗️ Побудова компонентів (Ін'єкція залежностей)
# =============================================================================


def build_llm(config: AgentConfig) -> ChatOllama:
    """Створити LLM-клієнт для Ollama."""
    return ChatOllama(
        model=config.llm_model,
        temperature=config.llm_temperature,
        base_url=config.llm_base_url,
        # Обмеження для малих моделей — стабільніший JSON
        num_predict=1024,
    )


def build_embeddings(config: AgentConfig) -> OllamaEmbeddings:
    """Створити embedding-модель через Ollama."""
    return OllamaEmbeddings(
        model=config.embedding_model,
        base_url=config.llm_base_url,
    )


def build_vector_store(config: AgentConfig) -> QdrantVectorStore:
    """
    Створити підключення до Qdrant.

    Автоматично створює колекцію, якщо її немає.
    """
    client = QdrantClient(url=config.qdrant_url)

    # Створити колекцію, якщо не існує
    collections = [c.name for c in client.get_collections().collections]
    if config.qdrant_collection not in collections:
        logger.info("📦 Створюю колекцію '%s' у Qdrant...", config.qdrant_collection)
        client.create_collection(
            collection_name=config.qdrant_collection,
            vectors_config=VectorParams(
                size=config.embedding_dimensions,
                distance=Distance.COSINE,
            ),
        )

    embeddings = build_embeddings(config)

    return QdrantVectorStore(
        client=client,
        collection_name=config.qdrant_collection,
        embedding=embeddings,
    )


# =============================================================================
# 🔗 Промпти (українською для кращого розуміння контексту)
# =============================================================================

GRADING_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You are a document relevance grader for a Ukrainian AI knowledge base. "
                "Evaluate if the document is relevant to the user's question. "
                'Respond with ONLY a JSON object: {{"score": "relevant"}} or {{"score": "irrelevant"}}. '
                "A document is relevant if it contains information that can help answer the question, "
                "even partially."
            ),
        ),
        ("human", "Document:\n{document}\n\nQuestion: {question}"),
    ]
)

REWRITE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You are a query rewriter for a Ukrainian AI knowledge base. "
                "Rephrase the user's question to improve retrieval from a vector database. "
                "Keep the semantic meaning but use different keywords and phrasing. "
                "Respond with ONLY the rewritten question, nothing else."
            ),
        ),
        (
            "human",
            (
                "Original question: {question}\n\n"
                "This question returned no relevant results. "
                "Rewrite it to improve search quality."
            ),
        ),
    ]
)

GENERATION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You are a helpful AI assistant for the AI-HomeLab project — "
                "a Ukrainian initiative for building local AI laboratories. "
                "Answer the user's question using ONLY the provided context. "
                "If the context is insufficient, clearly state what information is missing. "
                "Respond in the same language as the question (Ukrainian or English)."
            ),
        ),
        ("human", "Context:\n{context}\n\n---\nQuestion: {question}"),
    ]
)


# =============================================================================
# ⚙️ Вузли графу (Graph Nodes)
# =============================================================================


def retrieve_node(state: AgentState, config: AgentConfig, vector_store: QdrantVectorStore) -> dict:
    """
    🔍 Вузол RETRIEVE — пошук документів у Qdrant.

    Використовує переформульований запит, якщо він є,
    інакше — оригінальний.
    """
    query = state.rewritten_question or state.question
    logger.info("🔍 Пошук: '%s' (top_k=%d)", query, config.top_k_results)

    documents = vector_store.similarity_search(query, k=config.top_k_results)
    logger.info("📄 Знайдено %d документів", len(documents))

    return {"documents": documents, "relevant_documents": []}


def grade_documents_node(state: AgentState, config: AgentConfig, llm: ChatOllama) -> dict:
    """
    📊 Вузол GRADE — оцінка релевантності кожного документа.

    Малі моделі (3B-9B) можуть нестабільно генерувати JSON,
    тому використовуємо fallback-логіку з текстовим парсингом.
    """
    relevant_docs = []

    grading_chain = GRADING_PROMPT | llm | StrOutputParser()

    for i, doc in enumerate(state.documents):
        try:
            result = grading_chain.invoke(
                {
                    "document": doc.page_content[:500],  # Обмежуємо контекст для малих моделей
                    "question": state.rewritten_question or state.question,
                }
            )

            # Парсинг відповіді (з fallback для малих моделей)
            result_lower = result.lower().strip()
            is_relevant = "relevant" in result_lower and "irrelevant" not in result_lower

            if is_relevant:
                relevant_docs.append(doc)
                logger.info("  ✅ Документ %d: РЕЛЕВАНТНИЙ", i + 1)
            else:
                logger.info("  ❌ Документ %d: НЕРЕЛЕВАНТНИЙ", i + 1)

        except Exception as e:
            logger.warning("  ⚠️ Помилка оцінки документа %d: %s — пропускаю", i + 1, e)
            continue

    logger.info(
        "📊 Результат: %d/%d документів релевантні",
        len(relevant_docs),
        len(state.documents),
    )

    return {"relevant_documents": relevant_docs}


def decide_node(
    state: AgentState, config: AgentConfig
) -> Literal["generate", "rewrite", "no_answer"]:
    """
    🔀 Вузол DECIDE — умовне розгалуження.

    Логіка:
    1. Є релевантні документи → генеруємо відповідь
    2. Немає релевантних, але є спроби → переформулюємо
    3. Вичерпані спроби → відповідь "не знайдено"
    """
    if state.relevant_documents:
        logger.info(
            "➡️ Рішення: ГЕНЕРУВАТИ (знайдено %d релевантних)",
            len(state.relevant_documents),
        )
        return "generate"

    if state.rewrite_count < config.max_rewrite_attempts:
        logger.info(
            "➡️ Рішення: ПЕРЕФОРМУЛЮВАТИ (спроба %d/%d)",
            state.rewrite_count + 1,
            config.max_rewrite_attempts,
        )
        return "rewrite"

    logger.info("➡️ Рішення: ВІДПОВІДЬ НЕ ЗНАЙДЕНО (вичерпано спроби)")
    return "no_answer"


def rewrite_node(state: AgentState, llm: ChatOllama) -> dict:
    """
    ✏️ Вузол REWRITE — переформулювання запиту.

    Просить LLM створити альтернативне формулювання
    для покращення пошуку у векторній БД.
    """
    rewrite_chain = REWRITE_PROMPT | llm | StrOutputParser()

    original = state.rewritten_question or state.question
    rewritten = rewrite_chain.invoke({"question": original})
    rewritten = rewritten.strip().strip('"').strip("'")

    logger.info("✏️ Переформульовано: '%s' → '%s'", original, rewritten)

    return {
        "rewritten_question": rewritten,
        "rewrite_count": state.rewrite_count + 1,
    }


def generate_node(state: AgentState, llm: ChatOllama) -> dict:
    """
    💬 Вузол GENERATE — генерація фінальної відповіді.

    Формує контекст з релевантних документів
    та передає його LLM разом із запитом.
    """
    context = "\n\n---\n\n".join(doc.page_content for doc in state.relevant_documents)

    generation_chain = GENERATION_PROMPT | llm | StrOutputParser()

    question = state.rewritten_question or state.question
    answer = generation_chain.invoke(
        {
            "context": context,
            "question": question,
        }
    )

    logger.info("💬 Відповідь згенерована (%d символів)", len(answer))

    return {"generation": answer}


def no_answer_node(state: AgentState) -> dict:
    """
    🤷 Вузол NO_ANSWER — коли не знайдено релевантної інформації.
    """
    question = state.rewritten_question or state.question
    return {
        "generation": (
            f"На жаль, у базі знань AI-HomeLab не знайдено релевантної інформації "
            f"для відповіді на запит: «{question}».\n\n"
            f"💡 Спробуйте:\n"
            f"  1. Переформулювати запит іншими словами\n"
            f"  2. Перевірити, чи є потрібні документи у колекції Qdrant\n"
            f"  3. Додати документи через метод ingest_documents()"
        )
    }


# =============================================================================
# 🏗️ Збірка графу (Graph Assembly)
# =============================================================================


def build_graph(config: AgentConfig | None = None) -> StateGraph:
    """
    Збирає та компілює граф Corrective RAG агента.

    Архітектура:
    ┌─────────────┐     ┌────────────┐     ┌─────────┐
    │  retrieve    │────▶│   grade    │────▶│ decide  │
    └─────────────┘     └────────────┘     └────┬────┘
                                                │
                          ┌─────────────────────┼──────────────┐
                          ▼                     ▼              ▼
                    ┌───────────┐        ┌──────────┐   ┌────────────┐
                    │ generate  │        │ rewrite  │   │ no_answer  │
                    └─────┬─────┘        └────┬─────┘   └──────┬─────┘
                          ▼                   │                ▼
                        [END]                 └──▶ retrieve   [END]
    """
    if config is None:
        config = AgentConfig()

    llm = build_llm(config)
    vector_store = build_vector_store(config)

    # --- Визначення графу ---
    workflow = StateGraph(AgentState)

    # Вузли (з замиканням конфігурації)
    workflow.add_node("retrieve", lambda s: retrieve_node(s, config, vector_store))
    workflow.add_node("grade", lambda s: grade_documents_node(s, config, llm))
    workflow.add_node("decide_passthrough", lambda s: s)  # Прохідний вузол для розгалуження
    workflow.add_node("rewrite", lambda s: rewrite_node(s, llm))
    workflow.add_node("generate", lambda s: generate_node(s, llm))
    workflow.add_node("no_answer", lambda s: no_answer_node(s))

    # Ребра
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "grade")
    workflow.add_edge("grade", "decide_passthrough")

    # Умовне розгалуження
    workflow.add_conditional_edges(
        "decide_passthrough",
        lambda s: decide_node(s, config),
        {
            "generate": "generate",
            "rewrite": "rewrite",
            "no_answer": "no_answer",
        },
    )

    # Цикл: rewrite → retrieve (повторний пошук)
    workflow.add_edge("rewrite", "retrieve")

    # Фінальні вузли
    workflow.add_edge("generate", END)
    workflow.add_edge("no_answer", END)

    return workflow.compile()


# =============================================================================
# 📥 Утиліта завантаження документів (Ingestion)
# =============================================================================


def ingest_documents(
    documents: list[Document],
    config: AgentConfig | None = None,
) -> int:
    """
    Завантажити документи у Qdrant.

    Args:
        documents: Список LangChain Document об'єктів.
        config: Конфігурація агента (або за замовчуванням).

    Returns:
        Кількість завантажених документів.

    Приклад:
        >>> from langchain_community.document_loaders import TextLoader
        >>> from langchain_text_splitters import RecursiveCharacterTextSplitter
        >>> loader = TextLoader("my_docs.txt")
        >>> splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        >>> docs = splitter.split_documents(loader.load())
        >>> count = ingest_documents(docs)
        >>> print(f"Завантажено {count} чанків")
    """
    if config is None:
        config = AgentConfig()

    vector_store = build_vector_store(config)
    vector_store.add_documents(documents)

    logger.info("📥 Завантажено %d документів у '%s'", len(documents), config.qdrant_collection)
    return len(documents)


# =============================================================================
# 🚀 Точка входу (Demo)
# =============================================================================


def main() -> None:
    """
    Демонстрація роботи CRAG-агента.

    Завантажує тестові документи про AI-HomeLab та виконує запит.
    """
    config = AgentConfig()

    # --- Тестові документи ---
    demo_docs = [
        Document(
            page_content=(
                "Ollama — це інструмент для локального запуску великих мовних моделей. "
                "Встановлення: curl -fsSL https://ollama.com/install.sh | sh. "
                "Підтримує NVIDIA GPU, AMD та Apple Silicon. "
                "Найпопулярніші моделі: Gemma 4, LLaMA 4, Phi-4, Mistral."
            ),
            metadata={"source": "ai-homelab-docs", "topic": "ollama"},
        ),
        Document(
            page_content=(
                "Квантизація Q4_K_M — золотий стандарт для домашніх лабораторій. "
                "Зменшує розмір моделі до 25% від FP16 з мінімальною втратою якості. "
                "RTX 3060 12GB може запустити Phi-4 14B або Gemma 4 12B у Q4_K_M. "
                "Для Apple Silicon використовуйте MLX backend для +20-90% швидкості."
            ),
            metadata={"source": "ai-homelab-docs", "topic": "quantization"},
        ),
        Document(
            page_content=(
                "Стійкість до відключень (енергоавтономність) — ключова вимога для українських лабораторій. "
                "Apple Silicon споживає 15-40W під навантаженням (RTX 3060 — 170W). "
                "EcoFlow Delta 2 (1024Wh) забезпечить 25-46 годин роботи MacBook. "
                "GPU power limit: nvidia-smi -pl 100 знижує TDP з 170W до 100W."
            ),
            metadata={"source": "ai-homelab-docs", "topic": "blackout"},
        ),
        Document(
            page_content=(
                "LangGraph — це фреймворк для створення циклічних графових агентів. "
                "На відміну від лінійних ланцюжків LangChain, LangGraph дозволяє "
                "створювати агентів з циклами, умовними переходами та збереженням стану. "
                "Ідеально підходить для Corrective RAG, мультиагентних систем та "
                "складних workflow з human-in-the-loop."
            ),
            metadata={"source": "ai-homelab-docs", "topic": "langgraph"},
        ),
        Document(
            page_content=(
                "Безпека домашньої AI-лабораторії включає ізоляцію від IoT-мережі, "
                "використання VLAN для AI-серверів, блокування вихідних з'єднань LLM "
                "через nftables, та моніторинг витоку секретів через Gitleaks. "
                "Docker-контейнери мають запускатися з мінімальними привілеями."
            ),
            metadata={"source": "ai-homelab-docs", "topic": "security"},
        ),
    ]

    # --- Завантажуємо документи ---
    logger.info("📥 Завантажуємо демо-документи у Qdrant...")
    ingest_documents(demo_docs, config)

    # --- Запускаємо агента ---
    graph = build_graph(config)

    demo_questions = [
        "Як встановити Ollama та яку модель обрати для RTX 3060?",
        "Що таке квантизація Q4_K_M і чому вона важлива?",
        "Як забезпечити роботу лаби під час блекауту?",
    ]

    for question in demo_questions:
        logger.info("\n" + "=" * 70)
        logger.info("❓ Запит: %s", question)
        logger.info("=" * 70)

        result = graph.invoke({"question": question})
        print(f"\n📝 Відповідь:\n{result['generation']}\n")


if __name__ == "__main__":
    main()
