"""Static style keyword library. No LLM calls — pure local lookup."""
from typing import TypedDict


class StyleKeywords(TypedDict):
    style: str
    positive: list[str]   # 正向关键词，直接拼入图像生成 prompt
    negative: list[str]   # 负向关键词，拼入 negative_prompt
    mood: str             # 一句话氛围描述，供 agent 对话使用
    description: str      # 2-3 句风格说明，供 enhance_prompt LLM 参考


STYLE_LIBRARY: dict[str, StyleKeywords] = {
    "极简主义": {
        "style": "极简主义",
        "positive": [
            "minimalist architecture",
            "clean lines",
            "pure geometry",
            "monolithic form",
            "single material palette",
            "generous negative space",
            "shadow and light contrast",
        ],
        "negative": [
            "ornate decoration",
            "cluttered facade",
            "excessive detail",
            "mixed styles",
        ],
        "mood": "静谧、克制、纯粹，以留白和光影传递空间张力",
        "description": (
            "极简主义建筑以纯粹几何形体和单一材质为核心，摒弃一切装饰性元素，"
            "让结构本身成为美学表达。立面通常由大面积素混凝土、白色抹灰或深色金属板构成，"
            "开窗精准克制，光影随时间变化成为建筑的动态装饰。"
            "空间逻辑强调比例与留白，细节处理精度极高。"
        ),
    },
    "新中式": {
        "style": "新中式",
        "positive": [
            "new Chinese architecture",
            "sloped roof with upturned eaves",
            "wooden lattice screen",
            "grey brick facade",
            "courtyard layout",
            "ink-wash color palette",
            "stone lantern",
            "bamboo grove",
        ],
        "negative": [
            "western classical columns",
            "baroque ornament",
            "bright saturated colors",
        ],
        "mood": "含蓄内敛，融合传统意境与现代空间逻辑，灰白为主调",
        "description": (
            "新中式建筑将中国传统建筑语汇——坡屋顶、格栅、院落、灰砖——"
            "以现代建造技术和空间逻辑重新诠释，而非直接复制历史样式。"
            "色彩以水墨灰白为主调，辅以木色和青石，营造含蓄内敛的东方意境。"
            "院落与廊道是组织空间的核心手法，室内外边界模糊，强调人与自然的渗透关系。"
        ),
    },
    "工业风": {
        "style": "工业风",
        "positive": [
            "industrial architecture",
            "exposed concrete",
            "weathered steel structure",
            "rusted corten steel",
            "raw brick",
            "large factory windows",
            "visible structural beams",
            "matte dark palette",
        ],
        "negative": [
            "polished marble",
            "decorative molding",
            "warm wood cladding",
            "pastel colors",
        ],
        "mood": "粗粝、厚重、诚实，材料本身即装饰",
        "description": (
            "工业风建筑直接暴露结构与材料的原始状态，清水混凝土、耐候钢、裸砖和型钢"
            "不加修饰地呈现在立面上，诚实地表达建造逻辑。"
            "大尺度工厂窗、外露管道和可见结构梁是典型元素，"
            "整体色调偏深沉，以锈色、炭灰、深棕为主，拒绝一切表面装饰。"
        ),
    },
    "现代主义": {
        "style": "现代主义",
        "positive": [
            "modernist architecture",
            "floor-to-ceiling glass curtain wall",
            "cantilevered volume",
            "flat roof",
            "open plan",
            "white render facade",
            "horizontal ribbon windows",
            "pilotis",
        ],
        "negative": [
            "pitched roof",
            "traditional ornament",
            "heavy masonry",
        ],
        "mood": "理性、开放、通透，形式服从功能",
        "description": (
            "现代主义建筑以「形式服从功能」为核心原则，大面积玻璃幕墙引入自然光，"
            "平屋顶和悬挑结构打破传统建筑的厚重感，底层架空柱（pilotis）解放地面。"
            "立面以白色抹灰或玻璃为主，水平带窗强调横向延伸感，"
            "室内外空间通过通透界面形成连续流动的关系。"
        ),
    },
    "北欧风": {
        "style": "北欧风",
        "positive": [
            "Scandinavian architecture",
            "natural timber cladding",
            "white painted wood",
            "large panoramic windows",
            "soft diffused natural light",
            "pitched black metal roof",
            "minimalist Nordic detail",
            "birch forest surroundings",
        ],
        "negative": [
            "ornate facade",
            "tropical vegetation",
            "dark heavy materials",
        ],
        "mood": "温暖、自然、宁静，与北方自然环境融为一体",
        "description": (
            "北欧建筑深度回应高纬度气候，大尺度窗户最大化捕捉漫射自然光，"
            "坡屋顶（通常为深色金属板）有效排雪，木材是最核心的立面与室内材料。"
            "色彩以白色、浅灰和原木色为主，细节简洁克制，"
            "建筑与桦树林、湖泊等北方自然景观形成和谐共生的关系。"
        ),
    },
    "地中海风": {
        "style": "地中海风",
        "positive": [
            "Mediterranean architecture",
            "whitewashed stucco wall",
            "terracotta roof tile",
            "arched openings",
            "blue accent trim",
            "bougainvillea",
            "stone courtyard",
            "warm golden sunlight",
        ],
        "negative": [
            "glass curtain wall",
            "dark industrial material",
            "flat roof",
        ],
        "mood": "热烈、明媚、慵懒，阳光与白墙的永恒对话",
        "description": (
            "地中海建筑以强烈的阳光和海洋气候为背景，白色灰泥墙面反射强光，"
            "陶土瓦坡屋顶、拱券门窗和石材庭院是标志性元素。"
            "蓝色点缀（门窗框、瓷砖）与白墙形成鲜明对比，"
            "三角梅、橄榄树等植物与建筑融为一体，营造慵懒热烈的南欧氛围。"
        ),
    },
    "日式禅意": {
        "style": "日式禅意",
        "positive": [
            "Japanese Zen architecture",
            "karesansui dry garden",
            "natural stone",
            "bamboo screen",
            "low overhanging eaves",
            "shoji screen",
            "moss garden",
            "wabi-sabi texture",
            "subdued earth tones",
        ],
        "negative": [
            "bright colors",
            "ornate decoration",
            "western classical elements",
        ],
        "mood": "侘寂、空寂、物哀，以不完整和无常之美触动人心",
        "description": (
            "日式禅意建筑以「侘寂」美学为核心，接受材料的自然老化与不完整，"
            "枯山水、苔藓庭院和竹林是常见的外部空间元素。"
            "低矮出挑的屋檐制造深邃阴影，障子纸和竹格栅过滤光线，"
            "自然石材、素木和泥土色系构成克制而深沉的材料语言，"
            "空间以「间」（Ma）的概念处理虚实关系，留白与沉默同样重要。"
        ),
    },
    "未来主义": {
        "style": "未来主义",
        "positive": [
            "futurist architecture",
            "parametric curved surface",
            "fluid organic form",
            "metallic sheen facade",
            "dynamic structural skin",
            "LED integrated facade",
            "aerodynamic silhouette",
            "high-tech material",
        ],
        "negative": [
            "traditional roof",
            "brick masonry",
            "historical reference",
            "static rectangular form",
        ],
        "mood": "前卫、动感、科技感，挑战重力与形式的边界",
        "description": (
            "未来主义建筑以参数化设计和数字制造为基础，追求流线型有机曲面和动态结构表皮，"
            "形式不再受传统建造逻辑约束，常呈现出悬浮、扭转或生长的视觉张力。"
            "立面材料以高光金属板、ETFE 膜、复合铝板为主，"
            "夜间 LED 集成照明使建筑成为发光的城市地标，强调科技与未来感。"
        ),
    },
    "建筑竞赛风": {
        "style": "建筑竞赛风",
        "positive": [
            "architectural competition rendering",
            "conceptual diagram aesthetic",
            "dramatic atmospheric perspective",
            "bold conceptual gesture",
            "expressive structural form",
            "cinematic lighting",
            "human scale figures",
            "evocative mood",
            "award-winning composition",
            "poetic spatial narrative",
        ],
        "negative": [
            "generic commercial rendering",
            "flat lighting",
            "photorealistic mundane",
            "lack of concept",
        ],
        "mood": "概念先行，氛围强烈，以一张图讲述一个建筑故事，打动评委",
        "description": (
            "建筑竞赛效果图以传达概念和打动评委为首要目标，而非追求照片级写实。"
            "构图通常选取最能体现设计意图的戏剧性视角，配合电影级光线营造强烈氛围感，"
            "人物剪影和环境元素作为尺度参照，同时强化叙事性。"
            "画面往往带有概念图解的美学气质——轴测爆炸图、分析线条或材料拼贴——"
            "让一张图同时传递空间体验与设计逻辑。"
        ),
    },
}


def get_style(style_name: str) -> StyleKeywords | None:
    """Exact match first, then partial match."""
    if style_name in STYLE_LIBRARY:
        return STYLE_LIBRARY[style_name]
    for key, value in STYLE_LIBRARY.items():
        if style_name in key or key in style_name:
            return value
    return None


def list_styles() -> list[str]:
    return list(STYLE_LIBRARY.keys())


if __name__ == "__main__":
    print("Available styles:", list_styles())
    style = get_style("极简")
    if style:
        print("Matched style:", style["style"])
        print("Positive keywords:", style["positive"])
        print("Negative keywords:", style["negative"])
        print("Mood description:", style["mood"])
    else:
        print("No matching style found.")
