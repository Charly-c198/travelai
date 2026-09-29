"""路线规划工具"""
from typing import List, Dict, Any, Optional
import math
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()


class RouteOptimizer:
    """路线优化工具"""

    def _haversine(
        self,
        lat1: float, lng1: float,
        lat2: float, lng2: float
    ) -> float:
        """
        计算两点之间的球面距离 (km)
        Args:
            lat1, lng1: 第一个点的经纬度
            lat2, lng2: 第二个点的经纬度
        Returns:
            距离（公里）
        """
        R = 6371  # 地球半径 (km)

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)

        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lng / 2) ** 2)

        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def _calc_route_cost(self, route: List[int], dist_matrix: List[List[float]]) -> float:
        """计算一条路线总距离"""
        total = 0.0
        for i in range(len(route)-1):
            a = route[i]
            b = route[i+1]
            total += dist_matrix[a][b]
        return total

    def _two_opt(self, route: List[int], dist_matrix: List[List[float]]) -> List[int]:
        """2-opt局部搜索优化"""
        best_route = route.copy()
        best_cost = self._calc_route_cost(best_route, dist_matrix)
        n = len(best_route)
        improved = True

        while improved:
            improved = False
            for i in range(1, n - 2):
                for j in range(i + 1, n - 1):
                    # 翻转 i~j 区间路径
                    new_route = best_route[:i] + best_route[i:j+1][::-1] + best_route[j+1:]
                    new_cost = self._calc_route_cost(new_route, dist_matrix)
                    if new_cost < best_cost - 1e-6:
                        best_cost = new_cost
                        best_route = new_route
                        improved = True
                        break
                if improved:
                    break
        return best_route

    async def optimize(
        self,
        spots: List[Dict[str, Any]],
        start_location: Optional[str] = None,
        optimization_goal: str = "time"  # time / distance / balanced
    ) -> Dict[str, Any]:
        """
        优化景点游览路线
        使用最近邻算法进行简单的路径优化，再使用2-opt局部优化
        生产环境可调用高德/百度地图 API
        Args:
            spots: 景点列表，包含 id, lat, lng, duration
            start_location: 起点位置
            optimization_goal: 优化目标 time / distance / balanced
        Returns:
            优化后的路线
        """
        logger.info(f"🗺 优化路线，共 {len(spots)} 个景点，优化目标：{optimization_goal}")

        if len(spots) <= 2:
            return {
                "optimized_order": [s["id"] for s in spots],
                "total_distance_km": 0,
                "estimated_time_minutes": sum(s.get("duration", 120) for s in spots),
                "segments": []
            }

        # 计算距离矩阵
        n = len(spots)
        distance_matrix = [[0.0] * n for _ in range(n)]

        for i in range(n):
            for j in range(n):
                if i != j:
                    distance_matrix[i][j] = self._haversine(
                        spots[i].get("lat", 0),
                        spots[i].get("lng", 0),
                        spots[j].get("lat", 0),
                        spots[j].get("lng", 0)
                    )

        # ===== 最近邻贪心生成初始路线 =====
        visited = [False] * n
        route = []
        current = 0
        visited[current] = True
        route.append(current)

        for _ in range(n - 1):
            nearest = -1
            min_dist = float("inf")
            for j in range(n):
                if not visited[j] and distance_matrix[current][j] < min_dist:
                    nearest = j
                    min_dist = distance_matrix[current][j]
            if nearest != -1:
                route.append(nearest)
                visited[nearest] = True
                current = nearest

        # ===== 2-opt 局部优化 =====
        optimized_route = self._two_opt(route, distance_matrix)

        # 计算总距离和时间
        total_distance = sum(
            distance_matrix[optimized_route[i]][optimized_route[i + 1]]
            for i in range(len(optimized_route) - 1)
        )

        total_time = sum(s.get("duration", 120) for s in spots)
        # 假设平均移动速度 30km/h，加上每段 15 分钟的等待时间
        travel_time = (total_distance / 30) * 60 + (len(optimized_route) - 1) * 15

        return {
            "optimized_order": [spots[i]["id"] for i in optimized_route],
            "total_distance_km": round(total_distance, 2),
            "estimated_time_minutes": int(total_time + travel_time),
            "segments": [
                {
                    "from": spots[optimized_route[i]]["id"],
                    "to": spots[optimized_route[i + 1]]["id"],
                    "distance_km": round(distance_matrix[optimized_route[i]][optimized_route[i + 1]], 2),
                    "estimated_time_min": int((distance_matrix[optimized_route[i]][optimized_route[i + 1]] / 30) * 60)
                }
                for i in range(len(optimized_route) - 1)
            ]
        }


class RouteTool:
    """路线规划工具（LangChain 版本）"""
    name = "plan_route"
    description = """规划旅游路线，计算景点之间的最优顺序和交通方案。
当用户需要了解景点之间的交通方式、预计时间时使用。
输入: 景点列表（通过工具调用获得）"""

    async def run(self, spots_json: str) -> str:
        """执行路线规划"""
        import json

        spots = json.loads(spots_json)

        optimizer = RouteOptimizer()
        result = await optimizer.optimize(spots)

        output = "**🗺 路线规划结果：**\n\n"
        output += f"📍 途经景点: {result['optimized_order']}\n\n"
        output += f"📏 总距离: {result['total_distance_km']} km\n"
        output += f"⏱ 预计时间: {result['estimated_time_minutes']} 分钟\n\n"

        for i, segment in enumerate(result.get("segments", []), 1):
            output += f"{i}. {segment['from']} → {segment['to']}\n"
            output += f"  距离: {segment['distance_km']} km | ⏱ {segment['estimated_time_min']} 分钟\n\n"

        return output
