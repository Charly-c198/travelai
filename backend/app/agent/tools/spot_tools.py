"""景点搜索工具"""
from typing import List, Dict, Any, Optional
from app.rag.chain import RAGChain
import logging

logger = logging.getLogger(__name__)


class SpotSearchTool:
    """景点搜索工具"""

    def __init__(self):
        self.rag = RAGChain()

    async def search(
        self,
        query: str,
        city: Optional[str] = None,
        category: Optional[str] = None,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        搜索景点

        Args:
            query: 搜索关键词
            city: 城市筛选
            category: 类别筛选
            top_k: 返回数量

        Returns:
            景点列表
        """
        # 构建查询
        search_query = query
        if city:
            search_query = f"{city} {query}"

        # RAG 检索
        results = await self.rag.search_spots(
            query=search_query,
            top_k=top_k,
            filters={'city': city, 'category': category} if city or category else None
        )

        return results

    async def get_spot_detail(self, spot_id: str) -> Optional[Dict[str, Any]]:
        """获取景点详情"""
        # 从数据库或缓存获取详情
        from app.services.spot_service import SpotService

        service = SpotService()
        return await service.get_spot_by_id(spot_id)

    async def get_recommendations(
        self,
        city: str,
        style: str = "relaxed",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取景点推荐"""
        style_keywords = {
            "relaxed": "休闲 放松 舒适",
            "adventurous": "刺激 冒险 挑战",
            "cultural": "历史 文化 博物馆",
            "family": "亲子 儿童 家庭",
            "romantic": "浪漫 情侣 约会",
            "foodie": "美食 餐厅 小吃",
            "photography": "风景 拍照 美景"
        }

        keywords = style_keywords.get(style, "")
        query = f"{city} {keywords} 必去"

        return await self.search(query, city=city, top_k=limit)


class SpotTool:
    """景点工具（LangChain Tool）"""

    name = "search_spots"
    description = """搜索热门景点信息。当用户询问某地的景点、必去的地方、推荐游览的地方时使用。
输入: 目的城市和偏好（如：亲子、浪漫、美食等）"""

    async def run(self, city: str, preference: str = "") -> str:
        """执行景点搜索"""
        tool = SpotSearchTool()
        spots = await tool.get_recommendations(
            city=city,
            style=preference,
            limit=10
        )

        if not spots:
            return f"抱歉，没有找到 {city} 相关的景点信息。"

        # 格式化输出
        result = f"**{city} 热门景点推荐：**\n\n"
        for i, spot in enumerate(spots, 1):
            result += f"{i}. **{spot['name']}**\n"
            result += f"📍 {spot.get('address', '地址未知')}\n"
            result += f"⭐ 评分: {spot.get('rating', 'N/A')}\n"
            result += f"⏱ 建议游览: {spot.get('recommend_duration', 120)}分钟\n"
            result += f"🎫 门票: {spot.get('ticket_info', {}).get('price', '免费')}\n\n"

        return result
