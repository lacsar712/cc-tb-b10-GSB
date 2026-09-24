import re

# 唛头样式：前缀汉字段 + 中划线 + 四位数字，例如 茶-1234
PREFIX_RE = re.compile(r"^[一-鿿]+$")


def valid_prefix(prefix: str) -> bool:
    return bool(prefix) and bool(PREFIX_RE.match(prefix.strip()))


def mark_pattern(prefix: str) -> re.Pattern:
    return re.compile(r"^" + re.escape(prefix.strip()) + r"-\d{4}$")


def mark_matches(mark: str, prefix: str) -> bool:
    return bool(mark_pattern(prefix).match(mark.strip()))


def weigh(aroma: float, taste: float, liquor: float) -> tuple[str, str, float]:
    score = round(aroma * 0.3 + taste * 0.5 + liquor * 0.2, 2)
    if score >= 7:
        return "通过", "加权分达到放行线", score
    return "不通过", "加权分低于放行线", score
