"""RAG 知识库 Chain"""
import re
from typing import List, Dict, Any, Optional
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# 已知城市清单：用于把用户"合并目的地"（如"丽江大理"）拆成可命中的城市列表
_KNOWN_CITIES = [
    "北京", "上海", "广州", "深圳", "成都", "重庆", "杭州",
    "西安", "丽江", "大理", "昆明", "三亚", "厦门", "南京",
    "苏州", "桂林", "青岛", "武汉", "长沙", "张家界",
]


class RAGChain:
    """RAG 知识库 Chain"""

    def __init__(self):
        self.embeddings = self._create_embeddings()
        self.vectorstore = self._create_vectorstore()

    def _get_embedding_api_key(self) -> Optional[str]:
        """按 LLM_PROVIDER 选择对应提供商的有效 key，避免误用其他提供商的 key"""
        key_map = {
            "openai": settings.OPENAI_API_KEY,
            "deepseek": settings.DEEPSEEK_API_KEY,
            "qwen": settings.QWEN_API_KEY,
        }
        return key_map.get(settings.LLM_PROVIDER) or (
            settings.QWEN_API_KEY or settings.DEEPSEEK_API_KEY or settings.OPENAI_API_KEY
        )

    def _create_embeddings(self) -> OpenAIEmbeddings:
        """创建嵌入模型"""
        api_key = self._get_embedding_api_key()
        return OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            api_key=api_key,
            base_url=self._get_base_url(),
            # DashScope 兼容接口不接受 token id 数组，需发送原始文本
            check_embedding_ctx_length=False,
        )

    def _get_base_url(self) -> Optional[str]:
        """获取 API 基础 URL"""
        if settings.LLM_PROVIDER == "deepseek":
            return settings.DEEPSEEK_BASE_URL
        elif settings.LLM_PROVIDER == "qwen":
            return settings.QWEN_BASE_URL
        return None

    def _build_where(self, filters: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """将简单的过滤 dict 转为 chromadb 1.x 的 where 语法（$and / $eq 嵌套）"""
        if not filters:
            return None
        conditions = []
        for key, value in filters.items():
            if value is not None:
                conditions.append({key: {"$eq": value}})
        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def _create_vectorstore(self) -> Chroma:
        """创建向量存储（使用 PersistentClient）"""
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        client = chromadb.PersistentClient(
            path=settings.VECTOR_STORE_PATH,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        return Chroma(
            client=client,
            collection_name="travel_spots",
            embedding_function=self.embeddings,
        )

    def _city_candidates(self, dest: Optional[str]) -> List[str]:
        """把用户的目的地串拆成已知城市候选列表。

        既支持 "丽江/大理"、"丽江、大理" 等带分隔符的写法，
        也支持 "丽江大理" 这类合并写法（依靠已知城市子串匹配）。
        """
        if not dest:
            return []
        raw = [c.strip() for c in re.split(r"[|,，、和与+。;；\s]+", dest) if c.strip()]
        seen = set(raw)
        for c in _KNOWN_CITIES:
            if c in dest and c not in seen:
                raw.append(c)
                seen.add(c)
        return raw

    async def search_spots(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索景点（鲁棒版）

        检索策略按优先级逐级放宽，避免"严格过滤一空就返回空"：
          1. 具体城市(支持多城市) + 类别
          2. 具体城市
          3. 仅类别
          4. 全文检索（兜底，可能返回泛结果）
        每级内部都会做去重 + 相关性/评分重排。

        Args:
            query: 搜索查询
            top_k: 返回数量
            filters: 过滤条件（city、category 等）

        Returns:
            景点列表
        """
        city = (filters or {}).get("city") if filters else None
        category = (filters or {}).get("category") if filters else None

        base_query = query
        # 若关键句未含城市名，把城市名拼进查询以提升向量命中
        if city and not any(k in query for k in _KNOWN_CITIES):
            base_query = f"{city} {query}".strip()

        # 组装候选过滤策略。
        # 关键设计：一旦明确知道目的地城市，就只按"城市"来检索；库里若没有该城市则返回空，
        # 让上层依赖 LLM 通识兜底，而不是把其他城市的景点塞进来误导生成。
        strategies: List[Optional[Dict[str, Any]]] = []
        cities = self._city_candidates(city) if city else []
        if cities:
            if category:
                strategies.append({"$and": [{"city": {"$in": cities}}, {"category": category}]})
            strategies.append({"city": {"$in": cities}})
        else:
            # 无明确城市时，才允许按类别/全文兜底
            if category:
                strategies.append({"category": category})
            strategies.append({})

        for where in strategies:
            try:
                results = self.vectorstore.similarity_search_with_score(
                    query=base_query,
                    k=top_k,
                    filter=where or None
                )
            except Exception as e:
                logger.warning(f"检索失败(where={where}): {e}")
                continue

            spots = []
            seen = set()
            for doc, score in results:
                key = doc.metadata.get("id") or doc.metadata.get("name")
                if key and key in seen:
                    continue
                if key:
                    seen.add(key)
                spots.append({
                    "id": doc.metadata.get("id"),
                    "name": doc.metadata.get("name"),
                    "name_en": doc.metadata.get("name_en"),
                    "city": doc.metadata.get("city"),
                    "country": doc.metadata.get("country"),
                    "category": doc.metadata.get("category"),
                    "address": doc.metadata.get("address"),
                    "latitude": doc.metadata.get("latitude"),
                    "longitude": doc.metadata.get("longitude"),
                    "rating": doc.metadata.get("rating", 0),
                    "ticket_info": doc.metadata.get("ticket_info"),
                    "description": doc.page_content[:500],
                    "recommend_duration": doc.metadata.get("recommend_duration", 120),
                    "tags": doc.metadata.get("tags", []),
                    "relevance_score": 1 - score,
                })

            if spots:
                # 相关性为主、评分(0-5 归一化)为辅
                spots.sort(
                    key=lambda s: float(s.get("relevance_score") or 0)
                    + 0.3 * max(0.0, min(1.0, float(s.get("rating") or 0) / 5.0)),
                    reverse=True,
                )
                logger.info(f"✅ 找到 {len(spots)} 个相关景点 (where={where})")
                return spots

        logger.info("⚠️ 未找到任何相关景点")
        return []

    async def search_guides(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        搜索旅行攻略

        Args:
            query: 搜索查询
            top_k: 返回数量

        Returns:
            攻略列表
        """
        # 使用攻略专用 collection
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        client = chromadb.PersistentClient(
            path=settings.VECTOR_STORE_PATH,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        guide_store = Chroma(
            client=client,
            collection_name="travel_guides",
            embedding_function=self.embeddings,
        )
        results = guide_store.similarity_search(
            query=query,
            k=top_k
        )
        return [
            {
                "id": doc.metadata.get("id"),
                "title": doc.metadata.get("title"),
                "source": doc.metadata.get("source"),
                "url": doc.metadata.get("url"),
                "content": doc.page_content[:500]
            }
            for doc in results
        ]

    async def add_spots(self, spots: List[Dict[str, Any]], source: str = "seed") -> int:
        """
        添加景点到知识库

        Args:
            spots: 景点列表
            source: 数据来源（seed=人工种子 / learned=LLM 自学习回灌，便于区分与追溯）

        Returns:
            添加数量
        """
        docs = []
        for spot in spots:
            doc = Document(
                page_content=spot.get("description", ""),
                metadata={
                    "id": spot.get("id"),
                    "name": spot.get("name"),
                    "name_en": spot.get("name_en"),
                    "city": spot.get("city"),
                    "country": spot.get("country"),
                    "category": spot.get("category"),
                    "address": spot.get("address"),
                    "latitude": spot.get("latitude"),
                    "longitude": spot.get("longitude"),
                    "rating": spot.get("rating", 0),
                    "ticket_info": str(spot.get("ticket_info", {})),
                    "recommend_duration": spot.get("recommend_duration", 120),
                    "tags": spot.get("tags", []),
                    "type": "spot",
                    "source": source,
                }
            )
            docs.append(doc)

        if docs:
            # 单次嵌入有批次上限（阿里 DashScope 为 10），分批写入避免 400
            BATCH = 8
            for i in range(0, len(docs), BATCH):
                self.vectorstore.add_documents(docs[i:i + BATCH])
            logger.info(f"📥 添加 {len(docs)} 个景点到知识库")
        return len(docs)

    async def generate_context(
        self,
        destination: str,
        travel_style: str,
        duration: int
    ) -> str:
        """
        生成旅行上下文

        Args:
            destination: 目的地
            travel_style: 旅行风格
            duration: 行程天数

        Returns:
            上下文文本
        """
        from app.llm.client import get_llm_client
        # 搜索相关景点和攻略
        spots = await self.search_spots(
            query=f"{destination} {travel_style} 热门",
            top_k=10
        )
        guides = await self.search_guides(
            query=f"{destination} 攻略 tips",
            top_k=3
        )

        # 构建上下文
        context = f"**{destination} 旅行信息汇总**\n\n"
        if spots:
            context += "### 🏞 热门景点\n"
            for spot in spots:
                context += f"- {spot['name']}（评分：{spot['rating']}）\n"
            context += "\n"
        if guides:
            context += "### 📖 旅行攻略\n"
            for guide in guides:
                context += f"- {guide['title']}\n"
        return context
