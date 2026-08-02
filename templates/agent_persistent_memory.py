#!/usr/bin/env python3
"""
🧠 AI-HomeLab: Agent Persistent Memory (SQLite + Optional Ollama Embeddings)
=========================================================================
Компонент довготривалої сесійної пам'яті для автономних ШІ-агентів.
Натхненний проектом AgentMemory (https://github.com/rohitg00/agentmemory).

Цей модуль демонструє, як надати локальному ШІ-агенту можливість:
  1. Зберігати факти, рішення та преференції користувача між запусками.
  2. Робити семантичний пошук спогадів (через Ollama nomic-embed-text).
  3. Використовувати резервний текстовий пошук (якщо Ollama офлайн).
  4. Видаляти застарілу інформацію або оновлювати існуючу.

Вимоги:
    - Python 3.10+
    - pydantic >= 2.0
    - requests (для взаємодії з Ollama)

Запуск:
    python templates/agent_persistent_memory.py

Автор: AI-HomeLab (https://github.com/weby-homelab/AI-HOMELAB)
Ліцензія: MIT
"""

import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# Налаштування логування
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AgentMemory")

# =============================================================================
# 📦 Моделі Даних (Type-Safe Models)
# =============================================================================


class MemoryItem(BaseModel):
    """Одиничний спогад агента."""

    id: int | None = Field(None, description="Унікальний ідентифікатор спогаду в БД")
    category: str = Field(..., description="Категорія (напр., 'user_pref', 'codebase', 'decision')")
    content: str = Field(..., description="Текстовий зміст спогаду")
    importance: int = Field(default=5, ge=1, le=10, description="Важливість спогаду від 1 до 10")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="ISO мітка часу створення",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Додаткові метадані")
    embedding: list[float] | None = Field(
        None, description="Векторне представлення (якщо увімкнено)"
    )


# =============================================================================
# 💾 Двигун Пам'яті (SQLite Store)
# =============================================================================


class AgentMemoryStore:
    """Клас для збереження та пошуку спогадів агента."""

    def __init__(
        self,
        db_path: str = "agent_memory.db",
        ollama_url: str = "http://localhost:11434",
    ):
        self.db_path = db_path
        self.ollama_url = ollama_url
        self.embeddings_enabled = False
        self._init_db()
        self._check_ollama()

    def _init_db(self):
        """Ініціалізація SQLite таблиці для збереження спогадів."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    importance INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    embedding TEXT
                )
            """)
            # Створення індексу для швидкого пошуку за категоріями
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_category ON memories (category)")
            conn.commit()

    def _check_ollama(self):
        """Перевірка доступності локальної Ollama для генерації ембедінгів."""
        import requests

        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
            if response.status_code == 200:
                self.embeddings_enabled = True
                logger.info("Local Ollama detected. Vector embeddings search enabled.")
            else:
                logger.warning(
                    "Ollama returned status %s. Fallback to text search.",
                    response.status_code,
                )
        except Exception:
            logger.warning(
                "Local Ollama not detected at %s. Vector embeddings disabled. Using keyword search fallback.",
                self.ollama_url,
            )

    def _get_embedding(self, text: str) -> list[float] | None:
        """Отримання вектора через Ollama nomic-embed-text."""
        if not self.embeddings_enabled:
            return None
        import requests

        try:
            payload = {"model": "nomic-embed-text", "prompt": text}
            response = requests.post(f"{self.ollama_url}/api/embeddings", json=payload, timeout=3)
            if response.status_code == 200:
                return response.json().get("embedding")
        except Exception as e:
            logger.debug("Failed to fetch embedding from Ollama: %s", e)
        return None

    def add_memory(
        self,
        category: str,
        content: str,
        importance: int = 5,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryItem:
        """Додавання нового спогаду."""
        meta = metadata or {}
        embedding = self._get_embedding(content)
        embedding_str = json.dumps(embedding) if embedding else None

        item = MemoryItem(
            category=category,
            content=content,
            importance=importance,
            metadata=meta,
            embedding=embedding,
        )

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO memories (category, content, importance, timestamp, metadata, embedding)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    item.category,
                    item.content,
                    item.importance,
                    item.timestamp,
                    json.dumps(item.metadata),
                    embedding_str,
                ),
            )
            item.id = cursor.lastrowid
            conn.commit()

        logger.info(
            "Added memory ID %s [%s]: '%s'",
            item.id,
            item.category,
            item.content[:40] + "...",
        )
        return item

    def get_all_memories(self, category: str | None = None) -> list[MemoryItem]:
        """Отримання всіх спогадів (опціонально фільтрованих за категорією)."""
        query = (
            "SELECT id, category, content, importance, timestamp, metadata, embedding FROM memories"
        )
        params = []
        if category:
            query += " WHERE category = ?"
            params.append(category)

        memories = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            for row in rows:
                embedding = json.loads(row["embedding"]) if row["embedding"] else None
                memories.append(
                    MemoryItem(
                        id=row["id"],
                        category=row["category"],
                        content=row["content"],
                        importance=row["importance"],
                        timestamp=row["timestamp"],
                        metadata=json.loads(row["metadata"]),
                        embedding=embedding,
                    )
                )
        return memories

    def delete_memory(self, memory_id: int) -> bool:
        """Видалення спогаду за ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
        if deleted:
            logger.info("Deleted memory ID %s", memory_id)
        return deleted

    def update_memory(self, memory_id: int, content: str, importance: int | None = None) -> bool:
        """Оновлення текстового змісту та вектора існуючого спогаду."""
        embedding = self._get_embedding(content)
        embedding_str = json.dumps(embedding) if embedding else None

        query = "UPDATE memories SET content = ?, embedding = ?"
        params = [content, embedding_str]

        if importance is not None:
            query += ", importance = ?"
            params.append(importance)

        query += " WHERE id = ?"
        params.append(memory_id)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            updated = cursor.rowcount > 0

        if updated:
            logger.info("Updated memory ID %s with new content", memory_id)
        return updated

    def search_memories(self, query_text: str, limit: int = 3) -> list[tuple[MemoryItem, float]]:
        """
        Пошук релевантних спогадів.
        Якщо доступна Ollama, робить векторне порівняння (Cosine Similarity).
        Інакше робить текстовий пошук по ключовим словам (LIKE-фільтр).
        Повертає список пар (MemoryItem, score).
        """
        query_vector = self._get_embedding(query_text)

        if query_vector and self.embeddings_enabled:
            # Векторний пошук
            all_items = self.get_all_memories()
            scored_items = []
            for item in all_items:
                if item.embedding:
                    # Розрахунок Cosine Similarity
                    dot_product = sum(a * b for a, b in zip(query_vector, item.embedding))
                    norm_a = sum(a * a for a in query_vector) ** 0.5
                    norm_b = sum(b * b for b in item.embedding) ** 0.5
                    similarity = dot_product / (norm_a * norm_b) if norm_a and norm_b else 0.0
                    scored_items.append((item, similarity))

            # Сортування за схожістю спадаюче
            scored_items.sort(key=lambda x: x[1], reverse=True)
            return scored_items[:limit]
        else:
            # Резервний пошук слів в Python для гнучкості та надійності
            words = [w.lower().strip("?,.!") for w in query_text.split() if len(w) > 2]
            if not words:
                words = [query_text.lower().strip("?,.!")]

            all_memories = self.get_all_memories()
            results = []
            for item in all_memories:
                content_lower = item.content.lower()
                matches = 0
                for word in words:
                    if word in content_lower:
                        matches += 1
                if matches > 0:
                    # Ранг базується на відсотку знайдених слів
                    score = matches / len(words)
                    results.append((item, score))

            # Сортування: спочатку за схожістю (score), потім за важливістю (importance)
            results.sort(key=lambda x: (x[1], x[0].importance), reverse=True)
            return results[:limit]


# =============================================================================
# 🚀 Демонстраційний Запуск (CLI Demo)
# =============================================================================

if __name__ == "__main__":
    print("=====================================================================")
    print("🧠 AI-HomeLab: Тестування та демонстрація Persistent Memory")
    print("=====================================================================")

    # 1. Створення екземпляру бази
    db_name = "test_agent_memory.db"
    # Очистимо старий тестовий файл, якщо є
    if os.path.exists(db_name):
        os.remove(db_name)

    store = AgentMemoryStore(db_path=db_name)

    # 2. Наповнення спогадами
    print("\n📝 Запис первинних спогадів...")
    store.add_memory(
        category="user_pref",
        content="Користувач віддає перевагу темному інтерфейсу (OLED Black або near-black) з палітрою indigo.",
        importance=8,
        metadata={"scope": "ui-settings", "updated_by": "assistant"},
    )
    store.add_memory(
        category="project_fact",
        content="Основна структура репозиторію AI-HomeLab містить папки configs/, templates/, security/ та benchmarks/.",
        importance=9,
        metadata={"scope": "codebase"},
    )
    store.add_memory(
        category="decision",
        content="Ми вирішили використовувати pgvector та Qdrant для виробничих RAG-систем через їх продуктивність у Rust.",
        importance=7,
        metadata={"tech": "databases", "decision_date": "2026-05-31"},
    )
    store.add_memory(
        category="user_pref",
        content="Користувач не любить спам-сповіщення і просить відправляти лише критичні алерти про живлення у Telegram.",
        importance=9,
        metadata={"scope": "notifications"},
    )

    # 3. Виведення списку всіх збережених спогадів
    print("\n📋 Список спогадів в базі даних:")
    all_memories = store.get_all_memories()
    for item in all_memories:
        print(f"  [{item.id}] Category: {item.category} (Importance: {item.importance})")
        print(f"      Content: '{item.content}'")
        print(f"      Metadata: {item.metadata}")
        print("-" * 50)

    # 4. Пошук релевантних спогадів
    query1 = "Який дизайн інтерфейсу подобається користувачу?"
    print(f"\n🔍 Пошук спогадів за запитом: '{query1}'")
    search_results1 = store.search_memories(query1, limit=2)
    for idx, (item, score) in enumerate(search_results1):
        print(f"  {idx + 1}. Score: {score:.3f} | [{item.category}] {item.content}")

    query2 = "Які бази даних використовуються для RAG?"
    print(f"\n🔍 Пошук спогадів за запитом: '{query2}'")
    search_results2 = store.search_memories(query2, limit=2)
    for idx, (item, score) in enumerate(search_results2):
        print(f"  {idx + 1}. Score: {score:.3f} | [{item.category}] {item.content}")

    # 5. Оновлення та видалення
    print("\n🔄 Модифікація пам'яті...")
    if all_memories:
        first_id = all_memories[0].id
        if first_id:
            # Оновлюємо перший спогад
            store.update_memory(
                first_id,
                "Користувач любить темні інтерфейси OLED Black і термінальну верстку Ink.",
                importance=9,
            )

            # Перевіряємо оновлення
            updated = store.get_all_memories(category="user_pref")[0]
            print(
                f"  Оновлений спогад [{updated.id}]: '{updated.content}' (важливість: {updated.importance})"
            )

    # 6. Завершення та прибирання
    if os.path.exists(db_name):
        os.remove(db_name)
    print("\n✅ Тест завершено успішно. Тимчасову тестову БД видалено.")
