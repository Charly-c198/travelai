"""天气查询工具"""
from typing import Optional, Dict, Any
from datetime import date, timedelta
import httpx
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)

settings = get_settings()


class WeatherTool:
    """天气查询工具（优先高德 Web服务真实天气，失败/无 key 回退模拟）"""

    async def get_weather(
        self,
        city: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        获取天气预报

        Args:
            city: 城市名称
            start_date: 行程开始日期
            end_date: 行程结束日期

        Returns:
            天气预报信息（city/forecasts/tips/source）
        """
        logger.info(f"🌤 查询 {city} 天气")
        # 有高德 Web 服务 key 时用真实天气；否则返回模拟
        if settings.AMAP_API_KEY:
            return await self._fetch_amap(city, start_date, end_date)
        return self._get_mock_weather(city, start_date, end_date)

    async def _fetch_amap(
        self,
        city: str,
        start_date: Optional[date],
        end_date: Optional[date]
    ) -> Dict[str, Any]:
        """调用高德天气接口（extensions=all 未来预报）。"""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://restapi.amap.com/v3/weather/weatherInfo",
                    params={
                        "city": city,
                        "key": settings.AMAP_API_KEY,
                        "extensions": "all",
                    },
                    timeout=8,
                )
                resp.raise_for_status()
                data = resp.json()
            if data.get("status") != "1" or not data.get("forecasts"):
                logger.warning(f"高德天气返回异常: {data.get('info', data)}")
                return self._get_mock_weather(city, start_date, end_date)
            casts = data["forecasts"][0].get("casts", [])
            return self._build_forecast(city, casts, start_date, end_date)
        except Exception as e:
            logger.warning(f"高德天气调用失败: {e}, 回退模拟数据")
            return self._get_mock_weather(city, start_date, end_date)

    def _build_forecast(self, city, casts: list, start_date, end_date) -> Dict[str, Any]:
        """把高德 casts 映射到前端 schema；行程内超出高德预报窗口的日期用模拟补齐。"""
        wm = {
            "晴": "☀️", "少云": "🌤️", "多云": "⛅", "阴": "☁️",
            "小雨": "🌧️", "中雨": "🌧️", "大雨": "⛈️", "暴雨": "⛈️",
            "雷阵雨": "⛈️", "小雪": "🌨️", "中雪": "🌨️", "大雪": "❄️",
        }
        by_date = {}
        for c in casts:
            d = c.get("date", "")
            if not d:
                continue
            try:
                day = date.fromisoformat(d)
            except ValueError:
                continue
            w = c.get("dayweather") or "晴"
            by_date[day] = {
                "date": d,
                "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][day.weekday()],
                "weather": w,
                "icon": wm.get(w, "🌤️"),
                "temp_high": int(c.get("daytemp") or 0),
                "temp_low": int(c.get("nighttemp") or 0),
                "wind": c.get("daywind") or "",
            }

        base = start_date or date.today()
        num = 7 if not end_date else (end_date - base).days + 1
        num = max(1, min(num, 14))

        mock = None
        forecasts = []
        for i in range(num):
            d = base + timedelta(days=i)
            if d in by_date:
                f = dict(by_date[d])
                f["source"] = "amap"
                forecasts.append(f)
            else:
                # 超出高德窗口（高德免费只给当前到几天后）：用模拟补齐，保证卡片完整
                if mock is None:
                    mock = self._get_mock_weather(city, base, base + timedelta(days=num - 1))
                mc = dict(mock["forecasts"][i])
                mc["source"] = "mock"
                forecasts.append(mc)

        tips = self._generate_weather_tips(forecasts)
        dates = [f["date"] for f in forecasts]
        src = "amap" if any(f.get("source") == "amap" for f in forecasts) else "mock"
        return {"city": city, "forecasts": forecasts, "tips": tips, "source": src, "dates": dates}

    def _get_mock_weather(
        self,
        city: str,
        start_date: Optional[date],
        end_date: Optional[date]
    ) -> Dict[str, Any]:
        """生成模拟天气数据（用于测试）"""
        import random

        # 模拟天气类型
        weather_types = [
            {"type": "晴", "icon": "☀️", "temp_range": (18, 28)},
            {"type": "多云", "icon": "⛅", "temp_range": (16, 25)},
            {"type": "阴", "icon": "☁️", "temp_range": (14, 22)},
            {"type": "小雨", "icon": "🌧️", "temp_range": (15, 23)},
        ]

        forecasts = []

        # 生成未来 7 天的预报
        base_date = start_date or date.today()
        num_days = 7 if not end_date else (end_date - base_date).days + 1

        for i in range(min(num_days, 14)):  # 最多 14 天
            weather = random.choice(weather_types)
            day = base_date + timedelta(days=i)

            forecasts.append({
                "date": day.isoformat(),
                "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][day.weekday()],
                "weather": weather["type"],
                "icon": weather["icon"],
                "temp_high": random.randint(weather["temp_range"][0], weather["temp_range"][1]),
                "temp_low": random.randint(weather["temp_range"][0], weather["temp_range"][1]),
                "wind": f"{random.randint(1, 3)}级",
                "pm25": random.randint(20, 80),
                "source": "mock",
            })

        return {
            "city": city,
            "forecasts": forecasts,
            "tips": self._generate_weather_tips(forecasts),
        }

    def _generate_weather_tips(self, forecasts: list) -> str:
        """根据天气预报生成出行建议"""
        tips = []

        # 检查是否有雨天
        rainy_days = [f for f in forecasts if "雨" in f.get("weather", "")]
        if rainy_days:
            tips.append(f"行程中有 {len(rainy_days)} 天可能有雨，建议携带雨具。")

        # 检查温度
        all_temps = [f["temp_high"] for f in forecasts] + [f["temp_low"] for f in forecasts]
        avg_high = sum(all_temps) / len(all_temps)

        if avg_high > 30:
            tips.append("气温较高，注意防暑防晒，多补充水分。")
        elif avg_high < 15:
            tips.append("气温较低，建议携带外套和保暖衣物。")

        return " ".join(tips) if tips else "天气总体良好，适合出行。"


class WeatherToolLangchain:
    """天气查询工具（LangChain 版本）"""
    name = "get_weather"
    description = """查询城市和日期范围天气预报。当用户询问某地某时间的天气情况，或者需要根据天气安排行程时使用。
输入: 城市名称和日期范围"""

    async def run(self, city: str, start_date: str = "", end_date: str = "") -> str:
        """执行天气查询"""
        from datetime import date

        start = date.fromisoformat(start_date) if start_date else None
        end = date.fromisoformat(end_date) if end_date else None

        tool = WeatherTool()
        weather = await tool.get_weather(city, start, end)

        result = f"**{city} 天气预报：**\n\n"
        for day in weather.get("forecasts", []):
            result += f"📅 {day['date']} {day['weekday']}\n"
            result += f"🌤️ {day['icon']} {day['weather']}\n"
            result += f"🌡️ {day['temp_low']}℃ ~ {day['temp_high']}℃\n\n"

        if weather.get("tips"):
            result += f"💡出行建议：**{weather['tips']}**"

        return result
