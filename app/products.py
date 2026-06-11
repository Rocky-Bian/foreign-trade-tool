from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProductProfile:
    id: str
    name: str
    name_en: str
    description: str
    customer_types: list[str]
    markets: list[str]
    market_label: str
    keyword_templates: list[str] = field(default_factory=list)
    icp_hint: str = ""


SEA_COUNTRIES = [
    ("TH", "Thailand"),
    ("VN", "Vietnam"),
    ("ID", "Indonesia"),
    ("MY", "Malaysia"),
    ("PH", "Philippines"),
    ("SG", "Singapore"),
    ("MM", "Myanmar"),
    ("KH", "Cambodia"),
    ("LA", "Laos"),
]

GLOBAL_REGIONS = [
    ("US", "United States"),
    ("DE", "Germany"),
    ("GB", "United Kingdom"),
    ("FR", "France"),
    ("IN", "India"),
    ("BR", "Brazil"),
    ("MX", "Mexico"),
    ("AU", "Australia"),
    ("JP", "Japan"),
    ("KR", "South Korea"),
    ("AE", "UAE"),
    ("SA", "Saudi Arabia"),
    ("ZA", "South Africa"),
    ("NG", "Nigeria"),
    ("PL", "Poland"),
    ("IT", "Italy"),
    ("ES", "Spain"),
    ("NL", "Netherlands"),
    ("TR", "Turkey"),
    ("RU", "Russia"),
]


PRODUCTS: dict[str, ProductProfile] = {
    "halogen_moisture": ProductProfile(
        id="halogen_moisture",
        name="卤素水分仪",
        name_en="Halogen Moisture Analyzer",
        description="实验室/质检用卤素加热水分测定仪，精度高，适合经销商渠道销售",
        customer_types=["distributor", "dealer", "wholesaler"],
        markets=[c[0] for c in SEA_COUNTRIES],
        market_label="东南亚",
        keyword_templates=[
            "halogen moisture analyzer {customer_type} {country}",
            "moisture meter {customer_type} {country}",
            "laboratory equipment {customer_type} {country}",
            "weighing scale moisture analyzer {country}",
            "food testing equipment {customer_type} {country}",
        ],
        icp_hint=(
            "Target B2B distributors/dealers/wholesalers in Southeast Asia who sell "
            "laboratory instruments, weighing equipment, food/pharma testing devices, "
            "or general scientific equipment. Exclude manufacturers of moisture analyzers, "
            "retail marketplaces, and unrelated industries."
        ),
    ),
    "online_moisture": ProductProfile(
        id="online_moisture",
        name="在线水分仪",
        name_en="Online/In-line Moisture Analyzer",
        description="工业在线/原位水分检测，适用于生产线实时监测，面向经销商和终端工厂客户",
        customer_types=["distributor", "dealer", "manufacturer", "food processor", "chemical plant"],
        markets=[c[0] for c in GLOBAL_REGIONS],
        market_label="全球",
        keyword_templates=[
            "inline moisture analyzer {customer_type} {country}",
            "online moisture sensor {customer_type} {country}",
            "NIR moisture meter {customer_type} {country}",
            "process moisture measurement {country}",
            "industrial moisture analyzer {customer_type} {country}",
            "food production moisture monitoring {country}",
        ],
        icp_hint=(
            "Target distributors/dealers of industrial instrumentation AND end-user manufacturers "
            "in food, grain, chemical, pharma, plastics, paper, tobacco, or mining who need "
            "in-line/process moisture control. Exclude unrelated moisture products (soil/home), "
            "generic job boards, and marketplaces."
        ),
    ),
}


def get_product(product_id: str) -> ProductProfile:
    if product_id not in PRODUCTS:
        raise KeyError(f"Unknown product: {product_id}")
    return PRODUCTS[product_id]


def market_options(product_id: str) -> list[tuple[str, str]]:
    product = get_product(product_id)
    if product_id == "halogen_moisture":
        return SEA_COUNTRIES
    return GLOBAL_REGIONS
