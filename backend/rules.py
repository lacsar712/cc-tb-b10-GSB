import re

# 唛头样式：前缀汉字段 + 中划线 + 四位数字，如 茶-1234
HAN_PREFIX_RE = re.compile(r"^[一-鿿]+$")
MARK_DIGITS = 4


def weigh(aroma: float, taste: float, liquor: float) -> tuple[str, str, float]:
    score = round(aroma * 0.3 + taste * 0.5 + liquor * 0.2, 2)
    if score >= 7:
        return "通过", "加权分达到放行线", score
    return "不通过", "加权分低于放行线", score


def valid_prefix(prefix: str) -> bool:
    """样式前缀必须是非空汉字段。"""
    return bool(HAN_PREFIX_RE.fullmatch(prefix or ""))


def mark_matches(mark: str, prefix: str) -> bool:
    """唛头必须为：当前样式的汉字前缀 + 半角中划线 + 恰好四位数字。"""
    if not valid_prefix(prefix):
        return False
    return bool(re.fullmatch(rf"{re.escape(prefix)}-[0-9]{{{MARK_DIGITS}}}", mark or ""))
