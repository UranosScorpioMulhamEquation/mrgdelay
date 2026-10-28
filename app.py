from datetime import datetime, date, time, timedelta
import itertools
import os
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any, Optional

import geonamescache
import pandas as pd
import pytz
import streamlit as st
import swisseph as swe
from timezonefinder import TimezoneFinder

# ==================== إعدادات الصفحة و Swiss Ephemeris ====================
st.set_page_config(
    page_title="برنامج التحليل الفلكي لتأخر الزواج",
    page_icon="✨",
    layout="wide"
)

swe.set_ephe_path('')  # استخدام وضع Moshier الافتراضي للتقويم الفلكي الدقيق

# ==================== هيكل البيانات الجغرافية ====================
@dataclass
class City:
    geonameid: str
    name: str
    country_code: str
    latitude: float
    longitude: float
    admin1: str
    population: int

# ==================== تحميل البيانات الجغرافية تلقائياً ====================
@st.cache_resource
def load_cities() -> List[City]:
    gc = geonamescache.GeonamesCache()
    cities_list = []
    for city_id, city_data in gc.get_cities().items():
        if city_data.get("population", 0) >= 0:
            cities_list.append(
                City(
                    geonameid=city_id,
                    name=city_data.get("name", ""),
                    country_code=city_data.get("countrycode", ""),
                    latitude=city_data.get("latitude", 0.0),
                    longitude=city_data.get("longitude", 0.0),
                    admin1=city_data.get("admin1code", ""),
                    population=city_data.get("population", 0),
                )
            )
    return cities_list

@st.cache_resource
def load_countries() -> Dict[str, Dict[str, Any]]:
    gc = geonamescache.GeonamesCache()
    return gc.get_countries()

def get_sorted_countries() -> Tuple[Dict[str, str], List[str]]:
    countries_data = load_countries()
    country_map = {c_info["name"]: c_code for c_code, c_info in countries_data.items()}
    sorted_country_names = sorted(list(country_map.keys()))
    return country_map, sorted_country_names

def get_cities_by_country(country_code: str) -> List[City]:
    cities = load_cities()
    filtered_cities = [c for c in cities if c.country_code == country_code]
    return sorted(
        filtered_cities,
        key=lambda c: c.population,
        reverse=True,
    )

def get_utc_julian_day(date_obj: date, time_obj: time, tz_str: str) -> float:
    local_tz = pytz.timezone(tz_str)
    dt = datetime.combine(date_obj, time_obj)
    local_dt = local_tz.localize(dt)
    utc_dt = local_dt.astimezone(pytz.utc)
    return swe.julday(
        utc_dt.year,
        utc_dt.month,
        utc_dt.day,
        utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0,
    )

ZODIAC_SIGNS = [
    "الحمل", "الثور", "الجوزاء", "السرطان", 
    "الأسد", "العذراء", "الميزان", "العقرب", 
    "القوس", "الجدي", "الدلو", "الحوت"
]

def get_zodiac_sign(degrees: float) -> str:
    sign_index = int((degrees % 360) / 30)
    return ZODIAC_SIGNS[sign_index]

def get_whole_sign_house(planet_deg: float, asc_deg: float) -> int:
    """نظام كل برج بيت (Whole Sign Houses): البيت الأول هو برج الطالع كاملاً"""
    asc_sign_idx = int((asc_deg % 360) / 30)
    planet_sign_idx = int((planet_deg % 360) / 30)
    return (planet_sign_idx - asc_sign_idx) % 12 + 1

# ==================== إنشاء تقرير HTML متكامل ====================
def generate_html_report(
    name: str,
    gender: str,
    birth_date_str: str,
    birth_time_str: str,
    country_name: str,
    city_name: str,
    asc_sign: str,
    ascendant_deg: float,
    planet_data: dict,
    match_count: int,
    marriage_prediction: str,
    matched_conditions: list
) -> str:
    planet_rows = ""
    for p_name, p_info in planet_data.items():
        deg_str = f"{p_info['degrees'] % 30:.2f}°"
        planet_rows += f"""
        <tr>
            <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">{p_name}</td>
            <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">{p_info['sign']}</td>
            <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">{deg_str}</td>
            <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">البيت {p_info['house']}</td>
        </tr>
        """

    conditions_html = ""
    if matched_conditions:
        for idx, cond in enumerate(matched_conditions, 1):
            conditions_html += f"""
            <div style="background-color: #f9f9f9; border-right: 4px solid #1a365d; padding: 12px; margin-bottom: 10px; border-radius: 4px;">
                <h4 style="margin: 0 0 5px 0; color: #1a365d;">{idx}. {cond['title']} (دلالة رقم {cond['id']})</h4>
                <p style="margin: 0; color: #4a5568; font-size: 14px;">{cond['desc']}</p>
            </div>
            """
    else:
        conditions_html = "<p style='color: #2b6cb0;'>لم يتم رصد شروط ضاغطة على الزواج في هذه الهيئة الفلكية.</p>"

    html_content = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="UTF-8">
        <title>تقرير التحليل الفلكي لتأخر الزواج - {name}</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #f7fafc;
                color: #2d3748;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                max-width: 900px;
                margin: 0 auto;
                background: #ffffff;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            .header {{
                text-align: center;
                border-bottom: 2px solid #e2e8f0;
                padding-bottom: 20px;
                margin-bottom: 20px;
            }}
            .header h1 {{
                color: #1a365d;
                margin: 0 0 10px 0;
            }}
            .header p {{
                color: #718096;
                margin: 0;
            }}
            .section {{
                margin-bottom: 30px;
            }}
            .section h2 {{
                color: #2b6cb0;
                border-bottom: 1px solid #e2e8f0;
                padding-bottom: 8px;
            }}
            .grid {{
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 15px;
            }}
            .card {{
                background: #edf2f7;
                padding: 15px;
                border-radius: 6px;
            }}
            .card strong {{
                color: #2d3748;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
            }}
            th {{
                background-color: #2b6cb0;
                color: white;
                padding: 10px;
                border: 1px solid #ddd;
            }}
            .prediction-box {{
                background-color: #ebf8ff;
                border: 2px solid #3182ce;
                padding: 20px;
                border-radius: 8px;
                text-align: center;
                margin-top: 20px;
            }}
            .prediction-title {{
                font-size: 18px;
                color: #2c5282;
                margin-bottom: 10px;
            }}
            .prediction-value {{
                font-size: 26px;
                font-weight: bold;
                color: #2b6cb0;
            }}
            .footer {{
                text-align: center;
                font-size: 12px;
                color: #a0aec0;
                margin-top: 40px;
                border-top: 1px solid #e2e8f0;
                padding-top: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏛️ تقرير التحليل الفلكي لتأخر الزواج</h1>
                <p>نظام كل برج بيت (Whole Sign Houses)</p>
            </div>

            <div class="section">
                <h2>📋 البيانات الشخصية والهيئة الفلكية</h2>
                <div class="grid">
                    <div class="card"><strong>الاسم:</strong> {name}</div>
                    <div class="card"><strong>الجنس:</strong> {gender}</div>
                    <div class="card"><strong>تاريخ الميلاد:</strong> {birth_date_str}</div>
                    <div class="card"><strong>وقت الميلاد:</strong> {birth_time_str}</div>
                    <div class="card"><strong>مكان الميلاد:</strong> {city_name}، {country_name}</div>
                    <div class="card"><strong>الطالع الفلكي:</strong> {asc_sign} ({ascendant_deg:.2f}°)</div>
                </div>
            </div>

            <div class="prediction-box">
                <div class="prediction-title">نتيجة التحليل الشامل وتوقع سن الزواج</div>
                <div class="prediction-value">{marriage_prediction}</div>
                <p style="margin-top: 10px; color: #4a5568;">عدد الشروط المتحققة: <strong>{match_count}</strong> من أصل 50 شرطاً معتبراً</p>
            </div>

            <div class="section" style="margin-top: 30px;">
                <h2>🪐 مواقع الكواكب العشرة في البيوت (نظام كل برج بيت)</h2>
                <table>
                    <thead>
                        <tr>
                            <th>الكوكب</th>
                            <th>البرج</th>
                            <th>الدرجة</th>
                            <th>البيت</th>
                        </tr>
                    </thead>
                    <tbody>
                        {planet_rows}
                    </tbody>
                </table>
            </div>

            <div class="section">
                <h2>🔍 تفاصيل الدلالات والشروط المتحققة ({match_count} دلالة)</h2>
                {conditions_html}
            </div>

            <div class="footer">
                جميع الحقوق محفوظة للفلكي استرو رادار.
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

# ==================== واجهة المستخدم (Streamlit UI) ====================
st.title("🌟 النظام الاحترافي لتحليل دلالات تأخر الزواج")
st.markdown("### نظام كل برج بيت - تطوير الفلكي استرو رادار")
st.markdown("---")

with st.sidebar:
    st.header("📋 بيانات المولود")
    name = st.text_input("الاسم الكريم", "محمد")
    gender = st.selectbox("الجنس", ["ذكر", "أنثى"])
    
    birth_date = st.date_input(
        "تاريخ الميلاد",
        value=date(1990, 5, 15),
        min_value=date(1950, 1, 1),
        max_value=date(2040, 12, 31)
    )
    
    # اختيار الوقت بدقة الدقيقة الواحدة
    st.markdown("#### وقت الميلاد (دقة الدقيقة)")
    col_h, col_m = st.columns(2)
    with col_h:
        birth_hour = st.selectbox("الساعة", list(range(24)), index=12)
    with col_m:
        birth_minute = st.selectbox("الدقيقة", list(range(60)), index=0)
    
    birth_time = time(birth_hour, birth_minute)
    
    country_map, sorted_country_names = get_sorted_countries()
    selected_country_name = st.selectbox("دولة الميلاد", sorted_country_names)
    selected_country_code = country_map[selected_country_name]
    
    cities = get_cities_by_country(selected_country_code)
    city_names = [c.name for c in cities] if cities else [selected_country_name]
    selected_city_name = st.selectbox("مدينة الميلاد", city_names)
    
    selected_city = next((c for c in cities if c.name == selected_city_name), None)
    if selected_city:
        lat = selected_city.latitude
        lon = selected_city.longitude
    else:
        lat, lon = 24.4539, 54.3773  # افتراضي أبوظبي
        
    tf = TimezoneFinder()
    tz_str = tf.timezone_at(lat=lat, lng=lon)
    if not tz_str:
        tz_str = 'UTC'
        
    analyze_btn = st.button("🚀 ابدأ التحليل الفلكي الشامل", type="primary", width='stretch')

if analyze_btn:
    try:
        # 1. حساب التاريخ اليولياني بتوقيت UTC
        jd = get_utc_julian_day(birth_date, birth_time, tz_str)
        
        # 2. حساب الطالع وحساب البيوت بنظام كل برج بيت (Whole Sign)
        _, ascmc = swe.houses_ex(jd, lat, lon, b'P')
        ascendant_deg = ascmc[0]
        asc_sign = get_zodiac_sign(ascendant_deg)
        
        # 3. حساب الكواكب العشرة
        planet_defs = {
            'الشمس': swe.SUN,
            'القمر': swe.MOON,
            'عطارد': swe.MERCURY,
            'الزهرة': swe.VENUS,
            'المريخ': swe.MARS,
            'المشتري': swe.JUPITER,
            'زحل': swe.SATURN,
            'أورانوس': swe.URANUS,
            'نبتون': swe.NEPTUNE,
            'بلوتو': swe.PLUTO
        }
        
        planet_data = {}
        for p_name, p_id in planet_defs.items():
            res, _ = swe.calc_ut(jd, p_id)
            deg = res[0]
            planet_data[p_name] = {
                'degrees': deg,
                'sign': get_zodiac_sign(deg),
                'house': get_whole_sign_house(deg, ascendant_deg)
            }
            
        # دالة مساعدة لفحص الاقتران واتصالات التربيع/المقابلة
        def is_conjunct(p1: str, p2: str, orb: float = 7.0) -> bool:
            d1 = planet_data[p1]['degrees']
            d2 = planet_data[p2]['degrees']
            diff = abs(d1 - d2)
            if diff > 180:
                diff = 360 - diff
            return diff <= orb

        def is_afflicted(p_name: str, malefic: str, orb: float = 6.0) -> bool:
            d1 = planet_data[p_name]['degrees']
            d2 = planet_data[malefic]['degrees']
            diff = abs(d1 - d2)
            if diff > 180:
                diff = 360 - diff
            # اقتران، تربيع (90)، أو مقابلة (180)
            return diff <= orb or abs(diff - 90) <= orb or abs(diff - 180) <= orb

        # ==================== بناء قاعدة الـ 50 دلالة لتأخر الزواج (كاملاً دون اختصار) ====================
        conditions_pool = [
            # --- الدلالات الـ 20 من السياق المباشر ---
            {
                "id": 1, "title": "زحل في البيت السابع",
                "desc": "عوائق ومماطلات في الزواج، خوف من الالتزام، زواج متأخر جداً أو عدم زواج.",
                "met": planet_data['زحل']['house'] == 7
            },
            {
                "id": 2, "title": "زحل حاكم البيت السابع / متصل بالحاكم",
                "desc": "تأخر شديد في الزواج، حاجة لتجاوز دروس صعبة أولاً.",
                "met": planet_data['زحل']['house'] == 7 or is_afflicted('الزهرة', 'زحل')
            },
            {
                "id": 3, "title": "زحل في البيت الأول",
                "desc": "شخصية منغلقة، صعوبة في التعبير عن المشاعر، مظهر صارم يخيف الآخرين.",
                "met": planet_data['زحل']['house'] == 1
            },
            {
                "id": 4, "title": "زحل في البيت الخامس",
                "desc": "علاقات عاطفية فاشلة أو معدومة، خوف من المسؤولية الأسرية.",
                "met": planet_data['زحل']['house'] == 5
            },
            {
                "id": 5, "title": "زحل مقترن بالزهرة",
                "desc": "برودة عاطفية، خوف من الحب، حرمان عاطفي يؤدي لعدم الزواج.",
                "met": is_conjunct('زحل', 'الزهرة', 8.0)
            },
            {
                "id": 6, "title": "زحل في البيت الثامن",
                "desc": "عوائق نفسية أو جنسية، خوف من العلاقة الحميمة، صدمات سابقة.",
                "met": planet_data['زحل']['house'] == 8
            },
            {
                "id": 7, "title": "أورانوس في البيت السابع",
                "desc": "رفض الزواج التقليدي، ارتباطات لا تكتمل، نمط علاقات غير مستقر.",
                "met": planet_data['أورانوس']['house'] == 7
            },
            {
                "id": 8, "title": "أورانوس مقترن بالزهرة",
                "desc": "علاقات تبدأ بقوة وتنتهي فجأة، جذب للأشخاص غير المتاحين.",
                "met": is_conjunct('أورانوس', 'الزهرة', 6.0)
            },
            {
                "id": 9, "title": "نبتون في البيت السابع",
                "desc": "أوهام عن الشريك المثالي، علاقات غامضة لا تنتهي بزواج.",
                "met": planet_data['نبتون']['house'] == 7
            },
            {
                "id": 10, "title": "بلوتو في البيت السابع",
                "desc": "خوف من السيطرة أو فقدانها، صدمات سابقة في العلاقات.",
                "met": planet_data['بلوتو']['house'] == 7
            },
            {
                "id": 11, "title": "زحل في البيت العاشر",
                "desc": "انشغال تام بالعمل والمكانة، الزواج مؤجل لتحقيق أهداف مهنية.",
                "met": planet_data['زحل']['house'] == 10
            },
            {
                "id": 12, "title": "عطارد المقترن بزحل",
                "desc": "تفكير مفرط يحلل العلاقات ويمنع التقدم، منطق بارد يفسد العاطفة.",
                "met": is_conjunct('عطارد', 'زحل', 6.0)
            },
            {
                "id": 13, "title": "الشمس المقترنة بزحل",
                "desc": "شخصية أبوية متسلطة من الوالدين تمنع الزواج، أو ضعف ثقة بالنفس يمنع المبادرة.",
                "met": is_conjunct('الشمس', 'زحل', 7.0)
            },
            {
                "id": 14, "title": "القمر المقترن بزحل",
                "desc": "أم متطلبة أو باردة تؤثر على نظرة الشخص للزواج.",
                "met": is_conjunct('القمر', 'زحل', 7.0)
            },
            {
                "id": 15, "title": "الكثير من الكواكب في الأبراج الصامتة (العذراء، الجدي، الحوت)",
                "desc": "شخص لا يبادر ولا يظهر اهتماماً، فيؤجل الآخرون الارتباط به.",
                "met": sum(1 for p in planet_data.values() if p['sign'] in ['العذراء', 'الجدي', 'الحوت']) >= 5
            },
            {
                "id": 16, "title": "الطالع في برج العذراء أو الجدي",
                "desc": "شخصية متحفظة وحذرة، تظهر غير مهتمة بالزواج.",
                "met": asc_sign in ['العذراء', 'الجدي']
            },
            {
                "id": 17, "title": "ضعف كوكب الزهرة أو وجودها في برج صعب مع زحل",
                "desc": "قلة جاذبية عاطفية أو خوف من العلاقات الحميمة.",
                "met": planet_data['الزهرة']['sign'] in ['العقرب', 'الحمل', 'العذراء'] and is_afflicted('الزهرة', 'زحل')
            },
            {
                "id": 18, "title": "الشمس في البيت الثاني عشر مع زحل",
                "desc": "شخص يخفي رغبته في الزواج أو يشعر أنه غير مرغوب فيه.",
                "met": planet_data['الشمس']['house'] == 12 and (planet_data['زحل']['house'] == 12 or is_afflicted('الشمس', 'زحل'))
            },
            {
                "id": 19, "title": "بلوتو في البيت الخامس مع زحل",
                "desc": "علاقات عاطفية تنتهي بصدمات تمنع تكرار المحاولة.",
                "met": planet_data['بلوتو']['house'] == 5 and planet_data['زحل']['house'] == 5
            },
            {
                "id": 20, "title": "القمر في برج الجدي أو العذراء",
                "desc": "شخص يميل للعزلة العاطفية أو يشعر أن العلاقات تستهلكه.",
                "met": planet_data['القمر']['sign'] in ['الجدي', 'العذراء']
            },

            # --- 30 دلالة إضافية مستخلصة من أحدث المراجع الفلكية ---
            {
                "id": 21, "title": "المريخ في البيت السابع متصل بنحس",
                "desc": "خلافات ونزاعات حادة تجعل الشراكات العاطفية تنتهي قبل ترسيم الزواج.",
                "met": planet_data['المريخ']['house'] == 7 and (is_afflicted('المريخ', 'زحل') or is_afflicted('المريخ', 'الشمس'))
            },
            {
                "id": 22, "title": "المشتري في البيت السابع في موضع ضاغط",
                "desc": "مبالغة وتوقعات غير واقعية بالشريك تؤدي لرفض جميع الفرص المتاحة.",
                "met": planet_data['المشتري']['house'] == 7 and is_afflicted('المشتري', 'زحل')
            },
            {
                "id": 23, "title": "نبتون مقترن بالزهرة",
                "desc": "تعلق بالخيالات والأوهام العاطفية، والصدمة بالواقع عند الاقتراب من الزواج.",
                "met": is_conjunct('نبتون', 'الزهرة', 6.0)
            },
            {
                "id": 24, "title": "بلوتو مقترن بالزهرة",
                "desc": "هوس وشكوك وصدمات عاطفية تجعل الفرد ينعزل خوفاً من السيطرة.",
                "met": is_conjunct('بلوتو', 'الزهرة', 6.0)
            },
            {
                "id": 25, "title": "القمر في البيت السابع متأثر بالنحوس",
                "desc": "تقلبات مزاجية وتأثر مفرط بالعائلة يعيق الاستقرار والشراكة.",
                "met": planet_data['القمر']['house'] == 7 and is_afflicted('القمر', 'زحل')
            },
            {
                "id": 26, "title": "الشمس في البيت السابع تحت نحس",
                "desc": "استقلالية مفرطة وصراع قوة مع الطرف الآخر يؤدي لتأجيل الارتباط.",
                "met": planet_data['الشمس']['house'] == 7 and is_afflicted('الشمس', 'زحل')
            },
            {
                "id": 27, "title": "عطارد في البيت السابع متصل بزحل",
                "desc": "تحليل نقدي حاد وعقلاني يفسد مشاعر الود ويرفض المتقدمين للتفاهات.",
                "met": planet_data['عطارد']['house'] == 7 and is_afflicted('عطارد', 'زحل')
            },
            {
                "id": 28, "title": "الزهرة في البيت السادس",
                "desc": "انشغال كامل بتفاصيل الواجبات والعمل على حساب الحياة العاطفية.",
                "met": planet_data['الزهرة']['house'] == 6
            },
            {
                "id": 29, "title": "الزهرة في البيت الثاني عشر",
                "desc": "حب صامت، مشاعر سرية غير معلنة، أو علاقات تظل طي الكتمان ولا تتوج بالزواج.",
                "met": planet_data['الزهرة']['house'] == 12
            },
            {
                "id": 30, "title": "زحل في البيت الرابع",
                "desc": "بيئة أسرية قاسية أو باردة تخلق خوفاً باطناً من تكوين أسرة جديدة.",
                "met": planet_data['زحل']['house'] == 4
            },
            {
                "id": 31, "title": "أورانوس في البيت الأول",
                "desc": "رغبة جارفة بالاستقلالية والحرية ترفض القوالب التقليدية للزواج.",
                "met": planet_data['أورانوس']['house'] == 1
            },
            {
                "id": 32, "title": "نبتون في البيت الأول",
                "desc": "شخصية ضبابية مترددة تصعّب على الطرف الآخر فهم رغباتها العاطفية.",
                "met": planet_data['نبتون']['house'] == 1
            },
            {
                "id": 33, "title": "بلوتو في البيت الأول",
                "desc": "حضور حاد وجاد جداً يشكل حاجزاً يمنع الآخرين من المبادرة للتقرب.",
                "met": planet_data['بلوتو']['house'] == 1
            },
            {
                "id": 34, "title": "القمر في برج العقرب (هبوط القمر)",
                "desc": "عمق مشاعر مشحون بالخوف والشك يمنع الثقة السريعة بالشريك.",
                "met": planet_data['القمر']['sign'] == 'العقرب'
            },
            {
                "id": 35, "title": "الزهرة في الحمل أو العقرب مع تربيع زحل",
                "desc": "صراع شديد بين الرغبة الملحة والخوف التام من التعرض للرفض.",
                "met": planet_data['الزهرة']['sign'] in ['الحمل', 'العقرب'] and is_afflicted('الزهرة', 'زحل')
            },
            {
                "id": 36, "title": "المريخ مقترن بزحل",
                "desc": "إحباط الطاقة العاطفية والجنسية وكبح المبادرة في أوقاتها المناسبة.",
                "met": is_conjunct('المريخ', 'زحل', 6.0)
            },
            {
                "id": 37, "title": "المشتري مقترن بزحل",
                "desc": "تردد وتناقض بين الانفتحاح والتحفظ يضيع فرصل الزواج الذهبية.",
                "met": is_conjunct('المشتري', 'زحل', 6.0)
            },
            {
                "id": 38, "title": "انعدام الكواكب في البيوت الهوائية (الجوزاء، الميزان، الدلو)",
                "desc": "صعوبة بالتواصل اللفظي والاجتماعي المريح لجذب الشريك.",
                "met": sum(1 for p in planet_data.values() if p['sign'] in ['الجوزاء', 'الميزان', 'الدلو']) == 0
            },
            {
                "id": 39, "title": "الشمس والقمر في تربيع أو مقابلة",
                "desc": "صراع بين إرادة الشخص العقلانية واحتياجاته العاطفية الباطنة.",
                "met": abs(planet_data['الشمس']['degrees'] - planet_data['القمر']['degrees']) in range(84, 96) or abs(planet_data['الشمس']['degrees'] - planet_data['القمر']['degrees']) in range(174, 186)
            },
            {
                "id": 40, "title": "زحل في البيت الحادي عشر",
                "desc": "دائرة اجتماعية ضيقة جداً وقلة في الدعم الاجتماعي والفرص.",
                "met": planet_data['زحل']['house'] == 11
            },
            {
                "id": 41, "title": "أورانوس في البيت الخامس",
                "desc": "تغيرات مفاجئة وانقطاع سريع ومباغت في العلاقات العاطفية.",
                "met": planet_data['أورانوس']['house'] == 5
            },
            {
                "id": 42, "title": "نبتون في البيت الخامس",
                "desc": "استنزاف عاطفي في التضحية لأشخاص غير مستعدين للالتزام.",
                "met": planet_data['نبتون']['house'] == 5
            },
            {
                "id": 43, "title": "القمر في البيت الثاني عشر",
                "desc": "حاجة للعزلة ومخاوف باطنية من فقدان الخصوصية بعد الزواج.",
                "met": planet_data['القمر']['house'] == 12
            },
            {
                "id": 44, "title": "الشمس في البيت الثامن",
                "desc": "صعوبة في تسليم السيطرة للشريك وتجارب تحولية قاسية.",
                "met": planet_data['الشمس']['house'] == 8
            },
            {
                "id": 45, "title": "عطارد في الجدي أو العقرب",
                "desc": "تفكير حذر ومحترس للغاية يبحث عن الأخطاء والعيوب.",
                "met": planet_data['عطارد']['sign'] in ['الجدي', 'العقرب']
            },
            {
                "id": 46, "title": "المريخ في الجدي أو العذراء",
                "desc": "استهلاك الطاقة الحيوية في الطموح المهني وتأجيل العاطفة.",
                "met": planet_data['المريخ']['sign'] in ['الجدي', 'العذراء']
            },
            {
                "id": 47, "title": "الطالع في برج العقرب",
                "desc": "تحفظ شديد وغموض يظهر الشخص بمظهر كافٍ بنفسه لا يبحث عن ارتباط.",
                "met": asc_sign == 'العقرب'
            },
            {
                "id": 48, "title": "تركز 4 كواكب أو أكثر في بيوت الأرض (2، 6، 10)",
                "desc": "تركيز تام على التأمين المادي والاستقرار العملي قبل أي خطوة عاطفية.",
                "met": sum(1 for p in planet_data.values() if p['house'] in [2, 6, 10]) >= 4
            },
            {
                "id": 49, "title": "الزهرة مقترنة بالمريخ في برج ترابي",
                "desc": "جمود وتقييد للمشاعر العفوية والتعبير عن المحبة.",
                "met": is_conjunct('الزهرة', 'المريخ', 6.0) and planet_data['الزهرة']['sign'] in ['الثور', 'العذراء', 'الجدي']
            },
            {
                "id": 50, "title": "اتصالات متعددة لزحل بالكواكب الشخصية",
                "desc": "بطء عام وتأخير ملموس في تجسيد خطوات الالتزام والاستقرار.",
                "met": sum(1 for p in ['الشمس', 'القمر', 'الزهرة', 'المريخ'] if is_afflicted(p, 'زحل')) >= 2
            }
        ]

        matched_conditions = [c for c in conditions_pool if c['met']]
        match_count = len(matched_conditions)

        # ==================== تحديد نطاق التوقع (بفارق 5 سنوات) ====================
        if match_count >= 16 or (planet_data['زحل']['house'] == 7 and match_count >= 11):
            marriage_prediction = "حظوظ قليلة للزواج"
            prediction_color = "red"
        elif match_count >= 12:
            marriage_prediction = "من 40 - 45 سنه"
            prediction_color = "#d69e2e"
        elif match_count >= 8:
            marriage_prediction = "من 35 - 40 سنه"
            prediction_color = "#dd6b20"
        elif match_count >= 5:
            marriage_prediction = "من 30 - 35 سنه"
            prediction_color = "#3182ce"
        elif match_count >= 3:
            marriage_prediction = "من 25 - 30 سنه"
            prediction_color = "#2b6cb0"
        else:
            marriage_prediction = "زواج مبكر (قبل سن 25 سنة)"
            prediction_color = "#38a169"

        # ==================== عرض النتائج في واجهة Streamlit ====================
        st.success("✨ تم إتمام الحسابات الفلكية (نظام كل برج بيت) وتحليل الهيئة بنجاح تام!")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("الاسم الكريم", name)
            st.metric("الجنس", gender)
        with col2:
            st.metric("الطالع الفلكي (كل برج بيت)", f"{asc_sign} ({ascendant_deg:.2f}°)")
            st.metric("المدينة والبلد", f"{selected_city_name}, {selected_country_name}")
        with col3:
            st.metric("الشروط المتحققة (من 50)", f"{match_count} شرط")
            st.markdown(f"**توقع سن الزواج:**\n<h3 style='color:{prediction_color};'>{marriage_prediction}</h3>", unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("🪐 مواقع الكواكب العشرة في البيوت (نظام كل برج بيت):")
        
        planet_table_data = []
        for p_name, p_info in planet_data.items():
            planet_table_data.append({
                "الكوكب": p_name,
                "البرج": p_info['sign'],
                "درجة البرج": f"{p_info['degrees'] % 30:.2f}°",
                "البيت (كل برج بيت)": f"البيت {p_info['house']}"
            })
        st.dataframe(pd.DataFrame(planet_table_data), width='stretch')

        st.markdown("---")
        st.subheader(f"📋 تقرير دلالات تأخر الزواج المتحققة ({match_count} شرط متحقق)")
        
        if match_count >= 3:
            st.warning(f"⚠️ لقد تحقق **{match_count}** شرطاً من أصل 50 شرطاً معتبراً لتأخر الزواج (الحد الأدنى هو 3 شروط). إليك الشروط المرصودة:")
            for idx, cond in enumerate(matched_conditions, 1):
                with st.expander(f"{idx}. {cond['title']} (رقم الدلالة: {cond['id']})"):
                    st.write(cond['desc'])
        else:
            st.info(f"ℹ️ عدد الشروط المتحققة هو **{match_count}** (أقل من الحد الأدنى 3 شروط)، مما يعني أن مؤشرات تأخر الزواج ضعيفة جداً في هذه الهيئة.")
            if matched_conditions:
                st.write("الشروط النادرة المتحققة:")
                for idx, cond in enumerate(matched_conditions, 1):
                    st.markdown(f"- **{cond['title']}**: {cond['desc']}")

        # ==================== توليد وتحميل تقرير HTML ====================
        st.markdown("---")
        st.subheader("📄 طباعة وتحميل التقرير الكامل بصيغة HTML")
        
        html_report = generate_html_report(
            name=name,
            gender=gender,
            birth_date_str=birth_date.strftime("%Y-%m-%d"),
            birth_time_str=birth_time.strftime("%H:%M"),
            country_name=selected_country_name,
            city_name=selected_city_name,
            asc_sign=asc_sign,
            ascendant_deg=ascendant_deg,
            planet_data=planet_data,
            match_count=match_count,
            marriage_prediction=marriage_prediction,
            matched_conditions=matched_conditions
        )
        
        st.download_button(
            label="📥 تحميل التقرير بصيغة HTML للطباعة",
            data=html_report,
            file_name=f"Marriage_Astrology_Report_{name}.html",
            mime="text/html",
            type="primary"
        )

    except Exception as e:
        st.error(f"حدث خطأ أثناء المعالجة الحسابية الفلكية: {e}")