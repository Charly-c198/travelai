"""Seed 数据脚本：造示例景点写入向量库(Chroma) + 数据库"""
import asyncio
import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.database import AsyncSessionLocal
from app.models.spot import Spot
from app.rag.chain import RAGChain
from app.config import get_settings
import shutil

settings = get_settings()

# 示例景点数据（北京 / 西安）
SPOTS = [
    {
        "name": "故宫博物院",
        "name_en": "The Forbidden City",
        "city": "北京",
        "country": "中国",
        "category": "cultural",
        "address": "北京市东城区景山前街4号",
        "latitude": 39.9163,
        "longitude": 116.3972,
        "rating": 4.9,
        "ticket_info": {"price": 60, "currency": "CNY"},
        "description": "中国明清两代皇家宫殿，世界上现存规模最大、保存最完整的木质结构古建筑群，中国历史文化的瑰宝。",
        "recommend_duration": 240,
        "tags": ["历史文化", "地标", "博物馆"],
    },
    {
        "name": "长城（八达岭）",
        "name_en": "Great Wall (Badaling)",
        "city": "北京",
        "country": "中国",
        "category": "cultural",
        "address": "北京市延庆区八达岭镇",
        "latitude": 40.3601,
        "longitude": 116.0097,
        "rating": 4.8,
        "ticket_info": {"price": 40, "currency": "CNY"},
        "description": "世界文化遗产，中国古代伟大的军事防御工程，八达岭段是保存最完好、最著名的一段长城。",
        "recommend_duration": 300,
        "tags": ["地标", "户外", "历史"],
    },
    {
        "name": "颐和园",
        "name_en": "Summer Palace",
        "city": "北京",
        "country": "中国",
        "category": "relaxed",
        "address": "北京市海淀区新建宫门路19号",
        "latitude": 39.9978,
        "longitude": 116.2753,
        "rating": 4.7,
        "ticket_info": {"price": 30, "currency": "CNY"},
        "description": "清代皇家园林，中国现存规模最大、保存最完整的皇家园林，湖光山色美不胜收。",
        "recommend_duration": 240,
        "tags": ["园林", "湖泊", "休闲"],
    },
    {
        "name": "兵马俑",
        "name_en": "Terracotta Army",
        "city": "西安",
        "country": "中国",
        "category": "cultural",
        "address": "陕西省西安市临潼区秦陵北路",
        "latitude": 34.3841,
        "longitude": 109.2785,
        "rating": 4.9,
        "ticket_info": {"price": 120, "currency": "CNY"},
        "description": "被誉为世界第八大奇迹，秦始皇陵陪葬坑中出土的陶制军队，规模宏大、栩栩如生。",
        "recommend_duration": 240,
        "tags": ["历史", "世界奇迹", "博物馆"],
    },
    {
        "name": "大雁塔",
        "name_en": "Giant Wild Goose Pagoda",
        "city": "西安",
        "country": "中国",
        "category": "cultural",
        "address": "陕西省西安市雁塔区雁塔路南段",
        "latitude": 34.2185,
        "longitude": 108.9643,
        "rating": 4.6,
        "ticket_info": {"price": 50, "currency": "CNY"},
        "description": "唐代玄奘法师主持修建的佛塔，是西安的标志性建筑，登塔可俯瞰古城全景。",
        "recommend_duration": 120,
        "tags": ["佛教", "地标", "历史文化"],
    },
    {
        "name": "回民街",
        "name_en": "Muslim Quarter",
        "city": "西安",
        "country": "中国",
        "category": "foodie",
        "address": "陕西省西安市莲湖区北院门",
        "latitude": 34.2640,
        "longitude": 108.9397,
        "rating": 4.5,
        "ticket_info": {"price": 0, "currency": "CNY"},
        "description": "西安极具特色的美食街区，汇集众多地道的清真小吃，是体验西安美食文化的必去之地。",
        "recommend_duration": 120,
        "tags": ["美食", "小吃", "夜市"],
    },
    {
        "name": "北京野生动物园",
        "name_en": "Beijing Wildlife Park",
        "city": "北京",
        "country": "中国",
        "category": "family",
        "address": "北京市大兴区榆垡镇",
        "latitude": 39.6900,
        "longitude": 116.3200,
        "rating": 4.6,
        "ticket_info": {"price": 150, "currency": "CNY"},
        "description": "大型野生动物园，可自驾或乘坐小火车近距离观赏散养的野生动物，是亲子家庭出游的热门选择。",
        "recommend_duration": 240,
        "tags": ["亲子", "动物", "家庭"],
    },
    {
        "name": "中国科学技术馆",
        "name_en": "China Science and Technology Museum",
        "city": "北京",
        "country": "中国",
        "category": "family",
        "address": "北京市朝阳区北辰东路5号",
        "latitude": 40.0060,
        "longitude": 116.3930,
        "rating": 4.7,
        "ticket_info": {"price": 30, "currency": "CNY"},
        "description": "中国综合性科技馆，内含大量互动科普展项，适合带孩子们感受科学的魅力。",
        "recommend_duration": 180,
        "tags": ["亲子", "科普", "室内"],
    },
    {
        "name": "北京环球影城",
        "name_en": "Universal Beijing Resort",
        "city": "北京",
        "country": "中国",
        "category": "family",
        "address": "北京市通州区京哈高速东侧",
        "latitude": 39.8400,
        "longitude": 116.6800,
        "rating": 4.8,
        "ticket_info": {"price": 528, "currency": "CNY"},
        "description": "大型主题乐园，涵盖众多电影主题园区和游乐设施，是亲子与年轻人的乐园。",
        "recommend_duration": 480,
        "tags": ["亲子", "主题乐园", "娱乐"],
    },
    {
        "name": "丽江古城",
        "name_en": "Lijiang Ancient Town",
        "city": "丽江",
        "country": "中国",
        "category": "relaxed",
        "address": "云南省丽江市古城区",
        "latitude": 26.8721,
        "longitude": 100.2330,
        "rating": 4.8,
        "ticket_info": {"price": 0, "currency": "CNY"},
        "description": "保存完好的纳西族古城，世界文化遗产，四方街、木府、大水车等，适合悠闲漫步体验慢生活。",
        "recommend_duration": 300,
        "tags": ["休闲", "古城", "慢生活", "世界遗产"],
    },
    {
        "name": "玉龙雪山",
        "name_en": "Jade Dragon Snow Mountain",
        "city": "丽江",
        "country": "中国",
        "category": "relaxed",
        "address": "云南省丽江市玉龙纳西族自治县",
        "latitude": 27.0982,
        "longitude": 100.2139,
        "rating": 4.9,
        "ticket_info": {"price": 100, "currency": "CNY"},
        "description": "纳西族神山，终年积雪，可乘索道至冰川公园，俯瞰雪山与草甸风光。",
        "recommend_duration": 360,
        "tags": ["雪山", "自然", "摄影", "休闲"],
    },
    {
        "name": "束河古镇",
        "name_en": "Shuhe Ancient Town",
        "city": "丽江",
        "country": "中国",
        "category": "cultural",
        "address": "云南省丽江市束河古镇",
        "latitude": 26.8841,
        "longitude": 100.2411,
        "rating": 4.5,
        "ticket_info": {"price": 0, "currency": "CNY"},
        "description": "茶马古道上保存完好的古镇，比大研古城更安静，青石板路与清澈溪流，纳西文化浓郁。",
        "recommend_duration": 240,
        "tags": ["古镇", "文化", "茶马古道"],
    },
    {
        "name": "泸沽湖",
        "name_en": "Lugu Lake",
        "city": "丽江",
        "country": "中国",
        "category": "relaxed",
        "address": "云南省丽江市宁蒗彝族自治县",
        "latitude": 27.7072,
        "longitude": 100.7792,
        "rating": 4.8,
        "ticket_info": {"price": 70, "currency": "CNY"},
        "description": "高原湖泊，摩梭风情，湖光山色如画，适合环湖骑行与划船，宁静惬意。",
        "recommend_duration": 420,
        "tags": ["湖泊", "自然", "摩梭", "度假"],
    },
    {
        "name": "大理古城",
        "name_en": "Dali Ancient Town",
        "city": "大理",
        "country": "中国",
        "category": "cultural",
        "address": "云南省大理市大理古城",
        "latitude": 25.6877,
        "longitude": 100.1587,
        "rating": 4.7,
        "ticket_info": {"price": 0, "currency": "CNY"},
        "description": "苍山洱海间的历史文化名城，城门、洋人街、复兴路，白族风情浓郁。",
        "recommend_duration": 300,
        "tags": ["古城", "文化", "白族", "休闲"],
    },
    {
        "name": "洱海",
        "name_en": "Erhai Lake",
        "city": "大理",
        "country": "中国",
        "category": "relaxed",
        "address": "云南省大理市洱海",
        "latitude": 25.7482,
        "longitude": 100.1982,
        "rating": 4.8,
        "ticket_info": {"price": 0, "currency": "CNY"},
        "description": "高原明珠，环湖骑行或乘船观景，苍山倒影与海鸥相伴，风光旖旎。",
        "recommend_duration": 360,
        "tags": ["湖泊", "骑行", "自然", "度假"],
    },
    {
        "name": "崇圣寺三塔",
        "name_en": "Three Pagodas",
        "city": "大理",
        "country": "中国",
        "category": "cultural",
        "address": "云南省大理市崇圣寺三塔",
        "latitude": 25.7066,
        "longitude": 100.1486,
        "rating": 4.6,
        "ticket_info": {"price": 75, "currency": "CNY"},
        "description": "大理的标志性建筑，千年古塔与苍山洱海相映，历史文化厚重。",
        "recommend_duration": 180,
        "tags": ["古塔", "文化", "摄影"],
    },
    {
        "name": "喜洲古镇",
        "name_en": "Xizhou Ancient Town",
        "city": "大理",
        "country": "中国",
        "category": "foodie",
        "address": "云南省大理市喜洲镇",
        "latitude": 25.8340,
        "longitude": 100.1300,
        "rating": 4.5,
        "ticket_info": {"price": 0, "currency": "CNY"},
        "description": "白族民居建筑群，喜洲粑粑、乳扇等特色美食，田园风光与千年古镇兼具。",
        "recommend_duration": 240,
        "tags": ["美食", "古镇", "白族", "田园"],
    },
]


async def seed_spots():
    """将示例景点写入 Chroma 向量库 + Spot 数据库表"""
    # 清理旧的向量库目录，避免重复 seed 导致数据累积
    vec_path = settings.VECTOR_STORE_PATH
    if os.path.exists(vec_path):
        shutil.rmtree(vec_path)

    rag = RAGChain()

    # 为每个景点分配稳定 ID
    for spot in SPOTS:
        spot["id"] = str(uuid.uuid4())

    print(f"📥 写入 {len(SPOTS)} 个景点到 Chroma 向量库...")
    await rag.add_spots(SPOTS)

    print("💾 写入 Spot 数据库表...")
    async with AsyncSessionLocal() as db:
        for spot in SPOTS:
            db.add(Spot(**{k: v for k, v in spot.items() if k != "id"}))
        await db.commit()

    print("✅ Seed 数据写入完成")


if __name__ == "__main__":
    asyncio.run(seed_spots())