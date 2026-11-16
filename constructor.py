#!/usr/bin/env python3
"""
Конструктор постановлений — нативная Linux-версия.
"""
import textwrap
import json, os, sys, tempfile, shutil, re, zipfile, copy, hashlib, base64, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "libs"))
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
import traceback
import argparse
import csv
import html
import http.server
import threading
import warnings
import webbrowser
from urllib.parse import urlsplit
warnings.filterwarnings("ignore")

def setup_logger():
    logger = logging.getLogger("Constructor")
    logger.setLevel(logging.INFO)
    log_dir = Path("Логи")
    log_dir.mkdir(parents=True, exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    log_file = log_dir / f"{today_str}.log"
    if logger.hasHandlers():
        logger.handlers.clear()
    handler = logging.FileHandler(log_file, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

logger = setup_logger()

from collections import defaultdict
# Единый код: модуль tracker больше не импортируется — его функции встроены ниже
# (раздел «ТРЕКЕР ИЗМЕНЕНИЙ РАЗДЕЛА ТОС»). Флаг сохранён для обратной совместимости.
tracker = sys.modules.get(__name__)  # self-reference: tracker.scan() работает всегда
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None  # потребуется только для команд duma/tracker/diagnose
import tkinter as tk
import tksheet
from tkinter import ttk, messagebox, simpledialog, filedialog

# ============================================================
# КОНСТАНТЫ
# ============================================================
SIGNER_TITLE = "Временно исполняющий обязанности главы муниципального образования город Краснодар"
SIGNER_NAME  = "Д.Ю.Васильев"
YEAR_LIST = [2026, 2027, 2028]
SUM_YEARS = list(range(2015, 2029))
PASSPORT_PROGRAM_TOTAL = 2733127.5
OFFICIAL_SUB2_2026     = 44947.8

EXECUTOR_KGTOS = "Краснодарская городская ассоциация территориального общественного самоуправления"
EXECUTOR_SOYUZ = "Союз «Совет органов территориального общественного самоуправления муниципального образования город Краснодар»"

GROUPS = [
    ("1", "1. Избирательный округ № 10"),
    ("2", "2. Избирательный округ № 12"),
    ("3", "3. Избирательный округ № 20"),
    ("4", "4. Избирательный округ № 27"),
    ("5", "5. Избирательный округ № 31"),
    ("6", "6. Избирательный округ № 33"),
    ("7", "7. Муниципальный избирательный округ, депутат городской Думы Краснодара Галушко В.Ф."),
]
GROUPS_DICT = dict(GROUPS)

OTHER_SUBPROGRAMS = {
    "podderzhka":     ("Поддержка общественных инициатив и содействие развитию гражданского общества", 953223.1),
    "garmonizatsiya": ("Гармонизация межнациональных отношений и профилактика терроризма и экстремизма", 664930.1),
    "kazaki_vcp":     ("Казаки Краснодара (ВЦП)", 384568.7),
    "kazaki_podpr":   ("Казаки Краснодара (подпрограмма)", 230585.9),
    "arhivy":         ("Формирование и содержание муниципальных архивов (мероприятие)", 5409.3),
}

SUB2_YEARS = {
    "2015": 25523.8, "2016": 26014.8, "2017": 27606.8, "2018": 28893.2,
    "2019": 30427.6, "2020": 29661.5, "2021": 33280.9, "2022": 38891.1,
    "2023": 39118.8, "2024": 40023.4, "2025": 41310.7,
    "2026": 44947.8, "2027": 44355.0, "2028": 44355.0,
}

# ============================================================
# МОДЕЛЬ: мероприятия
# ============================================================
EVENTS = [
    # ==================== TABLE 3 (общая таблица) ====================
    {"id":"e_comp","source":"table3","name":"п. 1.1.1 «Предоставление компенсационных выплат председателям органов ТОС»","old_value":42000.0,"years":{"2026":42000.0,"2027":42000.0,"2028":42000.0}},
    {"id":"e_1_2","source":"table3","name":"п. 1.1.2 «Изготовление удостоверений для председателей органов ТОС и треугольных штампов»","old_value":50.0,"years":{"2026":50.0,"2027":50.0,"2028":50.0}},
    {"id":"e_2_1_3","source":"table3","name":"п. 2.1.3 «Проведение круглых столов, конференций по решению социально значимых вопросов»","old_value":100.0,"years":{"2026":100.0,"2027":100.0,"2028":100.0}},
    {"id":"e_bulletin","source":"table3","name":"п. 2.2.3 «Издание ежегодного бюллетеня о деятельности органов ТОС»","old_value":60.0,"years":{"2026":60.0,"2027":60.0,"2028":60.0}},
    {"id":"e_metod","source":"table3","name":"п. 2.2.5 «Разработка, издание и распространение информационно-методических и справочных материалов»","old_value":75.0,"years":{"2026":75.0,"2027":75.0,"2028":75.0}},
    {"id":"e_contest","source":"table3","name":"п. 3.1.1 «Проведение городских конкурсов на звания \"Лучший орган ТОС\"»","old_value":1236.0,"years":{"2026":1236.0,"2027":1236.0,"2028":1236.0}},
    {"id":"e_3_1_2","source":"table3","name":"п. 3.1.2 «Проведение конференций, а также участие в зональных (краевых) совещаниях»","old_value":112.0,"years":{"2026":112.0,"2027":112.0,"2028":112.0}},
    {"id":"e_celebr","source":"table3","name":"п. 3.1.3 «Проведение праздничного мероприятия по подведению итогов работы органов ТОС»","old_value":457.0,"years":{"2026":457.0,"2027":457.0,"2028":457.0}},
    {"id":"e_3_1_4","source":"table3","name":"п. 3.1.4 «Проведение мероприятия, посвящённого Дню местного самоуправления»","old_value":265.0,"years":{"2026":265.0,"2027":265.0,"2028":265.0}},
    {"id":"e_1_1_3","source":"table3","name":"п. 1.1.3 «Реализация мероприятий Программы по выполнению наказов избирателей депутатам городской Думы Краснодара VIII созыва: приложение N 3»","old_value":0.0,"is_aggregate":True},

    # ==================== APP3 (приложение № 3) ====================
    # Округ 10 (group 1)
    {"id":"e_1_1","source":"app3","parent":"e_1_1_3","group":"1","name":"п. 1.1 «Организация оздоровительной поездки по Краснодарскому краю»","old_value":45.0,"years":{"2026":45.0,"2027":0.0,"2028":0.0},"executor":EXECUTOR_KGTOS},
    # Округ 12 (group 2)
    {"id":"e_2_1","source":"app3","parent":"e_1_1_3","group":"2","name":"п. 2.1 «Проведение мероприятия \"Праздник нашего двора\"»","old_value":55.0,"years":{"2026":55.0,"2027":0.0,"2028":0.0},"executor":EXECUTOR_KGTOS},
    {"id":"e_2_2","source":"app3","parent":"e_1_1_3","group":"2","name":"п. 2.2 «Мероприятия, посвященные Международному дню защиты детей»","old_value":75.0,"years":{"2026":75.0,"2027":0.0,"2028":0.0},"executor":EXECUTOR_KGTOS},
    {"id":"e_2_3","source":"app3","parent":"e_1_1_3","group":"2","name":"п. 2.3 «Мероприятия, посвященные Дню России»","old_value":10.0,"years":{"2026":10.0,"2027":0.0,"2028":0.0},"executor":EXECUTOR_KGTOS},
    {"id":"e_2_4","source":"app3","parent":"e_1_1_3","group":"2","name":"п. 2.4 «Мероприятия, посвященные празднованию Дня города Краснодара»","old_value":50.0,"years":{"2026":50.0,"2027":0.0,"2028":0.0},"executor":EXECUTOR_KGTOS},
    {"id":"e_2_5","source":"app3","parent":"e_1_1_3","group":"2","name":"п. 2.5 «Мероприятия, посвященные Дню отца»","old_value":10.0,"years":{"2026":10.0,"2027":0.0,"2028":0.0},"executor":EXECUTOR_KGTOS},
    {"id":"e_2_6","source":"app3","parent":"e_1_1_3","group":"2","name":"п. 2.6 «Мероприятия, посвященные Дню пожилых людей»","old_value":50.0,"years":{"2026":50.0,"2027":0.0,"2028":0.0},"executor":EXECUTOR_KGTOS},
    {"id":"e_2_7","source":"app3","parent":"e_1_1_3","group":"2","name":"п. 2.7 «Мероприятия, посвященные Дню матери»","old_value":55.0,"years":{"2026":55.0,"2027":0.0,"2028":0.0},"executor":EXECUTOR_KGTOS},
    {"id":"e_2_8","source":"app3","parent":"e_1_1_3","group":"2","name":"п. 2.8 «Мероприятия, посвященные празднованию Нового года»","old_value":180.0,"years":{"2026":180.0,"2027":0.0,"2028":0.0},"executor":EXECUTOR_KGTOS},
    # Округ 20 (group 3)
    {"id":"e_3_1","source":"app3","parent":"e_1_1_3","group":"3","name":"п. 3.1 «Организация оздоровительных поездок по Краснодарскому краю»","old_value":350.0,"years":{"2026":350.0,"2027":0.0,"2028":0.0},"executor":EXECUTOR_KGTOS},
    # Округ 27 (group 4)
    {"id":"e_4_1","source":"app3","parent":"e_1_1_3","group":"4","name":"п. 4.1 «Мероприятия, посвященные Всероссийскому дню семьи, любви и верности»","old_value":20.0,"years":{"2026":20.0,"2027":0.0,"2028":0.0},"executor":EXECUTOR_KGTOS},
    {"id":"e_4_2","source":"app3","parent":"e_1_1_3","group":"4","name":"п. 4.2 «Мероприятия, посвященные Дню знаний»","old_value":200.0,"years":{"2026":200.0,"2027":0.0,"2028":0.0},"executor":EXECUTOR_KGTOS},
    # Округ 31 (group 5)
    {"id":"e_5_1","source":"app3","parent":"e_1_1_3","group":"5","name":"п. 5.1 «Мероприятия, посвященные Всероссийскому дню семьи, любви и верности»","old_value":100.0,"years":{"2026":100.0,"2027":0.0,"2028":0.0},"executor":EXECUTOR_KGTOS},
    {"id":"e_5_2","source":"app3","parent":"e_1_1_3","group":"5","name":"п. 5.2 «Соберем ребенка в школу вместе»","old_value":100.0,"years":{"2026":100.0,"2027":0.0,"2028":0.0},"executor":EXECUTOR_KGTOS},
    {"id":"e_5_3","source":"app3","parent":"e_1_1_3","group":"5","name":"п. 5.3 «Мероприятия, посвященные празднованию Нового года»","old_value":20.0,"years":{"2026":20.0,"2027":0.0,"2028":0.0},"executor":EXECUTOR_KGTOS},
    # Округ 33 (group 6)
    {"id":"e_6_1","source":"app3","parent":"e_1_1_3","group":"6","name":"п. 6.1 «Мероприятия, посвященные Международному дню защиты детей»","old_value":30.0,"years":{"2026":30.0,"2027":0.0,"2028":0.0},"executor":EXECUTOR_SOYUZ},
    {"id":"e_6_2","source":"app3","parent":"e_1_1_3","group":"6","name":"п. 6.2 «Мероприятия, посвященные Дню России»","old_value":70.0,"years":{"2026":70.0,"2027":0.0,"2028":0.0},"executor":EXECUTOR_SOYUZ},
    {"id":"e_6_3","source":"app3","parent":"e_1_1_3","group":"6","name":"п. 6.3 «Мероприятия, посвященные Празднику весны и труда»","old_value":50.0,"years":{"2026":50.0,"2027":0.0,"2028":0.0},"executor":EXECUTOR_SOYUZ},
    {"id":"e_6_4","source":"app3","parent":"e_1_1_3","group":"6","name":"п. 6.4 «Проведение Фестиваля творчества \"Искусство - это жизнь\"»","old_value":30.0,"years":{"2026":30.0,"2027":0.0,"2028":0.0},"executor":EXECUTOR_SOYUZ},
    {"id":"e_6_5","source":"app3","parent":"e_1_1_3","group":"6","name":"п. 6.5 «Мероприятия, посвященные Дню народного единства»","old_value":60.0,"years":{"2026":60.0,"2027":0.0,"2028":0.0},"executor":EXECUTOR_SOYUZ},
    {"id":"e_6_6","source":"app3","parent":"e_1_1_3","group":"6","name":"п. 6.6 «Мероприятия, посвященные празднованию Нового года»","old_value":60.0,"years":{"2026":60.0,"2027":0.0,"2028":0.0},"executor":EXECUTOR_SOYUZ},
    {"id":"e_6_7","source":"app3","parent":"e_1_1_3","group":"6","name":"п. 6.7 «Мероприятия, посвященные празднованию Дня города Краснодара»","old_value":70.0,"years":{"2026":70.0,"2027":0.0,"2028":0.0},"executor":EXECUTOR_SOYUZ},
    # Галушко (group 7)
    {"id":"e_7_1","source":"app3","parent":"e_1_1_3","group":"7","name":"п. 7.1 «Мероприятия, посвященные Дню Победы советского народа в Великой Отечественной войне 1941 - 1945 гг.»","old_value":100.0,"years":{"2026":100.0,"2027":0.0,"2028":0.0},"executor":EXECUTOR_KGTOS},
    {"id":"e_7_2","source":"app3","parent":"e_1_1_3","group":"7","name":"п. 7.2 «Мероприятия, посвященные Международному дню защиты детей»","old_value":100.0,"years":{"2026":100.0,"2027":0.0,"2028":0.0},"executor":EXECUTOR_KGTOS},
    {"id":"e_7_3","source":"app3","parent":"e_1_1_3","group":"7","name":"п. 7.3 «Мероприятия, посвященные Дню территориального общественного самоуправления»","old_value":50.0,"years":{"2026":50.0,"2027":0.0,"2028":0.0},"executor":EXECUTOR_KGTOS},
    {"id":"e_7_4","source":"app3","parent":"e_1_1_3","group":"7","name":"п. 7.4 «Мероприятия, посвященные празднованию Нового года»","old_value":80.0,"years":{"2026":80.0,"2027":0.0,"2028":0.0},"executor":EXECUTOR_KGTOS},
]

PRESET_EDITIONS = [
    {"id":"preset_424","date":"2026-01-29","label":"ПП N 424 от 29.01.2026","note":"2026 = 47 040,0 · 1.1.3 = 2 685,0","changes":{"e_1_1_3":{"2026":2685.0,"2027":0.0,"2028":0.0}}},
    {"id":"preset_1525","date":"2026-03-27","label":"ПП N 1525 от 27.03.2026","note":"2026 = 47 055,0 · 1.1.3 = 2 700,0","changes":{"e_1_1_3":{"2026":2700.0,"2027":0.0,"2028":0.0}}},
    {"id":"preset_2325","date":"2026-04-24","label":"ПП N 2325 от 24.04.2026","note":"2026 = 46 535,0 · 1.1.3 = 2 180,0","changes":{"e_1_1_3":{"2026":2180.0,"2027":0.0,"2028":0.0}}},
    {"id":"preset_3627","date":"2026-06-11","label":"ПП N 3627 от 11.06.2026","note":"2026 = 46 285,0 · 1.1.3 = 1 950,0 · 2.1.3 = 80,0","changes":{"e_1_1_3":{"2026":1950.0,"2027":0.0,"2028":0.0},"e_2_1_3":{"2026":80.0,"2027":100.0,"2028":100.0}}},
    {"id":"preset_5867","date":"2026-08-31","label":"ПП N 5867 от 31.08.2026","note":"2026 = 46 355,0 · 1.1.3 = 2 020,0","changes":{"e_1_1_3":{"2026":2020.0,"2027":0.0,"2028":0.0},"e_2_1_3":{"2026":80.0,"2027":100.0,"2028":100.0}}},
    {"id":"preset_7376","date":"2026-10-22","label":"ПП N 7376 от 22.10.2026 (текущая)","note":"2026 = 44 947,8 · 1.1.3 = 1 860,0","changes":{"e_1_1_3":None,"e_2_1_3":{"2026":80.0,"2027":100.0,"2028":100.0},"e_contest":{"2026":36.0,"2027":1236.0,"2028":1236.0},"e_3_1_2":{"2026":65.0,"2027":112.0,"2028":112.0},"e_bulletin":{"2026":59.8,"2027":60.0,"2028":60.0}}},
]

# ============================================================
# ПАРСЕР РЕШЕНИЙ ДУМЫ (был в duma_parser_tos.py)
# ============================================================
N_COLS = 7
RE_CHANGE = re.compile(r"от\s+(\d{2}\.\d{2}\.\d{4})\s+N\s+([\w\-.]+)\s+п\.(\d+)")

# ключевая фраза, по которой отбирается раздел (без привязки к регистру)
DEFAULT_SECTION = "Развитие форм участия населения в местном самоуправлении муниципального образования город Краснодар"

def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\xa0", " ")).strip()


def parse_amount(s: str):
    if not s:
        return None
    t = s.replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def expand_table(table):
    """Разворачивает rowspan/colspan в прямоугольную сетку."""
    grid = []
    spans = {}
    for tr in table.find_all("tr"):
        cells = tr.find_all(["td", "th"], recursive=False)
        row, col, i = [], 0, 0
        while True:
            while col in spans and spans[col][0] > 0:
                row.append(spans[col][1])
                spans[col][0] -= 1
                if spans[col][0] == 0:
                    del spans[col]
                col += 1
            if i >= len(cells):
                break
            cell = cells[i]; i += 1
            text = norm(cell.get_text(" ", strip=True))
            rs = int(cell.get("rowspan") or 1)
            cs = int(cell.get("colspan") or 1)
            for _ in range(cs):
                row.append(text)
                if rs > 1:
                    spans[col] = [rs - 1, text]
                col += 1
        while col in spans and spans[col][0] > 0:
            row.append(spans[col][1])
            spans[col][0] -= 1
            if spans[col][0] == 0:
                del spans[col]
            col += 1
        grid.append(row)
    return grid


def iter_blocks(soup):
    body = soup.body or soup
    for el in body.find_all(["div", "table"]):
        if el.name == "div" and el.find_parent("table") is not None:
            continue
        yield el


def parse_meta(soup):
    title = norm(soup.title.get_text(" ", strip=True)) if soup.title else ""
    meta = {"title": title, "date": None, "number": None,
            "redaction": None, "name": None}
    m = re.search(r"от\s+(\d{2}\.\d{2}\.\d{4})\s+N\s+([\w\-.]+)", title)
    if m:
        meta["date"], meta["number"] = m.group(1), m.group(2)
    m = re.search(r"\(ред\.\s*от\s+(\d{2}\.\d{2}\.\d{4})\)", title)
    if m:
        meta["redaction"] = m.group(1)
    parts = title.split('"')
    if len(parts) >= 3:
        meta["name"] = norm(parts[1])
    return meta


def parse_changes(soup):
    for div in soup.find_all("div", string=re.compile("Список изменяющих документов")):
        td = div.find_parent("td") or div.parent
        text = norm(td.get_text(" ", strip=True))
        return [{"date": d, "number": n, "item": p}
                for d, n, p in RE_CHANGE.findall(text)]
    return []


def _heading_matches(parts, section_filter):
    if not parts:
        return False
    heading = " ".join(parts)
    return section_filter.lower() in heading.lower()


def parse_document(path, section_filter=DEFAULT_SECTION):
    if BeautifulSoup is None:
        raise ImportError("Не установлена библиотека beautifulsoup4. Установите: pip install beautifulsoup4 lxml")
    soup = BeautifulSoup(Path(path).read_bytes(), "html.parser")

    doc = {
        "meta": parse_meta(soup),
        "changes": parse_changes(soup),
        "section": {"name": None, "total": None, "items": [], "notes": []},
    }
    section = doc["section"]

    in_target = False
    pending_heading = False
    heading_parts = []
    last_div_text = ""
    pending_excluded = []  # найденные фразы "По ... округу X строку Y исключить"
    
    # Регулярка для фраз "По [муниципальному] избирательному округу X строку Y исключить"
    EXCLUDE_PATTERN = re.compile(
        r"По\s+(?:муниципальному\s+)?избирательному\s+округу\s+(?:N\s+)?([^\s]+(?:\s+[А-ЯЁA-Z]\.\s*[А-ЯЁA-Z]\.)?)\s+"
        r"(?:в\s+строке\s+\d+\s+)?(?:строку|строки)\s+(\d+(?:,\s*\d+)*)\s+исключить",
        re.IGNORECASE
    )

    def detect_marker(text):
        """Определяет маркер изменения по тексту перед таблицей."""
        if not text:
            return "none"
        t = text.lower()
        if "изложить" in t and ("новой редакции" in t or "следующей редакции" in t):
            return "replace"
        if "дополнить строк" in t or "дополнить пункт" in t:
            return "add"
        if "исключить" in t or "утратившим" in t:
            return "exclude"
        return "none"

    def flush():
        nonlocal in_target, pending_heading, heading_parts, section
        if not pending_heading:
            return
        if _heading_matches(heading_parts, section_filter):
            in_target = True
            section["name"] = " ".join(heading_parts)
        else:
            in_target = False
        pending_heading = False
        heading_parts = []

    for el in iter_blocks(soup):
        # ---------- div ----------
        if el.name == "div":
            cls = el.get("class") or []
            text = norm(el.get_text(" ", strip=True))
            if not text:
                continue
            if "s2B" in cls and "aC" in cls:      # центрированный жирный заголовок
                heading_parts.append(text)
                pending_heading = True
                continue
            last_div_text = text
            flush()
            continue

        # ---------- table ----------
        flush()
        if not in_target:
            continue
        marker = detect_marker(last_div_text)
        
        # Ловим фразы "исключить" — только внутри ТОС (in_target=True)
        # (это фразы в тексте перед таблицей, но относящиеся к ТОС-разделу)
        if last_div_text and "исключ" in last_div_text.lower() and "изложить" not in last_div_text.lower():
            m = EXCLUDE_PATTERN.search(last_div_text)
            if m:
                district = m.group(1).strip()
                lines = [s.strip() for s in m.group(2).split(",")]
                for line in lines:
                    pending_excluded.append({
                        "status": "excluded",
                        "district": district,
                        "line": line,
                        "note": f"Исключен. - {last_div_text[:100]}",
                    })

        grid = expand_table(el)
        grid = [r for r in grid if any(c for c in r)]
        if not grid:
            continue

        # таблица «Итого по разделу»
        if "Итого по разделу" in grid[0][0]:
            for r in grid:
                if not r:
                    continue
                if "Итого по разделу" in r[0]:
                    if len(r) > 1:
                        section["total"] = parse_amount(r[1])
                    in_target = False
                elif r[0].startswith("("):
                    section["notes"].append(r[0])
            continue

        # строки данных
        last_district = ""
        last_institution = ""
        
        for row in grid:
            if not row or not any(row):
                continue
            joined = " ".join(row)
            if "КонсультантПлюс" in joined or joined.lower().startswith("примечание"):
                continue

            if "Итого по разделу" in row[0]:
                continue

            if "Исключен" in joined:
                section["items"].append({
                    "status": "excluded",
                    "district": row[0] if len(row) > 0 else "",
                    "line": row[1] if len(row) > 1 else "",
                    "note": row[2] if len(row) > 2 else joined,
                })
                continue

            if row[0].startswith("("):          # (в ред. …), (введено …)
                section["notes"].append(joined)
                continue

            row = (row + [""] * N_COLS)[:N_COLS]
            
            # Логика "протягивания" объединенных ячеек
            curr_district = row[0].strip()
            curr_institution = row[2].strip()
            
            if curr_district:
                last_district = curr_district
            else:
                row[0] = last_district
                
            if curr_institution:
                last_institution = curr_institution
            else:
                row[2] = last_institution

            section["items"].append({
                "status": "ok",
                "district": row[0],
                "line": row[1],
                "institution": row[2],
                "works": row[3],
                "responsible": row[4],
                "amount": parse_amount(row[5]),
                "amount_raw": row[5],
                "term": row[6],
                "_marker": marker,
            })

    # Добавляем найденные excluded items в section["items"]
    if pending_excluded:
        section["items"].extend(pending_excluded)
    
    if not section["name"]:
        section["name"] = f"(раздел не найден по фильтру: {section_filter!r})"
    return doc


def to_csv(doc, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Раздел", "Округ", "N строки", "Учреждение",
                    "Виды работ", "Ответственный орган",
                    "Сумма, тыс. руб.", "Сроки", "Статус", "Примечание"])
        for it in doc["section"]["items"]:
            if it["status"] == "excluded":
                w.writerow([doc["section"]["name"], it["district"], it["line"],
                            "", "", "", "", "", "excluded", it["note"]])
            else:
                w.writerow([doc["section"]["name"], it["district"], it["line"],
                            it["institution"], it["works"], it["responsible"],
                            it["amount_raw"], it["term"], "ok", ""])

def _duma_main():
    """CLI: python3 constructor.py duma file.htm [file2.htm ...] -o tos.json --csv tos.csv"""
    ap = argparse.ArgumentParser(
        prog="constructor.py duma",
        description="Парсер раздела про формы участия населения (ТОС) "
                    "из решений городской Думы Краснодара")
    ap.add_argument("files", nargs="+", help=".htm выгрузки КонсультантПлюс")
    ap.add_argument("-o", "--out", help="JSON-файл")
    ap.add_argument("--csv", help="CSV-файл")
    ap.add_argument("--section", default=DEFAULT_SECTION,
                    help=f"ключевая фраза раздела (по умолчанию: {DEFAULT_SECTION!r})")
    args = ap.parse_args(sys.argv[2:])

    docs = [parse_document(p, args.section) for p in args.files]
    data = docs[0] if len(docs) == 1 else docs

    if args.out and args.out != "-":
        Path(args.out).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"JSON: {args.out}", file=sys.stderr)
    elif args.out == "-":
        print(json.dumps(data, ensure_ascii=False, indent=2))

    if args.csv and args.csv != "/dev/null":
        to_csv(docs[0], args.csv)
        print(f"CSV:  {args.csv}", file=sys.stderr)

    if not args.out and not args.csv:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0

# ============================================================
# ТРЕКЕР ИЗМЕНЕНИЙ РАЗДЕЛА ТОС (был в tracker.py)
# ============================================================
FOLDER = Path("Наказы")
OUTPUT_JSON = Path("changes.json")
OUTPUT_HTML = Path("changes.html")
CACHE_DIR = Path(".cache")
PORT = 8765

def parse_cached(path: Path) -> dict:
    CACHE_DIR.mkdir(exist_ok=True)
    mtime = path.stat().st_mtime
    cache = CACHE_DIR / (path.name + ".json")
    if cache.exists():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if data.get("mtime") == mtime:
                return data["doc"]
        except Exception:
            pass
    doc = parse_document(path, DEFAULT_SECTION)
    cache.write_text(
        json.dumps({"mtime": mtime, "doc": doc}, ensure_ascii=False),
        encoding="utf-8",
    )
    return doc


def discover() -> list[dict]:
    sources = []
    for p in sorted(FOLDER.glob("*.htm*")):
        try:
            doc = parse_cached(p)
        except Exception as e:
            print(f"  ⚠ пропуск {p.name}: {e}", file=sys.stderr)
            continue
        meta = doc["meta"]
        section = doc["section"]
        has = bool(section.get("items")) and "не найден" not in (section.get("name") or "")
        if not has:
            continue

        # эффективная дата: у сводной — дата редакции, у изменений — своя
        eff = meta.get("redaction") or meta.get("date")
        try:
            dt = datetime.strptime(eff, "%d.%m.%Y")
        except (TypeError, ValueError):
            dt = datetime.min

        sources.append({
            "path": str(p),
            "file": p.name,
            "date": meta.get("date"),
            "number": meta.get("number"),
            "redaction": meta.get("redaction"),
            "effective": eff,
            "dt": dt,
            "is_consolidated": bool(meta.get("redaction")),
            "doc": doc,
        })
    return sources


def key(it: dict) -> tuple[str, str]:
    return (str(it.get("district", "")).strip(), str(it.get("works", "")).strip())


def by_district(items: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for it in items:
        out.setdefault(key(it)[0] or "(без округа)", []).append(it)
    return out


def compute_diff(before: list[dict], after: list[dict]) -> dict:
    b = {key(it): it for it in before if it["status"] == "ok"}
    a = {key(it): it for it in after if it["status"] == "ok"}
    removed = [b[k] for k in b if k not in a]
    added = [a[k] for k in a if k not in b]
    changed = []
    for k in b:
        if k in a and not items_equal(b[k], a[k]):
            changed.append({"key": k, "before": b[k], "after": a[k]})
    return {"removed": removed, "added": added, "changed": changed}


def items_equal(x: dict, y: dict) -> bool:
    for f in ("institution", "works", "responsible", "amount", "term"):
        if (x.get(f) or "") != (y.get(f) or ""):
            return False
    return True


def amount(it: dict) -> float:
    return float(it.get("amount") or 0)


def build_history(sources: list[dict]) -> dict:
    # 1) выбираем базовую редакцию
    consolidated = [s for s in sources if s["is_consolidated"]]
    if consolidated:
        base = max(consolidated, key=lambda s: s["dt"])
    else:
        base = min(sources, key=lambda s: s["dt"])

    # Берём только ok items — excluded в базе не считаются
    state_items = [
        json.loads(json.dumps(it))
        for it in base["doc"]["section"]["items"]
        if it.get("status") == "ok"
    ]
    state_total = base["doc"]["section"]["total"]

    timeline = [{
        "kind": "base",
        "date": base["date"],
        "number": base["number"],
        "redaction": base["redaction"],
        "file": base["file"],
        "action": "Базовая редакция",
        "total": state_total,
        "items": json.loads(json.dumps(state_items)),
    }]

    # 2) применяем ВСЕ решения по дате (даже те, что старше сводной, чтобы видеть историю)
    subsequent = sorted(
        [s for s in sources if s is not base],
        key=lambda s: s["dt"],
    )
    for src in subsequent:
        change = src["doc"]["section"]
        before_items = json.loads(json.dumps(state_items))
        before_total = state_total

        # ==== УДАЛЕНИЕ ИСКЛЮЧЁННЫХ (status='excluded') ====
        # Из state_items убираем всё, что помечено как "excluded" в этом решении
        # (даже если название не совпадает точно — берём по округу + note)
        excluded_districts = set()
        excluded_items = []
        for it in change["items"]:
            if it.get("status") == "excluded":
                d = str(it.get("district", "")).strip()
                excluded_districts.add(d)
                excluded_items.append(it)
        
        if excluded_items:
            # Удаляем из state_items всё, что в тех же округах, 
            # если название или note содержит "исключ"/"утратил"
            new_state_filtered = []
            for it in state_items:
                dist = key(it)[0]
                if dist in excluded_districts:
                    # Проверяем: может быть, это тот самый item
                    # Берём note из excluded — если в нём упоминается "исключен"
                    works_state = str(it.get("works", "")).lower()
                    matched = False
                    for exc in excluded_items:
                        note = str(exc.get("note", "")).lower()
                        # Если note содержит "исключен" — удаляем ВСЁ в этом округе (полная замена)
                        if "исключен" in note:
                            matched = True
                            break
                    if matched:
                        # Полная замена округа — удалить все старые items этого округа
                        continue
                new_state_filtered.append(it)
            state_items = new_state_filtered
            print(f"DEBUG [{src['date']}]: удалено {len(excluded_items)} excluded items из state")
        
        # ==== УДАЛЕНИЕ EXCLUDED ITEMS ====
        # Если в change есть status='excluded' — удаляем из state_items всё,
        # у кого district "похож" (первые 8 символов после удаления "МИО ").
        excluded_items = [it for it in change["items"] if it.get("status") == "excluded"]
        if excluded_items:
            def _norm_district(d):
                return str(d).lower().replace("мио ", "").replace("n ", "").strip()
            
            excl_keys = set()
            for exc in excluded_items:
                norm = _norm_district(exc.get("district", ""))
                if len(norm) >= 4:
                    excl_keys.add(norm[:8])
            
            if excl_keys:
                new_filtered = []
                for it in state_items:
                    it_norm = _norm_district(it.get("district", ""))
                    if any(k in it_norm[:8] for k in excl_keys):
                        continue  # удаляем — этот округ исключён
                    new_filtered.append(it)
                state_items = new_filtered
        
        # ==== НОВАЯ ЛОГИКА С УЧЁТОМ МАРКЕРОВ ====
        # Группируем items по округам (только status='ok')
        items_by_district = {}
        for it in change["items"]:
            if it["status"] != "ok":
                continue
            d = key(it)[0]
            items_by_district.setdefault(d, []).append(it)
        
        # DEBUG: что видит build_history для каждого решения
        if "Галушко" in str(change["items"]) or any("Галушко" in str(it.get("district","")) for it in change["items"]):
            for it in change["items"]:
                if "Галушко" in str(it.get("district","")):
                    print(f"  marker={it.get('_marker', 'НЕТ')} works={it.get('works','')[:50]}")
        
        new_state = list(state_items)
        for d, items in items_by_district.items():
            markers = {it.get("_marker", "none") for it in items}
            
            if "replace" in markers:
                # Полная замена округа: удалить все старые items этого округа
                new_state = [it for it in new_state if key(it)[0] != d]
                new_state.extend(items)
            elif "add" in markers:
                # Точечное добавление: заменить совпадающие + добавить новые
                keys = {key(it) for it in items}
                new_state = [it for it in new_state if key(it) not in keys]
                new_state.extend(items)
            else:
                # "none" или "exclude" — старое поведение (замена по ключу)
                keys = {key(it) for it in items}
                new_state = [it for it in new_state if key(it) not in keys]
                new_state.extend(items)
        
        # DEBUG: считаем Галушко до и после replace
        
        state_items = new_state
        added = [it for it in change["items"] if it["status"] == "ok"]
        kept = []  # для совместимости с compute_diff
        state_total = change["total"]

        diff = compute_diff(before_items, state_items)

        # сводка по округам
        per_district: dict[str, dict] = {}
        for it in diff["removed"]:
            d = key(it)[0] or "(без округа)"
            per_district.setdefault(d, {"removed": 0, "removed_sum": 0.0,
                                        "added": 0, "added_sum": 0.0,
                                        "changed": 0, "changed_delta": 0.0})
            per_district[d]["removed"] += 1
            per_district[d]["removed_sum"] += amount(it)
        for it in diff["added"]:
            d = key(it)[0] or "(без округа)"
            per_district.setdefault(d, {"removed": 0, "removed_sum": 0.0,
                                        "added": 0, "added_sum": 0.0,
                                        "changed": 0, "changed_delta": 0.0})
            per_district[d]["added"] += 1
            per_district[d]["added_sum"] += amount(it)
        for c in diff["changed"]:
            d = key(c["before"])[0] or "(без округа)"
            per_district.setdefault(d, {"removed": 0, "removed_sum": 0.0,
                                        "added": 0, "added_sum": 0.0,
                                        "changed": 0, "changed_delta": 0.0})
            per_district[d]["changed"] += 1
            per_district[d]["changed_delta"] += amount(c["after"]) - amount(c["before"])

        timeline.append({
            "kind": "amendment",
            "date": src["date"],
            "number": src["number"],
            "file": src["file"],
            "action": "Изменения",
            "total_before": before_total,
            "total_after": state_total,
            "delta_total": (state_total or 0) - (before_total or 0),
            "diff": diff,
            "per_district": per_district,
            "items": json.loads(json.dumps(state_items)),
        })

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "section_name": base["doc"]["section"]["name"],
        "sources": [
            {"file": s["file"], "date": s["date"], "number": s["number"],
             "redaction": s["redaction"], "effective": s["effective"],
             "kind": "base" if s is base else "amendment"}
            for s in [base] + subsequent
        ],
        "timeline": timeline,
        "final_total": state_total,
        "final_items": [it for it in state_items if it.get("status") == "ok"],
    }


def esc(v) -> str:
    return html.escape(str(v if v is not None else ""))


def fmt_money(v) -> str:
    if v is None:
        return "—"
    return f"{v:,.1f}".replace(",", " ").replace(".", ",")


def render_items_table(items: list[dict]) -> str:
    rows = []
    for it in items:
        rows.append(
            "<tr>"
            f"<td>{esc(it.get('district'))}</td>"
            f"<td>{esc(it.get('line'))}</td>"
            f"<td>{esc(it.get('institution'))}</td>"
            f"<td>{esc(it.get('works'))}</td>"
            f"<td class='num'>{fmt_money(it.get('amount'))}</td>"
            f"<td>{esc(it.get('term'))}</td>"
            "</tr>"
        )
    return (
        "<table class='tbl'>"
        "<thead><tr><th>Округ</th><th>N стр.</th><th>Учреждение</th>"
        "<th>Виды работ</th><th>Сумма</th><th>Срок</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_diff_block(diff: dict) -> str:
    parts = []
    for title, css, items in (
        ("Удалено", "removed", diff["removed"]),
        ("Добавлено", "added", diff["added"]),
        ("Изменено", "changed", diff["changed"]),
    ):
        if title == "Изменено":
            if not items:
                continue
            parts.append(f"<h4 class='diff-h {css}'>✏️ {title} ({len(items)})</h4>")
            rows = []
            for c in items:
                b, a = c["before"], c["after"]
                rows.append(
                    "<tr>"
                    f"<td>{esc(b.get('district'))}</td>"
                    f"<td>{esc(b.get('line'))}</td>"
                    f"<td>{esc(b.get('institution'))}</td>"
                    f"<td>{esc(b.get('works'))}</td>"
                    f"<td class='num'>{fmt_money(b.get('amount'))} → {fmt_money(a.get('amount'))}</td>"
                    f"<td>{esc(b.get('term'))} → {esc(a.get('term'))}</td>"
                    "</tr>"
                )
            parts.append(
                "<table class='tbl'>"
                "<thead><tr><th>Округ</th><th>N стр.</th><th>Учреждение</th>"
                "<th>Виды работ</th><th>Сумма было → стало</th><th>Срок было → стало</th></tr></thead>"
                f"<tbody>{''.join(rows)}</tbody></table>"
            )
        else:
            if not items:
                continue
            icon = "🗑" if css == "removed" else "➕"
            parts.append(f"<h4 class='diff-h {css}'>{icon} {title} ({len(items)})</h4>")
            parts.append(render_items_table(items))
    return "".join(parts) if parts else "<p class='muted'>Изменений нет.</p>"


def render_per_district(per: dict) -> str:
    if not per:
        return ""
    rows = []
    for d in sorted(per):
        r = per[d]
        delta = r["added_sum"] - r["removed_sum"] + r["changed_delta"]
        delta_cls = "up" if delta > 0 else ("down" if delta < 0 else "")
        rows.append(
            "<tr>"
            f"<td>{esc(d)}</td>"
            f"<td class='num'>{r['removed']}</td>"
            f"<td class='num'>{fmt_money(r['removed_sum'])}</td>"
            f"<td class='num'>{r['added']}</td>"
            f"<td class='num'>{fmt_money(r['added_sum'])}</td>"
            f"<td class='num'>{r['changed']}</td>"
            f"<td class='num {delta_cls}'>{('+' if delta > 0 else '')}{fmt_money(delta)}</td>"
            "</tr>"
        )
    return (
        "<table class='tbl compact'>"
        "<thead><tr><th>Округ</th><th>Удал.</th><th>Сумма удал.</th>"
        "<th>Доб.</th><th>Сумма доб.</th><th>Изм.</th><th>Δ суммы</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_html(data: dict) -> str:
    timeline_html = []
    # базовая редакция
    for step in data["timeline"]:
        if step["kind"] == "base":
            timeline_html.append(
                "<article class='event base'>"
                "<div class='event-head'>"
                f"<span class='date'>{esc(step['date'])}</span>"
                f"<span class='tag base'>Базовая редакция</span>"
                f"<h3>N {esc(step['number'])} — {esc(step['action'])}</h3>"
                "</div>"
                f"<div class='event-meta'>Итог: <b>{fmt_money(step['total'])}</b> тыс. руб.</div>"
                "<details><summary>Показать все строки (" + str(len(step['items'])) + ")</summary>"
                f"{render_items_table([i for i in step['items'] if i['status']=='ok'])}"
                "</details>"
                "</article>"
            )
        else:
            dt = step["delta_total"]
            cls = "up" if dt > 0 else ("down" if dt < 0 else "")
            timeline_html.append(
                "<article class='event amendment'>"
                "<div class='event-head'>"
                f"<span class='date'>{esc(step['date'])}</span>"
                f"<span class='tag change'>Изменения</span>"
                f"<h3>N {esc(step['number'])}</h3>"
                "</div>"
                f"<div class='event-meta'>Итого: {fmt_money(step['total_before'])} → "
                f"<b>{fmt_money(step['total_after'])}</b> "
                f"<span class='delta {cls}'>({('+' if dt>0 else '')}{fmt_money(dt)})</span></div>"
                f"<details><summary>Изменения по округам</summary>"
                f"{render_per_district(step['per_district'])}"
                "</details>"
                "<details open>"
                f"<summary>Подробно по строкам</summary>"
                f"{render_diff_block(step['diff'])}"
                "</details>"
                "</article>"
            )

    final_ok = [i for i in data["final_items"] if i["status"] == "ok"]
    sources_rows = "".join(
        f"<tr><td>{esc(s['date'])}</td><td>N {esc(s['number'])}</td>"
        f"<td>{esc(s['file'])}</td><td>{'сводная' if s['kind']=='base' else 'изменения'}</td></tr>"
        for s in data["sources"]
    )

    js_data = json.dumps({
        "final_total": data["final_total"],
        "final_items": final_ok,
    }, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Раздел ТОС — изменения</title>
<style>
  :root {{
    --bg: #f7f8fa; --card: #fff; --text: #1f2328; --muted: #656d76;
    --border: #d8dee4; --base: #0969da; --change: #9a6700;
    --up: #cf222e; --down: #1a7f37; --add-bg: #dafbe1; --rem-bg: #ffebe9; --chg-bg: #fff8c5;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#0d1117; --card:#161b22; --text:#e6edf3; --muted:#8b949e;
      --border:#30363d; --base:#58a6ff; --change:#d29922;
      --up:#f85149; --down:#3fb950; --add-bg:#04260f; --rem-bg:#3d0d0d; --chg-bg:#3a2d00; }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: 0; font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
    background: var(--bg); color: var(--text); font-size: 14px; line-height: 1.5; }}
  header {{ background: var(--card); border-bottom: 1px solid var(--border); padding: 16px 24px; position: sticky; top: 0; z-index: 10; }}
  header h1 {{ margin: 0 0 8px; font-size: 20px; }}
  .summary {{ display: flex; flex-wrap: wrap; gap: 20px; font-size: 13px; }}
  .summary b {{ font-size: 16px; }}
  .actions {{ margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap; }}
  button, .actions a {{ padding: 6px 12px; border: 1px solid var(--border); background: var(--card);
    color: var(--text); border-radius: 6px; cursor: pointer; font-size: 13px; text-decoration: none; }}
  button:hover, .actions a:hover {{ background: var(--bg); }}
  main {{ max-width: 1100px; margin: 0 auto; padding: 16px 24px 60px; }}
  .filter {{ display: flex; gap: 16px; align-items: center; padding: 12px 0; flex-wrap: wrap; }}
  .filter label {{ font-size: 13px; display: flex; align-items: center; gap: 6px; }}
  .filter select {{ padding: 4px 8px; border: 1px solid var(--border); border-radius: 6px; background: var(--card); color: var(--text); }}
  .event {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 14px 18px; margin-bottom: 16px; }}
  .event.base {{ border-left: 4px solid var(--base); }}
  .event.amendment {{ border-left: 4px solid var(--change); }}
  .event-head {{ display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-bottom: 6px; }}
  .event-head h3 {{ margin: 0; font-size: 15px; }}
  .date {{ font-size: 13px; color: var(--muted); font-variant-numeric: tabular-nums; }}
  .tag {{ padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }}
  .tag.base {{ background: #ddf4ff; color: var(--base); }}
  .tag.change {{ background: #fff8c5; color: var(--change); }}
  @media (prefers-color-scheme: dark) {{
    .tag.base {{ background: #0c2d6b; }} .tag.change {{ background: #3a2d00; }}
  }}
  .event-meta {{ font-size: 13px; color: var(--muted); margin-bottom: 10px; }}
  .event-meta b {{ color: var(--text); }}
  .delta {{ font-weight: 600; }}
  .delta.up {{ color: var(--up); }}
  .delta.down {{ color: var(--down); }}
  details {{ margin-top: 8px; }}
  summary {{ cursor: pointer; font-size: 13px; color: var(--muted); padding: 4px 0; user-select: none; }}
  summary:hover {{ color: var(--text); }}
  .tbl {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 8px; }}
  .tbl th, .tbl td {{ border: 1px solid var(--border); padding: 6px 8px; text-align: left; vertical-align: top; }}
  .tbl th {{ background: var(--bg); font-weight: 600; }}
  .tbl td.num {{ text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }}
  .tbl.compact td, .tbl.compact th {{ padding: 4px 6px; }}
  .diff-h {{ font-size: 13px; margin: 12px 0 4px; }}
  .diff-h.removed {{ color: var(--up); }}
  .diff-h.added {{ color: var(--down); }}
  .diff-h.changed {{ color: var(--change); }}
  .muted {{ color: var(--muted); }}
  .num.up {{ color: var(--up); }}
  .num.down {{ color: var(--down); }}
  .hint {{ font-size: 12px; color: var(--muted); margin-top: 8px; }}
</style>
</head>
<body>
<header>
  <h1>Раздел ТОС — история изменений</h1>
  <div class="summary">
    <div>Итого: <b>{fmt_money(data['final_total'])}</b> тыс. руб.</div>
    <div>Строк: <b>{len(final_ok)}</b></div>
    <div>Решений в истории: <b>{len(data['timeline'])}</b></div>
    <div>Обновлено: <b>{esc(data['generated_at'])}</b></div>
  </div>
  <div class="actions">
    <button onclick="location.reload()">↻ Обновить страницу</button>
    <button id="rescan" onclick="rescan()">📡 Пересканировать папку</button>
    <a href="changes.json" download>💾 Скачать JSON</a>
  </div>
  <div class="hint" id="hint"></div>
</header>
<main>
  <details>
    <summary>📂 Обработанные файлы ({len(data['sources'])})</summary>
    <table class="tbl compact">
      <thead><tr><th>Дата</th><th>N</th><th>Файл</th><th>Тип</th></tr></thead>
      <tbody>{sources_rows}</tbody>
    </table>
  </details>

  <div class="filter">
    <label>Округ:
      <select id="filter-district">
        <option value="">все</option>
      </select>
    </label>
    <label><input type="checkbox" id="only-changes"> только изменения</label>
  </div>

  <section class="timeline">
    {''.join(timeline_html)}
  </section>
</main>
<script>
const DATA = {js_data};

// заполнить фильтр округов
const districts = new Set();
DATA.final_items.forEach(i => districts.add((i.district||'').trim() || '(без округа)'));
const sel = document.getElementById('filter-district');
[...districts].sort().forEach(d => {{
  const o = document.createElement('option'); o.value = d; o.textContent = d; sel.appendChild(o);
}});

function applyFilter() {{
  const d = sel.value;
  const onlyChanges = document.getElementById('only-changes').checked;
  document.querySelectorAll('.tbl tbody tr').forEach(tr => {{
    const dd = tr.cells[0] ? tr.cells[0].textContent.trim() : '';
    let show = !d || dd === d;
    if (show && onlyChanges) {{
      const parentEvent = tr.closest('.event');
      if (parentEvent && parentEvent.classList.contains('base')) show = false;
    }}
    tr.style.display = show ? '' : 'none';
  }});
}}
sel.addEventListener('change', applyFilter);
document.getElementById('only-changes').addEventListener('change', applyFilter);

async function rescan() {{
  const hint = document.getElementById('hint');
  if (location.protocol === 'file:') {{
    hint.textContent = 'Открыто как файл. Запустите в терминале: python3 tracker.py serve';
    return;
  }}
  hint.textContent = 'Сканирую папку…';
  try {{
    const r = await fetch('/refresh', {{method: 'POST'}});
    if (r.ok) {{ location.reload(); }}
    else {{ hint.textContent = 'Ошибка: ' + r.status; }}
  }} catch (e) {{ hint.textContent = 'Ошибка: ' + e; }}
}}
</script>
</body>
</html>"""


def scan() -> bool:
    print(f"📂 Сканирую {FOLDER}/ …")
    sources = discover()
    if not sources:
        print("  ⚠ Не найдено ни одного решения с разделом ТОС", file=sys.stderr)
        return False
    print(f"  ✓ Найдено {len(sources)} решений с разделом ТОС")
    for s in sources:
        print(f"     • {s['date']}  N {s['number']:<8} "
              f"{'(сводная от ' + s['redaction'] + ')' if s['is_consolidated'] else '(изменения)':<24}  "
              f"{s['file']}")

    data = build_history(sources)
    OUTPUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    OUTPUT_HTML.write_text(render_html(data), encoding="utf-8")
    print(f"  ✓ changes.json — история из {len(data['timeline'])} шагов")
    print(f"  ✓ changes.html — наглядный отчёт")
    print(f"  ✓ Итог: {fmt_money(data['final_total'])} тыс. руб., строк: "
          f"{sum(1 for i in data['final_items'] if i['status']=='ok')}")
    return True


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in ("/", "/index.html", "/changes.html"):
            if not OUTPUT_HTML.exists():
                scan()
            body = OUTPUT_HTML.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/changes.json":
            body = OUTPUT_JSON.read_bytes() if OUTPUT_JSON.exists() else b"{}"
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def do_POST(self):
        if urlsplit(self.path).path == "/refresh":
            try:
                scan()
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"OK")
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Length", str(len(str(e))))
                self.end_headers()
                self.wfile.write(str(e).encode())
        else:
            self.send_error(404)


def serve():
    if not scan():
        return 1
    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}/"
    print(f"\n🌐 Открываю {url}")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    print("   Ctrl+C — остановить\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Остановлено")
    return 0

def _tracker_cli():
    """CLI: python3 constructor.py tracker [scan|serve|open]"""
    ap = argparse.ArgumentParser(prog="constructor.py tracker",
                                 description="Трекер изменений раздела ТОС")
    ap.add_argument("command", nargs="?", default="open",
                    choices=["scan", "serve", "open"])
    args = ap.parse_args(sys.argv[2:])

    if args.command == "scan":
        return 0 if scan() else 1
    if args.command == "serve":
        return serve()
    # open: scan + открыть файл
    if not scan():
        return 1
    webbrowser.open(OUTPUT_HTML.resolve().as_uri())
    print(f"\n🌐 Открыт {OUTPUT_HTML.resolve()}")
    return 0

# ============================================================
# ПУТИ И КОНФИГ
# ============================================================
CONFIG_DIR = Path.home() / ".config" / "constructor"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = CONFIG_DIR / "settings.json"

def load_config():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

def _hash_password(pw: str):
    salt = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, 100_000)
    return base64.b64encode(salt).decode(), base64.b64encode(h).decode()

def verify_password(pw: str, salt_b64: str, hash_b64: str) -> bool:
    try:
        salt = base64.b64decode(salt_b64)
        h = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, 100_000)
        return base64.b64encode(h).decode() == hash_b64
    except Exception:
        return False

def get_work_dir():
    cfg = load_config()
    p = cfg.get("work_dir")
    if p and Path(p).exists() and os.access(p, os.W_OK):
        return Path(p)
    return None

def ensure_work_dirs(work_dir):
    (work_dir / "Сохранения").mkdir(parents=True, exist_ok=True)
    return work_dir / "Сохранения", work_dir / "data.json"

# ============================================================
# ФОРМАТИРОВАНИЕ
# ============================================================
def fmt(n):
    if n is None: return "—"
    return f"{n:,.1f}".replace(",", " ").replace(".", ",")

def fmt_tbl(n):
    if n is None: 
        return "—"
    s = f"{n:,.3f}".replace(",", " ").replace(".", ",")
    if "," not in s: 
        s += ",0"
    if "," in s:
        s = s.rstrip("0").rstrip(",")
    return s


def normalize_name(s):
    """Нормализует название для сравнения: нижний регистр, ё→е, ё→е, убирает лишние пробелы."""
    if not s:
        return ""
    return re.sub(r"\s+", " ", s.lower().replace("ё", "е").replace("Ё", "Е")).strip()

# ============================================================
# МОДЕЛЬ
# ============================================================
def make_base_edition():
    return {"id":"base","date":"2026-01-01","label":"Начальная (01.01.2026)","note":"2026 = 44 355,0 · 1.1.3 отсутствует","changes":{"e_1_1_3":{"2026":0.0,"2027":0.0,"2028":0.0}},"renames":{},"added":[],"deleted":[],"preset":True}

def make_preset_edition(p):
    return {"id":p["id"],"date":p["date"],"label":p["label"],"note":p["note"],"changes":json.loads(json.dumps(p["changes"])),"renames":{},"added":[],"deleted":[],"preset":True}

def default_data():
    eds = [make_base_edition()] + [make_preset_edition(p) for p in PRESET_EDITIONS]
    return {"editions":eds,"base_overrides":{},"prog_overrides":{"other":{}}}

def atomic_write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp_", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try: os.remove(tmp)
        except Exception: pass
        raise

def get_effective_events(data, ed_idx):
    import re as _re
    deleted = set()
    added = []
    for i in range(1, ed_idx + 1):
        if i >= len(data["editions"]):
            break
        deleted |= set(data["editions"][i].get("deleted", []))
        added.extend(data["editions"][i].get("added", []))
    result = [e for e in EVENTS if e["id"] not in deleted]

    def _num(ev):
        m = _re.match(r"^e_(\d+(?:_\d+)*)$", str(ev.get("id", "")))
        if m:
            return tuple(int(x) for x in m.group(1).split("_"))
        m2 = _re.search(r"\d+(?:[.,]\d+)?", str(ev.get("name", "")))
        if m2:
            s = m2.group(0).replace(",", ".")
            if "." in s:
                return tuple(int(x) for x in s.split("."))
            return (int(s),)
        return None

    def _sib(n):
        return n if n is not None else ()

    for ev in added:
        # Добавляем is_custom для новых мероприятий
        if "is_custom" not in ev:
            ev["is_custom"] = True
        n = _num(ev)
        parent = ev.get("parent")
        at = None
        if n is not None:
            for i, b in enumerate(result):
                if b.get("parent") != parent:
                    continue
                bn = _num(b)
                if bn is not None and _sib(bn) > _sib(n):
                    at = i
                    break
        if at is None:
            last = None
            for i, b in enumerate(result):
                if b.get("parent") == parent:
                    last = i
            at = (last + 1) if last is not None else len(result)
        result.insert(at, ev)
    return result


def get_effective_name(ev, data, ed_idx):
    name = ev["name"]
    for i in range(1, ed_idx + 1):
        r = data["editions"][i].get("renames", {}).get(ev["id"])
        if r: name = r
    return name

def get_event_value_at(ev, year, data, ed_idx):
    year_s = str(year)
    if ev.get("is_aggregate"):
        total = 0.0
        for child in get_effective_events(data, ed_idx):
            if child.get("parent") == ev["id"]:
                total += get_event_value_at(child, year, data, ed_idx)
        return round(total, 1)

    base_ov = data.get("base_overrides", {}).get(ev["id"], {})
    if year_s in base_ov:
        val = float(base_ov[year_s])
    else:
        val = float(ev.get("years", {}).get(year_s, ev.get("old_value", 0.0)))
    for k in range(1, ed_idx + 1):
        if k >= len(data["editions"]): break
        c = data["editions"][k].get("changes", {}).get(ev["id"])
        if c is None: continue
        if isinstance(c, (int, float)):
            val = float(c)
        elif isinstance(c, dict) and c.get(year_s) is not None:
            try: val = float(c[year_s])
            except Exception: pass
    return round(val, 1)

def get_base_value(ev, year, data):
    return get_event_value_at(ev, year, data, 0)

def get_event_sum_at(year, data, ed_idx):
    total = 0.0
    for ev in get_effective_events(data, ed_idx):
        if ev.get("parent"): continue
        total += get_event_value_at(ev, year, data, ed_idx)
    return round(total, 1)

def get_sub2_year_at(year, data, ed_idx):
    if 2026 <= year <= 2028:
        return get_event_sum_at(year, data, ed_idx)
    return round(float(SUB2_YEARS.get(str(year), 0.0)), 1)

def get_sub2_total_at(data, ed_idx):
    return round(sum(get_sub2_year_at(y, data, ed_idx) for y in SUM_YEARS), 1)

def get_other_sub_value(key, data):
    ov = data.get("prog_overrides", {}).get("other", {})
    if key in ov: return round(float(ov[key]), 1)
    return round(OTHER_SUBPROGRAMS[key][1], 1)

def get_other_sub_sum(data):
    return round(sum(get_other_sub_value(k, data) for k in OTHER_SUBPROGRAMS), 1)

def get_program_total_at(data, ed_idx):
    return round(get_sub2_total_at(data, ed_idx) + get_other_sub_sum(data), 1)

def check_aggregate_consistency(data, ed_idx, year=2026):
    if ed_idx <= 0:
        return None, None, None
    year_s = str(year)
    official = None
    for j in range(1, ed_idx + 1):
        if j >= len(data["editions"]):
            break
        c = data["editions"][j].get("changes", {}).get("e_1_1_3", "__undef__")
        if c == "__undef__":
            continue
        if c is None:
            official = None
        elif isinstance(c, dict) and year_s in c and c[year_s] is not None:
            try:
                official = float(c[year_s])
            except Exception:
                pass

    computed = 0.0
    for ev in get_effective_events(data, ed_idx):
        if ev.get("parent") == "e_1_1_3":
            computed += get_event_value_at(ev, year, data, ed_idx)
    computed = round(computed, 1)
    if official is None:
        return None, computed, None
    return official, computed, round(official - computed, 1)


def get_unit_label(ev):
    if ev.get("source") == "table3":
        m = re.search(r"п\.\s*(\d+)\.(\d+)\.(\d+)", ev["name"])
        if m:
            a, b, c = m.groups()
            return f"В подпункте {a}.{b}.{c} подпункта {a}.{b} пункта {a} таблицы 3 приложения к Подпрограмме № 2 Программы"
        return "В таблице 3 приложения к Подпрограмме № 2 Программы"
    m2 = re.search(r"п\.\s*(\d+)\.(\d+)\s*«", ev["name"])
    if m2:
        g = GROUPS_DICT.get(ev.get("group", ""), "")
        return f"В подпункте {m2.group(1)}.{m2.group(2)} раздела «{g}» таблицы 3 приложения № 3 к Подпрограмме № 2 Программы"
    return "В таблице 3 приложения № 3 к Подпрограмме № 2 Программы"

def generate_items(data, ed_idx, year):
    items = []
    order = [0]

    progB = get_program_total_at(data, ed_idx - 1)
    progA = get_program_total_at(data, ed_idx)
    subTB = get_sub2_total_at(data, ed_idx - 1)
    subTA = get_sub2_total_at(data, ed_idx)
    subYB = get_sub2_year_at(year, data, ed_idx - 1)
    subYA = get_sub2_year_at(year, data, ed_idx)
    sumB = get_event_sum_at(year, data, ed_idx - 1)
    sumA = get_event_sum_at(year, data, ed_idx)

    if abs(subTA - subTB) > 0.0001:
        items.append({"kind":"digits","weight":progA,"order":order[0],
            "lead":"В абзаце «Объёмы и источники финансирования муниципальной программы, в том числе на финансовое обеспечение муниципальных проектов» Паспорта Программы:",
            "lines":[f"цифры «{fmt(progB)}» заменить цифрами «{fmt(progA)}»."]}); order[0] += 1
        items.append({"kind":"digits","weight":subTA,"order":order[0],
            "lead":"В абзаце «Объёмы и источники финансирования подпрограммы, в том числе на финансовое обеспечение муниципальных проектов» паспорта Подпрограммы № 2 Программы:",
            "lines":[f"цифры «{fmt(subTB)}» заменить цифрами «{fmt(subTA)}»;", f"цифры «{fmt(subYB)}» заменить цифрами «{fmt(subYA)}»."]}); order[0] += 1
        items.append({"kind":"paragraph","weight":subTA,"order":order[0],
            "text":f"В абзаце первом раздела IV «Обоснование ресурсного обеспечения подпрограммы» Подпрограммы № 2 Программы цифры «{fmt(subTB)}» заменить цифрами «{fmt(subTA)}»."}); order[0] += 1
        line1 = f"цифры «{fmt(subYB)}» заменить цифрами «{fmt(subYA)}»"
        line2 = f"цифры «{fmt(sumB)}» заменить цифрами «{fmt(sumA)}»"
        lines = [line1 + "."] if line1 == line2 else [line1 + ";", line2 + "."]
        items.append({"kind":"digits","weight":subYA,"order":order[0],
            "lead":"В таблице 3 раздела IV «Обоснование ресурсного обеспечения подпрограммы» Подпрограммы № 2 Программы:",
            "lines":lines}); order[0] += 1

    deleted_ids = set()
    for k in range(1, ed_idx + 1):
        if k >= len(data["editions"]): break
        deleted_ids |= set(data["editions"][k].get("deleted", []))

    # ============================================================
    # 1. TABLE3 — поштучно
    # ============================================================
    for ev in get_effective_events(data, ed_idx):
        if ev.get("is_aggregate"): continue
        if ev["id"] in deleted_ids: continue
        if ev.get("source") != "table3": continue
        
        is_new = bool(ev.get("is_custom"))
        old_name = get_effective_name(ev, data, ed_idx - 1)
        new_name = get_effective_name(ev, data, ed_idx)
        renamed = old_name != new_name
        b = get_event_value_at(ev, year, data, ed_idx - 1)
        a = get_event_value_at(ev, year, data, ed_idx)
        value_changed = abs(a - b) > 0.0001

        if is_new:
            eff_name = get_effective_name(ev, data, ed_idx)
            m = re.search(r"п\.\s*(\d+(?:\.\d+){1,2})", eff_name)
            sub = m.group(1) if m else ""
            items.append({"kind":"table","weight":a + 0.001,"order":order[0],
                "lead":f"{get_unit_label(ev)} дополнить подпунктом {sub} следующего содержания:",
                "table_data":get_table_data(ev, a, data, ed_idx, year)}); order[0] += 1
            continue
        if renamed:
            items.append({"kind":"paragraph","weight":a,"order":order[0],
                "text":f"{get_unit_label(ev)} слова «{old_name}» заменить словами «{new_name}»."}); order[0] += 1
        if value_changed:
            items.append({"kind":"table","weight":a,"order":order[0],
                "lead":f"{get_unit_label(ev)} изложить в следующей редакции:",
                "table_data":get_table_data(ev, a, data, ed_idx, year)}); order[0] += 1

    # ============================================================
    # 2. APP3 — группируем по group
    # ============================================================
    groups_changed = {}
    for ev in get_effective_events(data, ed_idx):
        if ev.get("is_aggregate"): continue
        if ev["id"] in deleted_ids: continue
        if ev.get("source") != "app3": continue
        
        group = ev.get("group")
        if not group: continue
        
        is_new = bool(ev.get("is_custom"))
        old_name = get_effective_name(ev, data, ed_idx - 1)
        new_name = get_effective_name(ev, data, ed_idx)
        renamed = old_name != new_name
        b = get_event_value_at(ev, year, data, ed_idx - 1)
        a = get_event_value_at(ev, year, data, ed_idx)
        value_changed = abs(a - b) > 0.0001
        
        if is_new or renamed or value_changed:
            if group not in groups_changed:
                groups_changed[group] = {"max_amount": 0.0, "representative": ev}
            if a > groups_changed[group]["max_amount"]:
                groups_changed[group]["max_amount"] = a
                groups_changed[group]["representative"] = ev

    for group in sorted(groups_changed.keys(), key=lambda g: -groups_changed[g]["max_amount"]):
        rep_ev = groups_changed[group]["representative"]
        max_amt = groups_changed[group]["max_amount"]
        
        # Ищем МИНИМАЛЬНЫЙ номер среди изменённых мероприятий этой группы
        # (например, 7.4, а не 7.5 — хотя у 7.5 сумма больше)
        min_num = None
        for ev_ch in get_effective_events(data, ed_idx):
            if ev_ch.get("group") != group: continue
            if ev_ch.get("parent") != "e_1_1_3": continue
            if ev_ch["id"] in deleted_ids: continue
            
            # ПРОВЕРЯЕМ, ЧТО МЕРОПРИЯТИЕ ДЕЙСТВИТЕЛЬНО ИЗМЕНИЛОСЬ
            is_new_ch = bool(ev_ch.get("is_custom"))
            old_name_ch = get_effective_name(ev_ch, data, ed_idx - 1)
            new_name_ch = get_effective_name(ev_ch, data, ed_idx)
            renamed_ch = old_name_ch != new_name_ch
            b_ch = get_event_value_at(ev_ch, year, data, ed_idx - 1)
            a_ch = get_event_value_at(ev_ch, year, data, ed_idx)
            value_changed_ch = abs(a_ch - b_ch) > 0.0001
            
            if not (is_new_ch or renamed_ch or value_changed_ch):
                continue  # не изменялось — пропускаем
            
            m = re.search(r"п\.\s*(\d+\.\d+)", get_effective_name(ev_ch, data, ed_idx))
            if not m: continue
            num_str = m.group(1)
            try:
                num_tuple = tuple(int(x) for x in num_str.split("."))
            except ValueError:
                continue
            if min_num is None or num_tuple < min_num[0]:
                min_num = (num_tuple, num_str)
        
        num = min_num[1] if min_num else ""
        lead = f"В подпункте {num} раздела «{GROUPS_DICT.get(group, '')}» таблицы 3 приложения № 3 к Подпрограмме № 2 Программы изложить в следующей редакции:"
        
        items.append({"kind":"table","weight":max_amt,"order":order[0],
            "lead":lead,
            "table_data":get_table_data(rep_ev, max_amt, data, ed_idx, year)}); order[0] += 1

    # ============================================================
    # 3. АГРЕГАТ 1.1.3
    # ============================================================
    agg = {"id":"e_1_1_3","is_aggregate":True}
    aggB = get_event_value_at(agg, year, data, ed_idx - 1)
    aggA = get_event_value_at(agg, year, data, ed_idx)
    if abs(aggA - aggB) > 0.0001:
        items.append({"kind":"paragraph","weight":aggA,"order":order[0],
            "text":f"В подпункте 1.1.3 подпункта 1.1 пункта 1 таблицы 3 приложения к Подпрограмме № 2 Программы цифры «{fmt(aggB)}» заменить цифрами «{fmt(aggA)}»."}); order[0] += 1

    items.sort(key=lambda it: (-it["weight"], it["order"]))
    return items

def get_table_data(ev, new_value, data, ed_idx, sel_year):
    if ev.get("source") == "table3":
        vals = [(new_value if y == sel_year else get_event_value_at(ev, y, data, ed_idx)) for y in YEAR_LIST]
        total = sum(vals)
        rows = [["Всего", fmt_tbl(total), fmt_tbl(total)]]
        for y, v in zip(YEAR_LIST, vals):
            rows.append([str(y), fmt_tbl(v), fmt_tbl(v)])
        return {"columns":[30,35,35],"rows":rows}
    else:
        group = ev.get("group")
        rows = []
        for e in get_effective_events(data, ed_idx):
            if e.get("group") == group and e.get("parent") == "e_1_1_3":
                m = re.search(r"п\.\s*(\d+\.\d+)\s*«([^»]+)»", e["name"])
                val = get_event_value_at(e, sel_year, data, ed_idx)
                rows.append([
                    (m.group(1) + ".") if m else "",
                    m.group(2) if m else e["name"],
                    fmt_tbl(val),
                    e.get("executor", ""),
                ])
        return {"columns":[8,44,16,32],"rows": rows}

# ============================================================
# XML-БЛОКИ DOCX
# ============================================================
NBSP = "\u00a0"

_DOCX_PARTS = {
    "styles.xml": r"""<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
        <w:color w:val="000000"/>
        <w:spacing w:val="0"/>
        <w:sz w:val="28"/>
      </w:rPr>
    </w:rPrDefault>
    <w:pPrDefault>
      <w:pPr>
        <w:widowControl w:val="1"/>
        <w:spacing w:after="0" w:before="0" w:line="276" w:lineRule="auto"/>
        <w:ind w:firstLine="0" w:left="0" w:right="0"/>
        <w:jc w:val="both"/>
      </w:pPr>
    </w:pPrDefault>
  </w:docDefaults>
  <w:style w:default="1" w:styleId="Normal" w:type="paragraph">
    <w:name w:val="Normal"/>
    <w:qFormat/>
  </w:style>
</w:styles>
""",
    "header1.xml": r"""<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:p>
    <w:pPr><w:jc w:val="center"/><w:spacing w:after="0"/></w:pPr>
    <w:r><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:sz w:val="24"/></w:rPr>
      <w:fldChar w:fldCharType="begin"/></w:r>
    <w:r><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:sz w:val="24"/></w:rPr>
      <w:instrText>PAGE</w:instrText></w:r>
    <w:r><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:sz w:val="24"/></w:rPr>
      <w:fldChar w:fldCharType="separate"/></w:r>
    <w:r><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:sz w:val="24"/></w:rPr>
      <w:t>2</w:t></w:r>
    <w:r><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:sz w:val="24"/></w:rPr>
      <w:fldChar w:fldCharType="end"/></w:r>
  </w:p>
</w:hdr>
""",
    "fontTable.xml": r"""<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<w:fonts xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:font w:name="Times New Roman">
    <w:panose1 w:val="02020603050405020304"/><w:charset w:val="00"/>
    <w:family w:val="roman"/><w:pitch w:val="variable"/>
  </w:font>
</w:fonts>
""",
    "settings.xml": r"""<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:defaultTabStop w:val="720"/>
  <w:compat>
    <w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/>
  </w:compat>
</w:settings>
""",
    "webSettings.xml": r"""<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<w:webSettings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:allowPNG/><w:doNotSaveAsSingleFile/>
</w:webSettings>
""",
    "theme/theme1.xml": r"""<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Office Theme">
  <a:themeElements>
    <a:clrScheme name="Office">
      <a:dk1><a:srgbClr val="000000"/></a:dk1>
      <a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>
      <a:dk2><a:srgbClr val="1F497D"/></a:dk2>
      <a:lt2><a:srgbClr val="EEECE1"/></a:lt2>
      <a:accent1><a:srgbClr val="4F81BD"/></a:accent1>
      <a:accent2><a:srgbClr val="C0504D"/></a:accent2>
      <a:accent3><a:srgbClr val="9BBB59"/></a:accent3>
      <a:accent4><a:srgbClr val="8064A2"/></a:accent4>
      <a:accent5><a:srgbClr val="4BACC6"/></a:accent5>
      <a:accent6><a:srgbClr val="F79646"/></a:accent6>
      <a:hlink><a:srgbClr val="0000FF"/></a:hlink>
      <a:folHlink><a:srgbClr val="800080"/></a:folHlink>
    </a:clrScheme>
    <a:fontScheme name="Office">
      <a:majorFont>
        <a:latin typeface="Times New Roman"/>
        <a:ea typeface=""/><a:cs typeface=""/>
      </a:majorFont>
      <a:minorFont>
        <a:latin typeface="Times New Roman"/>
        <a:ea typeface=""/><a:cs typeface=""/>
      </a:minorFont>
    </a:fontScheme>
    <a:fmtScheme name="Office">
      <a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>
      <a:lnStyleLst><a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst>
      <a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>
      <a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst>
    </a:fmtScheme>
  </a:themeElements>
</a:theme>
""",
}

_DOCX_CONTENT_TYPES = ('<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\r\n'
 '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\r\n'
 '  <Default ContentType="application/xml" Extension="xml"/>\r\n'
 '  <Default ContentType="application/vnd.openxmlformats-package.relationships+xml" Extension="rels"/>\r\n'
 '  <Override ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml" PartName="/docProps/app.xml"/>\r\n'
 '  <Override ContentType="application/vnd.openxmlformats-package.core-properties+xml" PartName="/docProps/core.xml"/>\r\n'
 '  <Override ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml" PartName="/word/document.xml"/>\r\n'
 '  <Override ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml" PartName="/word/fontTable.xml"/>\r\n'
 '  <Override ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml" PartName="/word/header1.xml"/>\r\n'
 '  <Override ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml" PartName="/word/settings.xml"/>\r\n'
 '  <Override ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml" PartName="/word/styles.xml"/>\r\n'
 '  <Override ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.webSettings+xml" PartName="/word/webSettings.xml"/>\r\n'
 '  <Override ContentType="application/vnd.openxmlformats-officedocument.theme+xml" PartName="/word/theme/theme1.xml"/>\r\n'
 '</Types>')

_DOCX_ROOT_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\r\n'
 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\r\n'
 '  <Relationship Id="rId1" Target="word/document.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"/>\r\n'
 '  <Relationship Id="rId2" Target="docProps/core.xml" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties"/>\r\n'
 '  <Relationship Id="rId3" Target="docProps/app.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties"/>\r\n'
 '</Relationships>')

_DOCX_DOC_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\r\n'
 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\r\n'
 '  <Relationship Id="rId1" Target="header1.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header"/>\r\n'
 '  <Relationship Id="rId2" Target="fontTable.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/fontTable"/>\r\n'
 '  <Relationship Id="rId3" Target="settings.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings"/>\r\n'
 '  <Relationship Id="rId4" Target="styles.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"/>\r\n'
 '  <Relationship Id="rId6" Target="webSettings.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/webSettings"/>\r\n'
 '  <Relationship Id="rId7" Target="theme/theme1.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme"/>\r\n'
 '</Relationships>')

_DOCX_APP = ('<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\r\n'
 '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
 'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
 '<Application>Microsoft Office Word</Application></Properties>')

_DOCX_CORE = ('<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\r\n'
 '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
 'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
 'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
 '<dc:creator></dc:creator><cp:lastModifiedBy></cp:lastModifiedBy>'
 '<dcterms:created xsi:type="dcterms:W3CDTF">2026-01-01T00:00:00Z</dcterms:created>'
 '<dcterms:modified xsi:type="dcterms:W3CDTF">2026-01-01T00:00:00Z</dcterms:modified>'
 '</cp:coreProperties>')


# ============================================================
# ГЕНЕРАЦИЯ DOCX
# ============================================================
def build_docx(items, save_dir: Path, year, data, ed_idx) -> Path:
    from xml.sax.saxutils import escape as _esc

    def _run(text, rpr=None):
        if rpr is None:
            rpr = ('<w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/>'
                   '<w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr>')
        sp = ' xml:space="preserve"' if (text != text.strip() or not text.strip()) else ""
        return f'<w:r>{rpr}<w:t{sp}>{_esc(str(text) if text is not None else "")}</w:t></w:r>'

    def _p(text="", jc="both", runs=None, after=0, first=709, bold=False):
        ppr = '<w:widowControl w:val="1"/>'
        ppr += f'<w:spacing w:before="0" w:after="{after}" w:line="240" w:lineRule="auto"/>'
        ppr += f'<w:ind w:firstLine="{first}" w:left="0" w:right="0"/>'
        if jc:
            ppr += f'<w:jc w:val="{jc}"/>'
        mrpr = ('<w:rPr><w:b w:val="1"/></w:rPr>' if bold
                else '<w:rPr><w:sz w:val="28"/></w:rPr>')
        ppr += mrpr
        if runs is not None:
            body_runs = runs
        elif text:
            if bold:
                body_runs = _run(text, rpr=('<w:rPr><w:rFonts w:ascii="Times New Roman" '
                                            'w:hAnsi="Times New Roman"/><w:b/>'
                                            '<w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr>'))
            else:
                body_runs = _run(text)
        else:
            body_runs = ""
        return f'<w:p><w:pPr>{ppr}</w:pPr>{body_runs}</w:p>'

    def _tbl(rows, widths, jc_cols):
        borders = ''.join(
            f'<w:{side} w:color="000000" w:sz="4" w:val="single"/>'
            for side in ("top", "left", "bottom", "right", "insideH", "insideV"))
        out = ('<w:tbl><w:tblPr><w:tblW w:type="auto" w:w="0"/><w:jc w:val="center"/>'
               f'<w:tblBorders>{borders}</w:tblBorders>'
               '<w:tblLayout w:type="fixed"/></w:tblPr>')
        out += '<w:tblGrid>' + ''.join(f'<w:gridCol w:w="{w}"/>' for w in widths) + '</w:tblGrid>'
        for ri, row in enumerate(rows):
            out += '<w:tr>'
            for ci, cell_text in enumerate(row):
                jcx = f'<w:jc w:val="{jc_cols[ci]}"/>' if jc_cols[ci] else ''
                rpr = '<w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:sz w:val="24"/></w:rPr>'
                para = (f'<w:p><w:pPr><w:widowControl w:val="1"/>'
                        '<w:spacing w:after="0" w:line="240" w:lineRule="auto"/>'
                        f'<w:ind/>{jcx}</w:pPr>'
                        f'<w:r>{rpr}<w:t>{_esc(str(cell_text) if cell_text is not None else "")}</w:t></w:r></w:p>')
                out += (f'<w:tc><w:tcPr><w:tcW w:type="dxa" w:w="{widths[ci]}"/>'
                        f'<w:tcBorders>{borders}</w:tcBorders></w:tcPr>{para}</w:tc>')
            out += '</w:tr>'
        return out + '</w:tbl>'

    parts = []

    parts.append(_p(
        "О внесении изменений в постановление администрации муниципального образования "
        "город Краснодар от 15.10.2014 № 7471 «Об утверждении муниципальной программы "
        "муниципального образования город Краснодар «Развитие гражданского общества»",
        jc="center", bold=True, after=240, first=0))
    parts.append(_p(after=120, first=0))

    parts.append(_p(
        "В связи с необходимостью уточнения перечня мероприятий муниципальной программы "
        "муниципального образования город Краснодар «Развитие гражданского общества», "
        "объёмов их финансирования и внесения редакционных правок п о с т а н о в л я ю:"))
    parts.append(_p(
        "1. Внести в постановление администрации муниципального образования город Краснодар "
        "от 15.10.2014 № 7471 «Об утверждении муниципальной программы муниципального "
        "образования город Краснодар «Развитие гражданского общества» следующие изменения:"))

    for i, item in enumerate(items, start=1):
        num = f"1.{i}. "
        if item["kind"] == "paragraph":
            parts.append(_p(num + item["text"]))
        elif item["kind"] == "digits":
            parts.append(_p(num + item["lead"]))
            for line in item["lines"]:
                parts.append(_p(line))
        elif item["kind"] == "table":
            parts.append(_p(num + item["lead"]))
            td = item["table_data"]
            rows, cols = td["rows"], td["columns"]
            if cols == [30, 35, 35]:
                widths, jc_cols = [2003, 4262, 3373], [None, "center", "center"]
            else:
                widths, jc_cols = [677, 3915, 821, 3661], [None, "left", "center", "left"]
            parts.append(_tbl(rows, widths, jc_cols))
            parts.append(_p("».", jc="right"))

    parts.append(_p(
        "2. Департаменту информационной политики администрации муниципального образования "
        "город Краснодар (Лутай) опубликовать настоящее постановление путём размещения "
        "на официальном Интернет-портале администрации муниципального образования "
        "город Краснодар и городской Думы Краснодара."))
    parts.append(_p("3. Настоящее постановление вступает в силу с момента его подписания."))
    parts.append(_p(
        "4. Контроль за выполнением настоящего постановления возложить на заместителя главы "
        "муниципального образования город Краснодар, директора департамента внутренней "
        "политики администрации муниципального образования город Краснодар А.А.Бородавку."))

    parts.append(_p(after=240, first=0))
    parts.append(_p("Временно исполняющий", jc="both", first=0))
    parts.append(_p("обязанности главы муниципального", jc="both", first=0))
    parts.append(_p("образования город Краснодар Д.Ю.Васильев", jc="both", first=0))

    sect = ('<w:sectPr>'
            '<w:headerReference r:id="rId1" w:type="default"/>'
            '<w:pgSz w:h="16848" w:orient="portrait" w:w="11908"/>'
            '<w:pgMar w:bottom="1134" w:footer="709" w:gutter="0" w:header="567" '
            'w:left="1701" w:right="567" w:top="1134"/>'
            '<w:pgNumType w:fmt="decimal"/><w:titlePg/>'
            '</w:sectPr>')
    document_xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<w:document '
                    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
                    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                    '<w:body>' + "".join(parts) + sect + '</w:body></w:document>')

    save_dir.mkdir(parents=True, exist_ok=True)
    fname = f"Postanovlenie_{datetime.now():%Y%m%d_%H%M}_{year}.docx"
    final_path = save_dir / fname
    fd, tmp = tempfile.mkstemp(prefix=".tmp_", suffix=".docx", dir=str(save_dir))
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", _DOCX_CONTENT_TYPES)
            zf.writestr("_rels/.rels", _DOCX_ROOT_RELS)
            zf.writestr("docProps/app.xml", _DOCX_APP)
            zf.writestr("docProps/core.xml", _DOCX_CORE)
            zf.writestr("word/document.xml", document_xml)
            zf.writestr("word/styles.xml", _DOCX_PARTS["styles.xml"])
            zf.writestr("word/fontTable.xml", _DOCX_PARTS["fontTable.xml"])
            zf.writestr("word/settings.xml", _DOCX_PARTS["settings.xml"])
            zf.writestr("word/webSettings.xml", _DOCX_PARTS["webSettings.xml"])
            zf.writestr("word/header1.xml", _DOCX_PARTS["header1.xml"])
            zf.writestr("word/theme/theme1.xml", _DOCX_PARTS["theme/theme1.xml"])
            zf.writestr("word/_rels/document.xml.rels", _DOCX_DOC_RELS)
        os.replace(tmp, final_path)
    except Exception:
        try: os.remove(tmp)
        except Exception: pass
        raise
    return final_path


# ============================================================
# UI
# ============================================================
class App:
    def __init__(self, root):
        self.logger = logger
        self.logger.info('=== Программа запущена ===')
        self.root = root
        self.work_dir = get_work_dir()
        self.data = None
        self.selected_edition = 0
        self.selected_year = 2026
        self._undo_stack = []
        self._redo_stack = []
        self._in_undo = False
        self.unresolved_districts = {}
        self._code_mtime = os.path.getmtime(__file__)
        if not self._ask_password():
            self.root.destroy()
            return
        self._build_ui()
        self._load_or_ask()
        
        if Path("changes.json").exists():
            try:
                data = json.loads(Path("changes.json").read_text(encoding="utf-8"))
                timeline = data.get("timeline", [])
                if timeline:
                    self._populate_postanovlenie_tab()
                    self._populate_nakazy_tab(timeline)
            except Exception:
                pass
                
        self.root.after(500, lambda: self._sync_from_duma(silent=True))
        self.root.after(2000, self._check_code_changes)

    # ---------- Undo / Redo ----------
    def _snapshot(self):
        if self._in_undo: return
        self._undo_stack.append(copy.deepcopy(self.data))
        if len(self._undo_stack) > 100: self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _undo(self):
        if not self._undo_stack: return
        self._redo_stack.append(copy.deepcopy(self.data))
        self.data = self._undo_stack.pop()
        self._in_undo = True
        try:
            self._save_data()
            self.selected_edition = min(self.selected_edition, len(self.data["editions"]) - 1)
            self.refresh_editions(); self.refresh_table(); self.refresh_totals()
        finally:
            self._in_undo = False

    def _redo(self):
        if not self._redo_stack: return
        self._undo_stack.append(copy.deepcopy(self.data))
        self.data = self._redo_stack.pop()
        self._in_undo = True
        try:
            self._save_data()
            self.selected_edition = min(self.selected_edition, len(self.data["editions"]) - 1)
            self.refresh_editions(); self.refresh_table(); self.refresh_totals()
        finally:
            self._in_undo = False

    # ---------- Пароль ----------
    def _ask_password(self):
        cfg = load_config()
        ph = cfg.get("password")
        if not ph: return True
        pw = simpledialog.askstring("Вход", "Введите пароль:", show="*", parent=self.root)
        if pw is None: return False
        if verify_password(pw, ph.get("salt", ""), ph.get("hash", "")):
            return True
        messagebox.showerror("Доступ запрещён", "Неверный пароль")
        return False

    def _change_password(self):
        cfg = load_config()
        ph = cfg.get("password")
        if ph:
            old = simpledialog.askstring("Старый пароль", "Введите текущий пароль:", show="*", parent=self.root)
            if old is None: return
            if not verify_password(old, ph.get("salt", ""), ph.get("hash", "")):
                messagebox.showerror("Ошибка", "Неверный пароль"); return
        pw1 = simpledialog.askstring("Новый пароль",
                                     "Новый пароль (пусто = снять пароль):",
                                     show="*", parent=self.root)
        if pw1 is None: return
        if pw1 == "":
            cfg.pop("password", None); save_config(cfg)
            messagebox.showinfo("OK", "Пароль снят"); return
        if len(pw1) < 4:
            messagebox.showwarning("Слабый пароль", "Минимум 4 символа"); return
        pw2 = simpledialog.askstring("Подтверждение", "Повторите пароль:", show="*", parent=self.root)
        if pw1 != pw2:
            messagebox.showerror("Ошибка", "Пароли не совпадают"); return
        salt, h = _hash_password(pw1)
        cfg["password"] = {"salt": salt, "hash": h}
        save_config(cfg)
        messagebox.showinfo("OK", "Пароль установлен")

    # ---------- Загрузка ----------
    def _load_or_ask(self):
        if not self.work_dir:
            if not self._ask_work_dir(first_time=True):
                messagebox.showwarning("Выход", "Без рабочей папки программа не может работать.")
                self.root.destroy(); return
        self._ensure_dirs()
        self._load_data()
        self.refresh_editions(); self.refresh_table(); self.refresh_totals()

    def _ensure_dirs(self):
        (self.work_dir / "Сохранения").mkdir(parents=True, exist_ok=True)

    def _data_path(self):
        return self.work_dir / "data.json"

    def _load_data(self):
        p = self._data_path()
        if p.exists():
            try:
                self.data = json.loads(p.read_text(encoding="utf-8"))
                if not self.data.get("editions") or self.data["editions"][0]["id"] != "base":
                    self.data = default_data()
            except Exception as e:
                messagebox.showerror("Ошибка чтения data.json", str(e))
                self.data = default_data()
        else:
            self.data = default_data()
            self._save_data()
        self.data.setdefault("base_overrides", {})
        self.data.setdefault("duma_errors", [])
        self.data.setdefault("prog_overrides", {}).setdefault("other", {})
        for ed in self.data.get("editions", []):
            ed.setdefault("changes", {})
            ed.setdefault("renames", {})
            ed.setdefault("added", [])
            ed.setdefault("deleted", [])
        self._last_saved_json = json.dumps(self.data, ensure_ascii=False, sort_keys=True)
        self._last_saved_data = copy.deepcopy(self.data)
        self.selected_edition = len(self.data["editions"]) - 1
        self._undo_stack.clear(); self._redo_stack.clear()
        self.logger.info(f"Загружены данные. Редакций: {len(self.data['editions'])}")

    def _save_data(self, explicit=False):
        try:
            atomic_write_json(self._data_path(), self.data)
            self.logger.info(f"Сохранение данных (explicit={explicit})")
            if explicit:
                self._last_saved_json = json.dumps(self.data, ensure_ascii=False, sort_keys=True)
                self._last_saved_data = copy.deepcopy(self.data)
        except Exception as e:
            messagebox.showerror("Ошибка сохранения",
                                 f"{e}\n\nПроверьте доступ к сетевой папке:\n{self.work_dir}")

    def _ask_work_dir(self, first_time=False):
        d = filedialog.askdirectory(title="Выберите рабочую папку (на сетевом диске)", mustexist=True)
        if not d: return False
        self.work_dir = Path(d)
        cfg = load_config(); cfg["work_dir"] = str(self.work_dir); save_config(cfg)
        self._ensure_dirs()
        if not first_time:
            self._load_data()
            self.refresh_editions(); self.refresh_table(); self.refresh_totals()
        return True

    # ---------- UI ----------
    def _log_click(self, event):
        widget = event.widget
        try:
            cls_name = widget.winfo_class()
            if cls_name in ("TButton", "Button"):
                text = widget.cget("text")
                if text:
                    self.logger.info(f"Клик по кнопке: «{text}»")
            elif cls_name == "TCombobox":
                self.logger.info("Клик по выпадающему списку")
            elif cls_name == "TRadiobutton":
                text = widget.cget("text")
                self.logger.info(f"Клик по переключателю: «{text}»")
        except Exception:
            pass

    def _save_ui_settings(self):
        try:
            data = {
                "tree_widths": [self.tree.column_width(c) for c in range(len(self.tree.headers()))],
                "err_widths": [self.err_tree.column_width(c) for c in range(len(self.err_tree.headers()))],
                "nakazy_widths": [self.nakazy_tree.column_width(c) for c in range(len(self.nakazy_tree.headers()))],
                "post_widths": [self.post_tree.column_width(c) for c in range(len(self.post_tree.headers()))]
            }
            Path("ui_settings.json").write_text(json.dumps(data), encoding="utf-8")
        except Exception as e:
            self.logger.error(f"Ошибка сохранения ui_settings: {e}")

    def _load_ui_settings(self):
        f = Path("ui_settings.json")
        if not f.exists(): return
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            pass # Высота строк больше не используется
            
            for i, w in enumerate(data.get("tree_widths", [])):
                if i < len(self.tree.headers()): self.tree.column_width(i, width=w)
            for i, w in enumerate(data.get("err_widths", [])):
                if i < len(self.err_tree.headers()): self.err_tree.column_width(i, width=w)
            for i, w in enumerate(data.get("nakazy_widths", [])):
                if i < len(self.nakazy_tree.headers()): self.nakazy_tree.column_width(i, width=w)
            for i, w in enumerate(data.get("post_widths", [])):
                if i < len(self.post_tree.headers()): self.post_tree.column_width(i, width=w)
        except Exception as e:
            self.logger.error(f"Ошибка загрузки ui_settings: {e}")

    def _auto_resize_rows_in_sheet(self, sheet):
        import textwrap
        try:
            data = sheet.get_sheet_data()
        except Exception:
            return
        if not data:
            return
        try:
            ncols = len(sheet.headers())
        except Exception:
            ncols = len(data[0]) if data else 0
        col_widths = []
        for c in range(ncols):
            try:
                col_widths.append(sheet.column_width(c))
            except Exception:
                col_widths.append(100)
        heights = []
        NL = chr(10)
        for row in data:
            if not row:
                heights.append(25)
                continue
            max_lines = 1
            for c, cell in enumerate(row):
                if cell is None:
                    continue
                text = str(cell)
                width_px = col_widths[c] if c < len(col_widths) else 100
                chars_per_line = max(10, int((width_px - 15) / 7.5))
                existing_lines = text.split(NL)
                total_lines = 0
                for line in existing_lines:
                    if not line:
                        total_lines += 1
                    else:
                        total_lines += max(1, len(textwrap.wrap(line, width=chars_per_line, break_long_words=False, break_on_hyphens=False)))
                max_lines = max(max_lines, total_lines)
            heights.append(max(25, max_lines * 14 + 2))
        sheet.set_row_heights(heights)

    def _tree_right_click(self, event):
        """Правый клик по таблице — контекстное меню (tksheet не перехватывает правый клик)."""
        try:
            row = self.tree.identify_row(event.y)
            col = self.tree.identify_column(event.x)
        except Exception:
            return
        
        if row is None or col is None:
            return
        
        # Определяем, куда попал клик
        try:
            row_int = int(row)
            col_int = int(str(col).lstrip("#"))
        except (ValueError, TypeError):
            return
        
        if row_int >= len(self.sheet_rows_map):
            return
        ev_id = self.sheet_rows_map[row_int]
        if not ev_id:
            return
        ev = next((e for e in get_effective_events(self.data, self.selected_edition) if e["id"] == ev_id), None)
        if not ev:
            return
        
        # Создаём меню
        menu = tk.Menu(self.root, tearoff=0)
        if not ev.get("is_aggregate"):
            menu.add_command(
                label="✏️ Редактировать сумму",
                command=lambda: self._edit_event_by_id(ev_id)
            )
        menu.add_command(
            label="🗑 Удалить / Утратило силу",
            command=lambda: self._delete_event(ev_id)
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _edit_event_by_id(self, ev_id):
        """Открывает окно редактирования суммы для мероприятия по его id."""
        if self.selected_edition == 0:
            messagebox.showinfo("Начальная редакция", "Начальную редакцию менять нельзя.")
            return
        
        ev = next((e for e in get_effective_events(self.data, self.selected_edition) if e["id"] == ev_id), None)
        if not ev:
            return
        if ev.get("is_aggregate"):
            messagebox.showinfo("Сводная строка", "Сумма 1.1.3 считается автоматически.")
            return
        
        year = int(self.year_var.get())
        cur_val = get_event_value_at(ev, year, self.data, self.selected_edition)
        cur_str = fmt(cur_val) if cur_val is not None else "0"
        
        new_val = simpledialog.askstring(
            "Изменение суммы",
            f"Мероприятие:\n{ev['name']}\n\nВведите новую сумму:",
            initialvalue=cur_str,
            parent=self.root
        )
        if new_val is None:
            return
        
        try:
            v = float(new_val.replace(",", ".").replace(" ", ""))
        except ValueError:
            messagebox.showerror("Ошибка", "Неверный формат числа.")
            return
        
        self._snapshot()
        ed = self.data["editions"][self.selected_edition]
        ed.setdefault("changes", {}).setdefault(ev["id"], {})[str(year)] = v
        if ev.get("parent"):
            ed.setdefault("changes", {})[ev["parent"]] = None
        
        self.logger.info(f"Изменено мероприятие {ev['name']} ({year}): {cur_val} -> {v}")
        self._save_data()
        self.refresh_table()
        self.refresh_totals()



    def _edit_cell(self, event):
        """Редактирование суммы по двойному клику (Treeview)."""
        iid = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        
        if not iid or iid.startswith("__group_"):
            return
        if col != "#3":  # колонка "Станет"
            return
        
        ev = next((e for e in get_effective_events(self.data, self.selected_edition) if e["id"] == iid), None)
        if not ev or ev.get("is_aggregate"):
            messagebox.showinfo("Сводная строка", "Сумма 1.1.3 считается автоматически.")
            return
        
        if self.selected_edition == 0:
            messagebox.showinfo("Начальная редакция", "Начальную редакцию менять нельзя.")
            return
        
        year = int(self.year_var.get())
        cur_val = get_event_value_at(ev, year, self.data, self.selected_edition)
        cur_str = fmt(cur_val) if cur_val is not None else "0"
        
        new_val = simpledialog.askstring(
            "Изменение суммы",
            f"Мероприятие:\n{ev['name']}\n\nВведите новую сумму:",
            initialvalue=cur_str,
            parent=self.root
        )
        if new_val is None:
            return
        
        try:
            v = float(new_val.replace(",", ".").replace(" ", ""))
        except ValueError:
            messagebox.showerror("Ошибка", "Неверный формат числа.")
            return
        
        self._snapshot()
        ed = self.data["editions"][self.selected_edition]
        ed.setdefault("changes", {}).setdefault(ev["id"], {})[str(year)] = v
        if ev.get("parent"):
            ed.setdefault("changes", {})[ev["parent"]] = None
        
        self.logger.info(f"Изменено мероприятие {ev['name']} ({year}): {cur_val} -> {v}")
        self._save_data()
        self.refresh_table()
        self.refresh_totals()

    def _on_tree_select(self, event):
        sel = self.tree.selection()
        if sel:
            iid = sel[0]
            if not iid.startswith("__group_"):
                name = self.tree.set(iid, "name").strip()
                self.logger.info(f"Выбрана строка таблицы: «{name}»")

    def _build_ui(self):
        self.root.title("Конструктор постановлений — Linux")
        self.root.geometry("1400x900")

        top = ttk.Frame(self.root, padding=(6, 6, 6, 2)); top.pack(fill=tk.X)
        
        ttk.Label(top, text="Редакция:").pack(side=tk.LEFT)
        self.edition_cb = ttk.Combobox(top, state="readonly", width=35)
        self.edition_cb.pack(side=tk.LEFT, padx=4)
        self.edition_cb.bind("<<ComboboxSelected>>", self._on_edition_change)
        
        btn_frame = ttk.Frame(top); btn_frame.pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="📥 Из Думы", command=self._sync_from_duma).pack(side=tk.LEFT, padx=1)
        ttk.Button(btn_frame, text="➕", command=self._add_edition).pack(side=tk.LEFT, padx=1)
        ttk.Button(btn_frame, text="📋", command=self._dup_edition).pack(side=tk.LEFT, padx=1)
        ttk.Button(btn_frame, text="✏️", command=self._edit_meta).pack(side=tk.LEFT, padx=1)
        ttk.Button(btn_frame, text="🗑", command=self._del_edition).pack(side=tk.LEFT, padx=1)

        ttk.Label(top, text="Решение Думы:").pack(side=tk.LEFT, padx=(10, 0))
        self.decision_cb = ttk.Combobox(top, state="readonly", width=25)
        self.decision_cb.bind("<<ComboboxSelected>>", self._on_duma_decision_change)
        self.decision_cb.pack(side=tk.LEFT, padx=4)

        year_row = ttk.Frame(self.root, padding=(6, 2, 6, 6)); year_row.pack(fill=tk.X)
        
        ttk.Label(year_row, text="Год:").pack(side=tk.LEFT)
        self.year_var = tk.StringVar(value="2026")
        for y in YEAR_LIST:
            ttk.Radiobutton(year_row, text=str(y), value=str(y),
                            variable=self.year_var, command=self._on_year_change).pack(side=tk.LEFT, padx=2)
                            
        ttk.Separator(year_row, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=8)
        
        ttk.Button(year_row, text="↔ Ширина", command=self._ask_column_width).pack(side=tk.LEFT, padx=4)
        ttk.Button(year_row, text="➕ Добавить", command=self._add_event).pack(side=tk.LEFT, padx=4)
        
        ttk.Separator(year_row, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=8)

        ttk.Button(year_row, text="💾", command=lambda: self._save_data(explicit=True)).pack(side=tk.LEFT, padx=1)
        ttk.Button(year_row, text="↶", command=self._undo, width=3).pack(side=tk.LEFT, padx=1)
        ttk.Button(year_row, text="↷", command=self._redo, width=3).pack(side=tk.LEFT, padx=1)
        ttk.Button(year_row, text="📜 Логи", command=self._show_logs).pack(side=tk.LEFT, padx=4)
        ttk.Button(year_row, text="🩺 Диагностика", command=self._run_diagnostics).pack(side=tk.LEFT, padx=4)
        
        self.btn_errors = ttk.Button(year_row, text="⚠ Ошибки", command=self._show_errors_dialog, state="disabled")
        self.btn_errors.pack(side=tk.LEFT, padx=4)
        ttk.Button(year_row, text="🔒 Пароль", command=self._change_password).pack(side=tk.RIGHT, padx=4)
        ttk.Button(year_row, text="📂 Папка", command=lambda: self._ask_work_dir()).pack(side=tk.RIGHT, padx=4)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self.tab_main = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_main, text="Мероприятия")
        
        # Используем обычный ttk.Treeview — он надёжно поддерживает выделение и редактирование
        cols = ("name", "base", "new", "delta")
        self.tree = ttk.Treeview(self.tab_main, columns=cols, show="headings", height=20)
        self.tree.heading("name",  text="Наименование мероприятия")
        self.tree.heading("base",  text="Сейчас")
        self.tree.heading("new",   text="Станет")
        self.tree.heading("delta", text="Разница")
        self.tree.column("name",  width=700)
        self.tree.column("base",  width=120, anchor="e")
        self.tree.column("new",   width=120, anchor="e")
        self.tree.column("delta", width=110, anchor="e")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=6)
        
        sb = ttk.Scrollbar(self.tab_main, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y, pady=6)
        
        self.tree.bind("<Double-1>", self._edit_cell)

        self.tab_errors = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_errors, text="Расхождения с Думой")
        
        self.err_tree = tksheet.Sheet(self.tab_errors, headers=["Тип", "Мероприятие", "Сейчас", "В Думе", "Источник", "Постановление"])
        self.err_tree.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.err_tree.set_options(table_wrap="w", allow_column_width_resizing=True)
        for i in range(6): self.err_tree.column_width(column=i, width=150)

        self.tab_nakazy = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_nakazy, text="Наказы (История)")
        
        self.nakazy_tree = tksheet.Sheet(self.tab_nakazy)
        self.nakazy_tree.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.nakazy_tree.set_options(table_wrap="w", allow_column_width_resizing=True)

        self.tab_error_details = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_error_details, text="Ошибки: подробно")
        
        details_frame = ttk.Frame(self.tab_error_details)
        details_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        
        btn_row = ttk.Frame(details_frame)
        btn_row.pack(side=tk.TOP, anchor="w", pady=(0, 5))
        
        btn_refresh = ttk.Button(btn_row, text="🔄 Пересчитать и обновить", command=self._display_error_report)
        btn_refresh.pack(side=tk.LEFT, padx=(0, 4))
        
        btn_pdf = ttk.Button(btn_row, text="📄 Экспорт в PDF/A", command=self._export_errors_pdf)
        btn_pdf.pack(side=tk.LEFT, padx=4)
        
        btn_txt = ttk.Button(btn_row, text="📋 Копировать текст", command=self._copy_error_report)
        btn_txt.pack(side=tk.LEFT, padx=4)
        
        self.error_details_text = tk.Text(details_frame, wrap="word", font=("TkDefaultFont", 10), bg="#f9f9f9", padx=10, pady=10)
        self.error_details_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scroll = ttk.Scrollbar(details_frame, orient="vertical", command=self.error_details_text.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.error_details_text.configure(yscrollcommand=scroll.set)
        
        self.tab_postanovlenie = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_postanovlenie, text="Постановление 7471 (История)")
        
        self.post_tree = tksheet.Sheet(self.tab_postanovlenie)
        self.post_tree.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.post_tree.set_options(table_wrap="w", allow_column_width_resizing=True)

        bottom = ttk.Frame(self.root, padding=6); bottom.pack(fill=tk.X)
        
        self.totals_label = tk.StringVar()
        ttk.Label(bottom, textvariable=self.totals_label, font=("TkDefaultFont", 10, "bold")).pack(side=tk.LEFT)
        
        ttk.Button(bottom, text="📄 Сформировать .docx", command=self._generate).pack(side=tk.RIGHT, padx=4)
        ttk.Button(bottom, text="📂 Открыть «Сохранения»", command=self._open_save_dir).pack(side=tk.RIGHT, padx=4)
        
        warn_row = ttk.Frame(self.root, padding=(6, 0, 6, 6)); warn_row.pack(fill=tk.X)
        self.warn_label = tk.StringVar()
        self.warn_widget = ttk.Label(warn_row, textvariable=self.warn_label, foreground="#a00")
        self.warn_widget.pack(side=tk.LEFT)
        
        path_row = ttk.Frame(self.root, padding=(6, 0, 6, 6)); path_row.pack(fill=tk.X)
        self.path_label = ttk.Label(path_row, text="", foreground="#666", font=("TkDefaultFont", 8))
        self.path_label.pack(side=tk.LEFT)

        self.root.bind_all("<ButtonRelease-1>", self._log_click)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Control-s>", lambda _e: self._save_data(explicit=True))
        self.root.bind("<Control-z>", lambda _e: self._undo())
        self.root.bind("<Control-y>", lambda _e: self._redo())

        self.root.after(100, self._load_ui_settings)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def refresh_editions(self):
        labels = []
        for ed in self.data["editions"]:
            mark = "📜 " if ed.get("preset") else "✏️ "
            labels.append(f"{mark}{ed['label']} ({ed.get('date','')})")
        self.edition_cb["values"] = labels
        if 0 <= self.selected_edition < len(labels):
            self.edition_cb.current(self.selected_edition)
        if self.work_dir:
            self.path_label.config(text=f"Папка: {self.work_dir}")

    def refresh_table(self):
        # Очищаем
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        
        ed_idx = self.selected_edition
        year = int(self.year_var.get())
        cur_group = None
        
        for ev in get_effective_events(self.data, ed_idx):
            # Заголовок округа
            if ev.get("parent") and ev.get("group") and ev["group"] != cur_group:
                cur_group = ev["group"]
                group_name = GROUPS_DICT.get(cur_group, "")
                self.tree.insert("", "end", iid=f"__group_{cur_group}",
                                 values=(group_name, "", "", ""),
                                 tags=("group",))
            
            name = get_effective_name(ev, self.data, ed_idx)
            if ev.get("parent"):
                name = "    " + name
            
            prev_idx = max(0, ed_idx - 1)
            base = get_event_value_at(ev, year, self.data, prev_idx)
            new = get_event_value_at(ev, year, self.data, ed_idx)
            d = round(new - base, 1)
            if abs(d) < 0.0001:
                delta_txt = "0,0"
            else:
                delta_txt = ("+" if d > 0 else "−") + fmt(abs(d))
            
            tag = ""
            if ev.get("is_aggregate"):
                tag = "agg"
            elif ev["id"] in self.data.get("duma_errors", []):
                tag = "err"
            elif ev.get("is_custom"):
                tag = "new"
            
            self.tree.insert("", "end", iid=ev["id"],
                             values=(name, fmt(base), fmt(new), delta_txt),
                             tags=(tag,))
        
        # Настройка тегов
        self.tree.tag_configure("group", background="#eef2f7", font=("TkDefaultFont", 9, "bold"))
        self.tree.tag_configure("agg",   background="#f0f7ff")
        self.tree.tag_configure("err",   background="#ffe0e0", foreground="#a00")
        self.tree.tag_configure("new",   background="#f0fff4")
        
        # Запоминаем маппинг (для _edit_cell)
        self.sheet_rows_map = []  # не нужен для Treeview, но чтобы не ломать код

    def refresh_totals(self):
        ed_idx = self.selected_edition
        year = int(self.year_var.get())
        self.totals_label.set(
            f"Сумма мероприятий за {year}: {fmt(get_event_sum_at(year, self.data, ed_idx))}   |   "
            f"Подпрограмма за {year}: {fmt(get_sub2_year_at(year, self.data, ed_idx))}   |   "
            f"Подпрограмма всего: {fmt(get_sub2_total_at(self.data, ed_idx))}   |   "
            f"Программа всего: {fmt(get_program_total_at(self.data, ed_idx))}"
        )
        year_i = int(self.year_var.get())
        try:
            official, computed, diff = check_aggregate_consistency(self.data, ed_idx, year_i)
        except Exception:
            official, computed, diff = None, None, None
        if official is not None and diff is not None and abs(diff) > 0.1:
            self.warn_label.set(
                f"⚠ 1.1.3: официально {fmt(official)}, "
                f"по мероприятиям {fmt(computed)} (расхождение {fmt(diff)})"
            )
            self.warn_widget.configure(foreground="#a00")
        else:
            self.warn_label.set("")

    def _on_tab_changed(self, event):
        # Пересчитываем высоту строк для активной вкладки
        try:
            current = self.notebook.index("current")
            # Вкладка "Мероприятия"
            if current == self.notebook.index(self.tab_main):
                self._auto_resize_rows_in_sheet(self.tree)
            # Вкладка "Расхождения с Думой"
            elif current == self.notebook.index(self.tab_errors):
                self._auto_resize_rows_in_sheet(self.err_tree)
            # Вкладка "Наказы (История)"
            elif current == self.notebook.index(self.tab_nakazy):
                self._auto_resize_rows_in_sheet(self.nakazy_tree)
            # Вкладка "Ошибки: подробно"
            elif current == self.notebook.index(self.tab_error_details):
                self._display_error_report()
            # Вкладка "История решений Думы"
            elif current == self.notebook.index(self.tab_postanovlenie):
                self._auto_resize_rows_in_sheet(self.post_tree)
        except Exception as e:
            print(f"DEBUG: Ошибка в _on_tab_changed: {e}")

    def _check_code_changes(self):
        try:
            current_mtime = os.path.getmtime(__file__)
        except Exception:
            current_mtime = self._code_mtime
        if current_mtime > self._code_mtime:
            self.logger.info("Обнаружено изменение кода программы. Перезапуск...")
            try:
                self._save_data(explicit=True)
            except Exception:
                pass
            try:
                messagebox.showinfo("Обновление кода", "Код программы был изменён.\nПрограмма будет перезапущена.", parent=self.root)
            except Exception:
                pass
            try:
                self.root.destroy()
            except Exception:
                pass
            try:
                subprocess.Popen([sys.executable, os.path.abspath(__file__)], cwd=os.path.dirname(os.path.abspath(__file__)))
            except Exception as e:
                print("Не удалось перезапустить программу:", e)
            os._exit(0)
            return
        else:
            self.root.after(2000, self._check_code_changes)


    def _copy_error_report(self):
        if not hasattr(self, 'error_details_text'): return
        text = self.error_details_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showinfo("Пусто", "Отчёт пуст.", parent=self.root); return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo("Готово", "Текст отчёта скопирован в буфер обмена.", parent=self.root)

    def _export_errors_pdf(self):
        if not hasattr(self, 'error_details_text'): return
        text = self.error_details_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showinfo("Пусто", "Отчёт пуст. Сначала нажмите «Пересчитать и обновить».", parent=self.root)
            return

        path = filedialog.asksaveasfilename(
            parent=self.root,
            defaultextension=".pdf",
            filetypes=[("PDF/A", "*.pdf"), ("Все файлы", "*.*")],
            initialfile=f"Отчёт_об_ошибках_{datetime.now():%Y%m%d_%H%M}.pdf",
            title="Экспорт отчёта в PDF/A"
        )
        if not path:
            return

        try:
            # 1. Проверяем наличие библиотек
            import reportlab
            import pikepdf
        except ImportError as e:
            messagebox.showerror("Ошибка", f"Не найдены библиотеки: {e}\n\nСохраняем как .txt...", parent=self.root)
            txt_path = Path(path).with_suffix('.txt')
            txt_path.write_text(text, encoding='utf-8')
            return

        # 2. Генерируем PDF через reportlab
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.platypus import SimpleDocTemplate, Paragraph
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

            font_path = "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf"
            if not Path(font_path).exists():
                font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
            
            pdfmetrics.registerFont(TTFont("Mono", font_path))
            styles = getSampleStyleSheet()
            style = ParagraphStyle(
                'MonoStyle', parent=styles['Normal'],
                fontName="Mono", fontSize=9, leading=11, spaceAfter=2
            )

            # Временный файл
            import tempfile
            tmp_pdf = tempfile.mktemp(suffix=".pdf")
            
            doc = SimpleDocTemplate(tmp_pdf, pagesize=A4, leftMargin=30, rightMargin=30, topMargin=30, bottomMargin=30)
            elements = []
            for line in text.split("\n"):
                # Заменяем пробелы на неразрывные, чтобы сохранить отступы
                safe_line = line.replace(" ", "&nbsp;").replace("<", "&lt;").replace(">", "&gt;")
                if not safe_line.strip(): safe_line = "&nbsp;"
                elements.append(Paragraph(safe_line, style))
            
            doc.build(elements)
            self.logger.info(f"Сгенерирован PDF: {tmp_pdf}")

            # 3. Превращаем в PDF/A-2b через pikepdf
            with pikepdf.open(tmp_pdf, allow_overwriting_input=True) as pdf:
                with pdf.open_metadata() as meta:
                    meta['pdfaid:part'] = '2'
                    meta['pdfaid:conformance'] = 'B'
                    meta['dc:title'] = 'Отчет об ошибках в мероприятиях ТОС'
                    meta['dc:creator'] = ['Конструктор постановлений']
                    meta['pdf:Producer'] = 'Constructor PDF/A Engine'
                
                # Устанавливаем OutputIntent (упрощенно, для валидации)
                # В реальном PDF/A нужен ICC-профиль. Если его нет, pdf всё равно откроется.
                try:
                    icc_path = Path("/usr/share/color/icc/colord/sRGB.icc")
                    if icc_path.exists():
                        icc_data = icc_path.read_bytes()
                        stream = pdf.make_stream(icc_data)
                        stream.N = 3
                        pdf.Root.OutputIntents = [pikepdf.Dictionary({
                            "/Type": pikepdf.Name("/OutputIntent"),
                            "/S": pikepdf.Name("/GTS_PDFA1"),
                            "/OutputConditionIdentifier": pikepdf.String("sRGB"),
                            "/DestOutputProfile": stream
                        })]
                except Exception as icc_e:
                    self.logger.warning(f"Не удалось добавить OutputIntent: {icc_e}")

                pdf.save(path)
            
            Path(tmp_pdf).unlink(missing_ok=True)
            self.logger.info(f"PDF/A успешно сохранён: {path}")

            if messagebox.askyesno("Готово", f"PDF/A сохранён:\n{path}\n\nОткрыть?", parent=self.root):
                subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        except Exception as e:
            import traceback
            self.logger.error(f"Ошибка создания PDF/A: {e}\n{traceback.format_exc()}")
            messagebox.showerror("Ошибка", f"Не удалось создать PDF/A:\n{e}\n\nСохраняем как .txt...", parent=self.root)
            try:
                txt_path = Path(path).with_suffix('.txt')
                txt_path.write_text(text, encoding='utf-8')
            except Exception:
                pass

    def _run_diagnostics(self):
        win = tk.Toplevel(self.root)
        win.title("Диагностика программы")
        win.geometry("800x600")
        
        txt = tk.Text(win, wrap="word", font=("Courier", 10), bg="#f9f9f9")
        txt.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        
        def log(msg, status="OK"):
            icons = {"OK": "✅", "WARN": "⚠️", "ERR": "❌"}
            line = f"{icons.get(status, '•')} [{status}] {msg}\n"
            txt.insert(tk.END, line)
            self.logger.info(f"ДИАГНОСТИКА: {line.strip()}")
            txt.see(tk.END)
            
        txt.insert(tk.END, "=== ДИАГНОСТИКА КОНСТРУКТОРА ===\n\n")
        
        data_path = self._data_path()
        if data_path.exists(): log(f"data.json найден: {data_path}")
        else: log(f"data.json НЕ НАЙДЕН: {data_path}", "ERR")
            
        if self.data and self.data.get("editions"): log(f"Загружено редакций: {len(self.data['editions'])}")
        else: log("Редакции не загружены", "ERR")
            
        try:
            tree_rows = len(self.tree.get_sheet_data())
            log(f"Таблица 'Мероприятия': {tree_rows} строк")
            if tree_rows == 0: log("Таблица 'Мероприятия' ПУСТАЯ!", "WARN")
        except Exception as e: log(f"Ошибка чтения таблицы 'Мероприятия': {e}", "ERR")
            
        try:
            err_rows = len(self.err_tree.get_sheet_data())
            log(f"Таблица 'Расхождения': {err_rows} строк")
        except Exception as e: log(f"Ошибка чтения таблицы 'Расхождения': {e}", "ERR")
            
        try:
            nak_rows = len(self.nakazy_tree.get_sheet_data())
            log(f"Таблица 'Наказы': {nak_rows} строк")
            if nak_rows == 0: log("Таблица 'Наказы' ПУСТАЯ! Возможно, парсер не смог загрузить данные.", "WARN")
        except Exception as e: log(f"Ошибка чтения таблицы 'Наказы': {e}", "ERR")
            
        try:
            hist_rows = len(self.post_tree.get_sheet_data())
            log(f"Таблица 'История': {hist_rows} строк")
        except Exception as e: log(f"Ошибка чтения таблицы 'История': {e}", "ERR")
            
        folder = Path("Наказы")
        if folder.exists():
            count = len(list(folder.glob("*.htm*")))
            log(f"Папка 'Наказы': найдено {count} HTML-файлов")
            if count == 0: log("В папке 'Наказы' нет HTML-файлов!", "WARN")
        else: log("Папка 'Наказы' не найдена!", "ERR")
            
        changes = Path("changes.json")
        if changes.exists():
            try:
                d = json.loads(changes.read_text(encoding="utf-8"))
                tl = d.get("timeline", [])
                log(f"changes.json: {len(tl)} шагов истории")
                if len(tl) < 2: log("История слишком короткая (меньше 2 шагов)!", "WARN")
            except Exception as e: log(f"Ошибка чтения changes.json: {e}", "ERR")
        else: log("changes.json не найден (не было синхронизации)", "WARN")
            
        try:
            ed_idx = self.selected_edition
            year = int(self.year_var.get())
            total = get_event_sum_at(year, self.data, ed_idx)
            log(f"Сумма мероприятий за {year} ({self.data['editions'][ed_idx]['label']}): {fmt(total)}")
        except Exception as e: log(f"Ошибка расчета суммы: {e}", "ERR")
            
        today = datetime.now().strftime("%Y-%m-%d")
        log_path = Path("Логи") / f"{today}.log"
        if log_path.exists(): log(f"Файл логов за сегодня: {log_path.stat().st_size} байт")
        else: log("Файл логов за сегодня не создан", "WARN")
            
        txt.insert(tk.END, "\n=== КОНЕЦ ДИАГНОСТИКИ ===\n")
        txt.configure(state="disabled")
        ttk.Button(win, text="Закрыть", command=win.destroy).pack(pady=4)

    def _show_logs(self):
        win = tk.Toplevel(self.root)
        win.title("Журнал событий (Логи)")
        win.geometry("900x600")
        
        txt = tk.Text(win, wrap="word", font=("Courier", 10), bg="#f9f9f9")
        txt.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        
        def load_current_log():
            txt.configure(state="normal")
            txt.delete(1.0, tk.END)
            today_str = datetime.now().strftime("%Y-%m-%d")
            log_path = Path("Логи") / f"{today_str}.log"
            if log_path.exists(): txt.insert(tk.END, log_path.read_text(encoding="utf-8"))
            else: txt.insert(tk.END, f"Файл логов за {today_str} пока пуст.")
            txt.see(tk.END)
            txt.configure(state="disabled")
            
        def copy_logs():
            win.clipboard_clear()
            win.clipboard_append(txt.get("1.0", tk.END))
            messagebox.showinfo("Скопировано", "Весь текст логов скопирован в буфер обмена.", parent=win)
            
        def export_logs():
            path = filedialog.asksaveasfilename(parent=win, defaultextension=".txt", filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")], initialfile=f"Логи_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.txt", title="Экспорт логов")
            if path:
                try:
                    with open(path, "w", encoding="utf-8") as f: f.write(txt.get("1.0", tk.END))
                    messagebox.showinfo("Экспорт", f"Логи сохранены в файл:\n{path}", parent=win)
                except Exception as e: messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\n{e}", parent=win)
            
        load_current_log()
        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=4)
        ttk.Button(btn_frame, text="🔄 Обновить", command=load_current_log).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="📋 Копировать всё", command=copy_logs).pack(side=tk.LEFT, padx=4)
        
        def copy_selected():
            try:
                selected = txt.get("sel.first", "sel.last")
                if not selected:
                    messagebox.showwarning("Не выделено", "Сначала выделите текст мышью.", parent=win)
                    return
                win.clipboard_clear()
                win.clipboard_append(selected)
                messagebox.showinfo("Скопировано", f"Скопировано строк: {len(selected.splitlines())}", parent=win)
            except tk.TclError:
                messagebox.showwarning("Не выделено", "Сначала выделите текст мышью.", parent=win)
        
        ttk.Button(btn_frame, text="📋 Копировать выделенное", command=copy_selected).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="💾 Экспорт", command=export_logs).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="Закрыть", command=win.destroy).pack(side=tk.LEFT, padx=4)

    def _ask_column_width(self):
        win = tk.Toplevel(self.root)
        win.title("Настройка ширины столбцов")
        win.geometry("560x340")
        win.transient(self.root)

        top = ttk.Frame(win, padding=10)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Таблица:").grid(row=0, column=0, sticky="w", pady=4)
        table_cb = ttk.Combobox(top, state="readonly", width=30, values=[
            "1. Мероприятия",
            "2. Расхождения с Думой",
            "3. Наказы (История)",
            "4. Постановление 7471 (История)"
        ])
        table_cb.current(0)
        table_cb.grid(row=0, column=1, sticky="ew", padx=6, pady=4)

        ttk.Label(top, text="Столбец:").grid(row=1, column=0, sticky="w", pady=4)
        col_cb = ttk.Combobox(top, state="readonly", width=30)
        col_cb.grid(row=1, column=1, sticky="ew", padx=6, pady=4)
        top.columnconfigure(1, weight=1)

        bottom = ttk.Frame(win, padding=10)
        bottom.pack(fill=tk.X)

        width_label = tk.StringVar(value="Ширина: — px")
        ttk.Label(bottom, textvariable=width_label, font=("TkDefaultFont", 12, "bold")).pack(pady=(0, 10))

        btn_row = ttk.Frame(bottom)
        btn_row.pack(pady=4)

        state = {"sheet": None, "col": 0, "width": 100}

        def get_sheet_by_index(idx):
            if idx == 0: return self.tree
            if idx == 1: return self.err_tree
            if idx == 2: return self.nakazy_tree
            if idx == 3: return self.post_tree
            return None

        def refresh_columns(*_):
            sheet = get_sheet_by_index(table_cb.current())
            state["sheet"] = sheet
            if not sheet: return
            try:
                headers = sheet.headers()
                col_names = [f"{i+1}. {h}" for i, h in enumerate(headers)]
                col_cb["values"] = col_names
                if col_names:
                    col_cb.current(0)
                    on_column_change()
            except Exception as e:
                print("Ошибка обновления столбцов:", e)

        def on_column_change(*_):
            idx = col_cb.current()
            if idx < 0: return
            state["col"] = idx
            sheet = state["sheet"]
            if not sheet: return
            try:
                w = sheet.column_width(idx)
                state["width"] = w
                width_label.set(f"Ширина: {w} px")
            except Exception as e:
                print("Ошибка получения ширины:", e)

        def change_width(delta):
            sheet = state["sheet"]
            if not sheet: return
            new_w = state["width"] + delta
            if new_w < 30: new_w = 30
            if new_w > 2000: new_w = 2000
            try:
                sheet.column_width(state["col"], width=new_w)
                state["width"] = new_w
                width_label.set(f"Ширина: {new_w} px")
                self._save_ui_settings()
            except Exception as e:
                print("Ошибка изменения ширины:", e)

        def enter_width():
            sheet = state["sheet"]
            if not sheet: return
            val = simpledialog.askinteger(
                "Точная ширина",
                f"Введите ширину в пикселях (текущая: {state['width']}):",
                initialvalue=state["width"], minvalue=30, maxvalue=2000, parent=win
            )
            if val is not None:
                try:
                    sheet.column_width(state["col"], width=val)
                    state["width"] = val
                    width_label.set(f"Ширина: {val} px")
                    self._save_ui_settings()
                except Exception as e:
                    print("Ошибка:", e)

        ttk.Button(btn_row, text="−50", width=6, command=lambda: change_width(-50)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="−10", width=6, command=lambda: change_width(-10)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="−1",  width=6, command=lambda: change_width(-1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="✎",  width=6, command=enter_width).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_row, text="+1",  width=6, command=lambda: change_width(1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="+10", width=6, command=lambda: change_width(10)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="+50", width=6, command=lambda: change_width(50)).pack(side=tk.LEFT, padx=2)

        ttk.Button(win, text="Закрыть", command=win.destroy).pack(pady=10)

        table_cb.bind("<<ComboboxSelected>>", refresh_columns)
        col_cb.bind("<<ComboboxSelected>>", on_column_change)

        refresh_columns()


    def _on_year_change(self):
        self.logger.info(f"Выбран год: {self.year_var.get()}")
        self.refresh_table(); self.refresh_totals()

    def _on_edition_change(self, _evt=None):
        idx = self.edition_cb.current()
        if idx < 0: return
        self.selected_edition = idx
        label = self.data["editions"][idx].get("label", f"Индекс {idx}")
        self.logger.info(f"Выбрана редакция: «{label}»")
        self.refresh_table(); self.refresh_totals()

    def _add_event(self):
        if self.selected_edition == 0: messagebox.showwarning("Редакция", "Выберите редакцию (не начальную)."); return
        win = tk.Toplevel(self.root); win.title("Добавить мероприятие"); win.geometry("620x560"); win.transient(self.root); win.grab_set()
        frm = ttk.Frame(win, padding=12); frm.pack(fill=tk.BOTH, expand=True)
        src_cb = ttk.Combobox(frm, state="readonly", values=["Приложение № 3 (наказы избирателей)", "Таблица 3 (общая)"]); src_cb.current(0)
        grp_cb = ttk.Combobox(frm, state="readonly", values=[g[1] for g in GROUPS]); grp_cb.current(0)
        num_var = tk.StringVar(value="2.9"); name_var = tk.StringVar(value="")
        y26_var = tk.StringVar(value="0"); y27_var = tk.StringVar(value="0"); y28_var = tk.StringVar(value="0")
        exec_var = tk.StringVar(value=EXECUTOR_KGTOS)
        rows = [
            ("Куда:", src_cb), ("Округ:", grp_cb), ("Номер (напр. 2.9):", ttk.Entry(frm, textvariable=num_var)),
            ("Название:", ttk.Entry(frm, textvariable=name_var)), ("Сумма 2026, тыс. руб.:", ttk.Entry(frm, textvariable=y26_var)),
            ("Сумма 2027, тыс. руб.:", ttk.Entry(frm, textvariable=y27_var)), ("Сумма 2028, тыс. руб.:", ttk.Entry(frm, textvariable=y28_var)),
            ("Исполнитель:", ttk.Entry(frm, textvariable=exec_var)),
        ]
        exec_widget = None
        for ri, (lbl, widget) in enumerate(rows):
            ttk.Label(frm, text=lbl).grid(row=ri, column=0, sticky="w", pady=4); widget.grid(row=ri, column=1, sticky="ew", pady=4, padx=6)
            if ri == 7: exec_widget = widget
        frm.columnconfigure(1, weight=1)
        def on_src_change(*_):
            is_app3 = (src_cb.current() == 0); grp_cb.configure(state="readonly" if is_app3 else "disabled")
            if exec_widget: exec_widget.configure(state="normal" if is_app3 else "disabled")
        src_cb.bind("<<ComboboxSelected>>", on_src_change)
        def on_ok():
            try:
                name = name_var.get().strip(); num = num_var.get().strip()
                if not name or not num: messagebox.showwarning("Ошибка", "Заполните номер и название", parent=win); return
                y26 = float(y26_var.get().replace(",", ".") or 0); y27 = float(y27_var.get().replace(",", ".") or 0); y28 = float(y28_var.get().replace(",", ".") or 0)
            except ValueError: messagebox.showwarning("Ошибка", "Неверный формат суммы", parent=win); return
            is_app3 = (src_cb.current() == 0)
            if is_app3:
                if not re.match(r"^\d+\.\d+$", num): messagebox.showwarning("Ошибка", "Для приложения № 3 номер должен быть вида X.Y (напр. 2.9)", parent=win); return
            else:
                if not re.match(r"^\d+\.\d+\.\d+$", num): messagebox.showwarning("Ошибка", "Для таблицы 3 номер должен быть вида X.Y.Z (напр. 4.1.1)", parent=win); return
            self._snapshot()
            ev = {"id": f"custom_{int(datetime.now().timestamp() * 1000)}", "is_custom": True, "source": "app3" if is_app3 else "table3", "name": f"п. {num} «{name}»", "old_value": y26, "years": {"2026": y26, "2027": y27, "2028": y28}}
            if is_app3: ev["parent"] = "e_1_1_3"; ev["group"] = GROUPS[grp_cb.current()][0]; ev["executor"] = exec_var.get().strip()
            self.logger.info(f"Добавлено новое мероприятие: {ev['name']} на сумму {y26}")
            self.data["editions"][self.selected_edition].setdefault("added", []).append(ev)
            self._save_data(); win.destroy(); self.refresh_table(); self.refresh_totals()
        btns = ttk.Frame(frm); btns.grid(row=len(rows), column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Отмена", command=win.destroy).pack(side=tk.RIGHT, padx=4); ttk.Button(btns, text="Добавить", command=on_ok).pack(side=tk.RIGHT, padx=4)

    def _delete_event(self, ev_id: str):
        if self.selected_edition == 0: return
        ed = self.data["editions"][self.selected_edition]
        custom = next((e for e in ed.get("added", []) if e["id"] == ev_id), None)
        if custom:
            if not messagebox.askyesno("Удалить", f"Удалить «{custom['name']}»?", parent=self.root): return
            self._snapshot(); ed["added"] = [e for e in ed.get("added", []) if e["id"] != ev_id]
            self._save_data(); self.refresh_table(); self.refresh_totals(); return
        base_ev = next((e for e in EVENTS if e["id"] == ev_id), None)
        if not base_ev: return
        if not messagebox.askyesno("Утратило силу", f"Признать утратившим силу «{base_ev['name']}»?\n(все суммы за 2026–2028 станут 0 в этой редакции)", parent=self.root): return
        self._snapshot(); self.logger.info(f"Признано утратившим силу мероприятие: {base_ev['name']}")
        ed.setdefault("changes", {})[ev_id] = {"2026": 0.0, "2027": 0.0, "2028": 0.0}
        if base_ev.get("parent"): ed["changes"].pop(base_ev["parent"], None)
        self._save_data(); self.refresh_table(); self.refresh_totals()

    def _add_edition(self):
        d = simpledialog.askstring("Дата (ГГГГ-ММ-ДД)", "Введите дату:", initialvalue=datetime.now().strftime("%Y-%m-%d"))
        if not d: return
        try: datetime.strptime(d, "%Y-%m-%d")
        except ValueError: messagebox.showwarning("Неверный формат", "Дата должна быть в формате ГГГГ-ММ-ДД"); return
        l = simpledialog.askstring("Описание", "Название редакции:", initialvalue=f"Изменения от {d}")
        if not l: return
        self._snapshot(); self.logger.info(f"Создана новая редакция: {l} от {d}")
        self.data["editions"].append({"id": f"ed_{int(datetime.now().timestamp()*1000)}", "date": d, "label": l, "note": "", "changes": {}, "renames": {}, "added": [], "deleted": []})
        self.selected_edition = len(self.data["editions"]) - 1
        self._save_data(); self.refresh_editions(); self.refresh_table(); self.refresh_totals()

    def _dup_edition(self):
        if self.selected_edition < 0: return
        src = self.data["editions"][self.selected_edition]
        d = simpledialog.askstring("Дата", "Дата:", initialvalue=datetime.now().strftime("%Y-%m-%d"))
        if not d: return
        try: datetime.strptime(d, "%Y-%m-%d")
        except ValueError: messagebox.showwarning("Неверный формат", "Дата должна быть в формате ГГГГ-ММ-ДД"); return
        l = simpledialog.askstring("Описание", "Название:", initialvalue=src["label"] + " (копия)")
        if not l: return
        self._snapshot()
        new_ed = json.loads(json.dumps(src))
        new_ed["id"] = f"ed_{int(datetime.now().timestamp()*1000)}"; new_ed["date"] = d; new_ed["label"] = l; new_ed["preset"] = False
        new_ed["added"] = []; new_ed["deleted"] = []; new_ed["renames"] = {}
        self.data["editions"].insert(self.selected_edition + 1, new_ed)
        self.selected_edition += 1
        self._save_data(); self.refresh_editions(); self.refresh_table(); self.refresh_totals()

    def _edit_meta(self):
        if self.selected_edition == 0: return
        ed = self.data["editions"][self.selected_edition]
        d = simpledialog.askstring("Дата", "Дата:", initialvalue=ed["date"])
        if not d: return
        try: datetime.strptime(d, "%Y-%m-%d")
        except ValueError: messagebox.showwarning("Неверный формат", "Дата должна быть в формате ГГГГ-ММ-ДД"); return
        l = simpledialog.askstring("Название", "Название:", initialvalue=ed["label"])
        if not l: return
        self._snapshot(); ed["date"] = d; ed["label"] = l
        self._save_data(); self.refresh_editions()

    def _del_edition(self):
        if self.selected_edition == 0: return
        ed = self.data["editions"][self.selected_edition]
        if ed.get("preset"): messagebox.showwarning("Нельзя удалить", "Пресетные (исторические) редакции нельзя удалять."); return
        if not messagebox.askyesno("Удалить", f"Удалить «{ed['label']}»?"): return
        self._snapshot(); del self.data["editions"][self.selected_edition]
        self.selected_edition = max(0, self.selected_edition - 1)
        self._save_data(); self.refresh_editions(); self.refresh_table(); self.refresh_totals()

    def _generate(self):
        if self.selected_edition == 0: messagebox.showwarning("Редакция", "Выберите редакцию (не начальную)."); return
        try:
            year = int(self.year_var.get())
            official, computed, diff = check_aggregate_consistency(self.data, self.selected_edition, year)
            if official is not None and diff is not None and abs(diff) > 0.1:
                if not messagebox.askyesno("Расхождение в 1.1.3", f"⚠ В редакции «{self.data['editions'][self.selected_edition]['label']}» официальное значение 1.1.3 = {fmt(official)}, а по мероприятиям = {fmt(computed)} (расхождение {fmt(diff)}).\n\nСформировать документ всё равно?", parent=self.root): return
            items = generate_items(self.data, self.selected_edition, year)
            if not items: messagebox.showinfo("Нет изменений", f"За {year} год изменений не найдено."); return
            save_dir = self.work_dir / "Сохранения"
            path = build_docx(items, save_dir, year, self.data, self.selected_edition)
            if messagebox.askyesno("Готово", f"Сохранено:\n{path}\n\nОткрыть?"):
                subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            self.logger.error(f"Ошибка при генерации DOCX: {e}\n{traceback.format_exc()}")
            import traceback; traceback.print_exc(); messagebox.showerror("Ошибка", str(e))

    def _on_close(self):
        self._save_ui_settings()
        if hasattr(self, '_last_saved_json'):
            current = json.dumps(self.data, ensure_ascii=False, sort_keys=True)
            if current != self._last_saved_json:
                ans = messagebox.askyesnocancel("Несохраненные изменения", "В программе есть несохраненные изменения.\n\nСохранить их перед выходом?", parent=self.root)
                if ans is True: self._save_data(explicit=True); self.root.destroy()
                elif ans is False:
                    if hasattr(self, '_last_saved_data') and self._last_saved_data is not None:
                        try: atomic_write_json(self._data_path(), self._last_saved_data)
                        except Exception: pass
                    self.root.destroy()
                return
        self.root.destroy()

    def _open_save_dir(self):
        if not self.work_dir: return
        d = self.work_dir / "Сохранения"
        d.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["xdg-open", str(d)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # --- Синхронизация с Думой ---
    def _sync_from_duma(self, silent=False):
        if not tracker:
            if not silent: messagebox.showerror("Ошибка", "Файл tracker.py не найден.")
            return
        try:
            success = tracker.scan()
            if not success:
                if not silent: messagebox.showerror("Ошибка", "Не удалось найти HTML-файлы решений в папке 'Наказы'.")
                return
            changes_path = Path("changes.json")
            if not changes_path.exists():
                if not silent: messagebox.showerror("Ошибка", "Файл changes.json не создан.")
                return
            data = json.loads(changes_path.read_text(encoding="utf-8"))
            
            fixes_file = Path("district_fixes.json")
            fixes = {}
            if fixes_file.exists():
                try: fixes = json.loads(fixes_file.read_text(encoding="utf-8"))
                except Exception: pass
            self.unresolved_districts = {}
            for step in data.get("timeline", []):
                for item in step.get("items", []):
                    if item.get("status") == "ok":
                        works = item.get("works", "").strip()
                        if not item.get("district", "").strip():
                            if works in fixes: item["district"] = fixes[works]
                            else:
                                if works not in self.unresolved_districts: self.unresolved_districts[works] = {"sources": set()}
                                src_info = f"от {step['date']} № {step['number']}"
                                self.unresolved_districts[works]["sources"].add(src_info)
            for w in self.unresolved_districts: self.unresolved_districts[w]["sources"] = list(self.unresolved_districts[w]["sources"])
            if self.unresolved_districts:
                self._ask_for_missing_districts()
                for step in data.get("timeline", []):
                    for item in step.get("items", []):
                        works = item.get("works", "").strip()
                        if not item.get("district", "").strip() and works in fixes: item["district"] = fixes[works]
            self._update_errors_button()

            timeline = data.get("timeline", [])
            if not timeline:
                if not silent: messagebox.showerror("Ошибка", "История решений пуста.")
                return

            folder = Path("Наказы")
            all_files = []
            if folder.exists():
                for p in folder.glob("*.htm*"):
                    m = re.search(r"от\s+(\d{2}\.\d{2}\.\d{4})\s+N\s+([\w\-.]+)", p.name)
                    if m: all_files.append({"date": m.group(1), "number": m.group(2), "file": p.name})
            all_files.sort(key=lambda x: datetime.strptime(x["date"], "%d.%m.%Y"))
            self.all_duma_files = all_files

            decisions = []
            for f in all_files:
                is_in_timeline = any(step.get("date") == f["date"] and step.get("number") == f["number"] for step in timeline)
                suffix = "" if is_in_timeline else " [нет данных ТОС]"
                decisions.append(f"от {f['date']} № {f['number']}{suffix}")
            self.decision_cb["values"] = decisions
            if decisions: self.decision_cb.current(len(decisions) - 1)
            
            self._populate_postanovlenie_tab()
            self._populate_nakazy_tab(timeline)
            self._compare_with_selected_duma()
            self.root.after(200, self._load_ui_settings)
            
            # Принудительно обновляем текст после завершения синхронизации
            self.root.after(200, self._refresh_error_details_text)
            
            if not silent: messagebox.showinfo("Успех", "Данные из решений Думы обновлены.")
        except Exception as e:
            if not silent:
                import traceback; traceback.print_exc(); messagebox.showerror("Ошибка синхронизации", str(e))

    def _display_error_report(self, event=None):
        if not hasattr(self, 'error_details_text'):
            return
        
        self.error_details_text.configure(state="normal")
        self.error_details_text.delete("1.0", tk.END)
        
        # ============ РАЗДЕЛ A ============
        self.error_details_text.insert(tk.END, "═══ РАЗДЕЛ A: ОШИБКИ В РЕШЕНИЯХ ДУМЫ ═══\n\n")
        errors_a = self._check_duma_errors()
        if errors_a:
            for i, e in enumerate(errors_a, 1):
                self.error_details_text.insert(tk.END, f"❌ A.{i}: {e}\n\n")
        else:
            self.error_details_text.insert(tk.END, "✅ Ошибок в решениях Думы не найдено.\n\n")
        self.error_details_text.insert(tk.END, "="*60 + "\n\n")
        
        # ============ РАЗДЕЛ B ============
        self.error_details_text.insert(tk.END, "═══ РАЗДЕЛ B: ОШИБКИ В ПОСТАНОВЛЕНИЯХ ═══\n\n")
        errors_b = self._check_postanovlenie_errors()
        if errors_b:
            for i, e in enumerate(errors_b, 1):
                self.error_details_text.insert(tk.END, f"❌ B.{i}: {e}\n\n")
        else:
            self.error_details_text.insert(tk.END, "✅ Ошибок в постановлениях не найдено.\n\n")
        self.error_details_text.insert(tk.END, "="*60 + "\n\n")
        
        # ============ РАЗДЕЛ C ============
        self.error_details_text.insert(tk.END, "═══ РАЗДЕЛ C: ПОСТАНОВЛЕНИЕ vs ДУМА ═══\n\n")
        errors_c = self._check_postanovlenie_vs_duma()
        if errors_c:
            for i, e in enumerate(errors_c, 1):
                self.error_details_text.insert(tk.END, f"❌ C.{i}: {e}\n\n")
        else:
            self.error_details_text.insert(tk.END, "✅ Расхождений с Думой не найдено.\n\n")
        
        self.error_details_text.configure(state="disabled")
        self.error_details_text.see("1.0")

    def _check_duma_errors(self):
        """Раздел A: проверка решений Думы между собой."""
        errors = []
        changes_path = Path("changes.json")
        if not changes_path.exists():
            return ["changes.json не найден (нет синхронизации с Думой)"]
        
        try:
            data = json.loads(changes_path.read_text(encoding="utf-8"))
        except Exception as e:
            return [f"Ошибка чтения changes.json: {e}"]
        
        timeline = data.get("timeline", [])
        if not timeline:
            return ["История Думы пуста"]
        
        # 1. Сумма final_items (только status=ok) vs final_total
        final_items = data.get("final_items", [])
        final_total = data.get("final_total", 0)
        ok_items = [it for it in final_items if it.get("status") == "ok"]
        calc_total = sum(float(it.get("amount", 0) or 0) for it in ok_items)
        if abs(calc_total - final_total) > 0.1:
            diff = calc_total - final_total
            errors.append(
                f"Итоговая сумма {len(ok_items)} мероприятий ({fmt(calc_total)}) "
                f"не совпадает с итогом в документе ({fmt(final_total)}), "
                f"расхождение {fmt(diff)}. Возможно, одно из мероприятий ошибочно оставлено/удалено."
            )
        
        # 2. Каждое решение должно давать изменения (diff)
        for step in timeline:
            if step.get("kind") != "amendment":
                continue
            diff = step.get("diff", {})
            has_changes = diff.get("added") or diff.get("removed") or diff.get("changed")
            if not has_changes:
                errors.append(f"Решение от {step.get('date')} № {step.get('number')}: не даёт никаких изменений (подозрительно)")
        
        return errors

    def _check_postanovlenie_errors(self):
        """Раздел B: проверка постановлений между собой (аудит 1.1.3)."""
        errors = []
        if not self.data or not self.data.get("editions"):
            return ["Данные постановлений не загружены"]
        
        for i, ed in enumerate(self.data["editions"]):
            if i == 0:
                continue
            official, computed, diff = check_aggregate_consistency(self.data, i, 2026)
            if official is None:
                continue
            if diff is not None and abs(diff) > 0.1:
                errors.append(f"[{i}] {ed.get('label')}: 1.1.3 официально {fmt(official)}, по мероприятиям {fmt(computed)} (расхождение {fmt(diff)})")
        
        return errors

    def _check_postanovlenie_vs_duma(self):
        """Раздел C: сравнение текущей редакции постановления с последним решением Думы."""
        errors = []
        changes_path = Path("changes.json")
        if not changes_path.exists():
            return ["changes.json не найден (нет синхронизации с Думой)"]
        
        try:
            data = json.loads(changes_path.read_text(encoding="utf-8"))
        except Exception as e:
            return [f"Ошибка чтения changes.json: {e}"]
        
        timeline = data.get("timeline", [])
        if not timeline:
            return ["История Думы пуста"]
        
        last_step = timeline[-1]
        target_items = last_step.get("items", [])
        
        # Карта Думы
        group_mapping = {"10":"1","12":"2","20":"3","27":"4","31":"5","33":"6","МИО Галушко В.Ф.":"7"}
        duma_map = {}
        for item in target_items:
            if item.get("status") != "ok":
                continue
            dist = item.get("district", "").strip()
            g = group_mapping.get(dist)
            if not g:
                continue
            name = normalize_name(item.get("works", ""))
            amount = float(item.get("amount") or 0)
            duma_map[(g, name)] = amount
        
        current_idx = len(self.data["editions"]) - 1
        current_label = self.data["editions"][current_idx].get("label", "текущая")
        app3 = [e for e in get_effective_events(self.data, current_idx) if e.get("source") == "app3"]
        
        found_in_duma = set()
        for ev in app3:
            g = ev.get("group")
            eff_name = get_effective_name(ev, self.data, current_idx)
            m = re.search(r'«(.*)»', eff_name)
            name = normalize_name(m.group(1) if m else eff_name)
            key = (g, name)
            
            val = get_event_value_at(ev, 2026, self.data, current_idx)
            
            if key in duma_map:
                found_in_duma.add(key)
                expected = duma_map[key]
                if abs(val - expected) > 0.01:
                    errors.append(f"Неверная сумма: {eff_name[:70]} = {fmt(val)} (в Думе {fmt(expected)})")
            else:
                errors.append(f"Лишнее мероприятие: {eff_name[:70]} = {fmt(val)} (нет в Думе)")
        
        for key, expected in duma_map.items():
            if key not in found_in_duma:
                g, name = key
                errors.append(f"Не хватает в постановлении: [{g}] {name[:60]} = {fmt(expected)}")
        
        return errors

    def _on_duma_decision_change(self, event):
        sel = self.decision_cb.get()
        self.logger.info(f"Выбрано решение Думы для сравнения: «{sel}»")
        self._compare_with_selected_duma()

    def _update_errors_button(self):
        if hasattr(self, 'unresolved_districts') and self.unresolved_districts: self.btn_errors.configure(state="normal")
        else: self.btn_errors.configure(state="disabled")

    def _show_errors_dialog(self):
        if hasattr(self, 'unresolved_districts') and self.unresolved_districts: self._ask_for_missing_districts()
        else: messagebox.showinfo("Ошибки парсинга", "Все округа успешно определены.")

    def _ask_for_missing_districts(self):
        if not hasattr(self, 'unresolved_districts') or not self.unresolved_districts: return
        if hasattr(self, '_error_win') and self._error_win.winfo_exists(): self._error_win.lift(); return
        self._error_win = tk.Toplevel(self.root); self._error_win.title("Ошибка парсинга: не указан округ"); self._error_win.geometry("850x450"); self._error_win.transient(self.root)
        ttk.Label(self._error_win, text="В решениях Думы не удалось определить округ для следующих мероприятий.\nПожалуйста, укажите его (программа запомнит ваш выбор):", font=("TkDefaultFont", 10, "bold"), padding=10).pack()
        canvas = tk.Canvas(self._error_win); scrollbar = ttk.Scrollbar(self._error_win, orient="vertical", command=canvas.yview); scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))); canvas.create_window((0, 0), window=scrollable_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5); scrollbar.pack(side="right", fill="y")
        vars = {}; row = 0; fixes_file = Path("district_fixes.json"); fixes = {}
        if fixes_file.exists():
            try: fixes = json.loads(fixes_file.read_text(encoding="utf-8"))
            except Exception: pass
        for works, data in self.unresolved_districts.items():
            sources_str = ", ".join(data["sources"]); lbl_text = f"{works}\n(Встречается в: {sources_str})"
            ttk.Label(scrollable_frame, text=lbl_text, wraplength=500, justify="left").grid(row=row, column=0, sticky="w", pady=5, padx=5)
            var = tk.StringVar()
            if works in fixes: gid = fixes[works]; val = next((g[1] for g in GROUPS if g[0] == gid), ""); var.set(val)
            choices = [g[1] for g in GROUPS] + ["Без округа"]; cb = ttk.Combobox(scrollable_frame, textvariable=var, state="readonly", values=choices, width=40)
            cb.grid(row=row, column=1, sticky="w", padx=10, pady=5); vars[works] = var; row += 1
        def save():
            for works, var in vars.items():
                val = var.get()
                if not val: messagebox.showwarning("Ошибка", f"Пожалуйста, укажите округ для:\n{works}", parent=self._error_win); return
                if val == "Без округа": gid = "0"
                else: gid = next((g[0] for g in GROUPS if g[1] == val), "")
                if gid is not None: fixes[works] = gid
                if works in self.unresolved_districts: del self.unresolved_districts[works]
            fixes_file.write_text(json.dumps(fixes, ensure_ascii=False, indent=2), encoding="utf-8"); self._update_errors_button(); self._error_win.destroy(); self._sync_from_duma(silent=True)
        ttk.Button(self._error_win, text="💾 Сохранить и продолжить", command=save).pack(pady=10)

    def _populate_nakazy_tab(self, timeline):
        try:
            if not timeline: return
            master_decisions = []
            try:
                data = json.loads(Path("changes.json").read_text(encoding="utf-8"))
                base = timeline[0]; master_decisions.append({"date": base["date"], "number": base["number"], "is_base": True})
                for ch in data.get("changes", []): master_decisions.append({"date": ch["date"], "number": ch["number"], "is_base": False})
                for step in timeline[1:]:
                    if not any(m["date"] == step["date"] and m["number"] == step["number"] for m in master_decisions): master_decisions.append({"date": step["date"], "number": step["number"], "is_base": False})
                def parse_date(d_str):
                    try: return datetime.strptime(d_str, "%d.%m.%Y")
                    except: return datetime.min
                master_decisions.sort(key=lambda x: parse_date(x["date"]))
            except Exception as e: self.logger.error(f"Ошибка чтения changes.json: {e}"); return
            all_events = set()
            for step in timeline:
                for item in step.get("items", []):
                    if item.get("status") == "ok":
                        dist = item.get("district", "").strip()
                        if not dist: dist = "Без округа"
                        all_events.add((dist, item.get("works", "").strip()))
            def sort_key(x):
                dist = x[0]
                if dist.isdigit(): return (int(dist), x[1])
                return (999, x[1])
            sorted_events = sorted(all_events, key=sort_key)
            headers = ["Округ", "Мероприятие"] + [f"{m['date']} N {m['number']}" for m in master_decisions]
            self.nakazy_tree.headers(headers)
            self.nakazy_tree.column_width(0, width=100); self.nakazy_tree.column_width(1, width=300)
            for i in range(2, len(headers)): self.nakazy_tree.column_width(i, width=110)
            timeline_steps = {(s["date"], s["number"]): s for s in timeline}
            final_rows = []; current_district = None
            for event in sorted_events:
                dist, name = event
                if dist != current_district:
                    current_district = dist
                    group_name = f"Округ {dist}" if dist and dist != "0" else "Без округа"
                    final_rows.append([group_name, "", ""] + [""] * len(master_decisions))
                row_values = [dist, name]; current_amount = None; is_removed = False
                for m_dec in master_decisions:
                    step = timeline_steps.get((m_dec["date"], m_dec["number"]))
                    if m_dec["is_base"]:
                        item_in_step = next((it for it in step.get("items", []) if it.get("district","").strip() == dist and it.get("works","").strip() == name and it.get("status") == "ok"), None) if step else None
                        if item_in_step: current_amount = float(item_in_step.get("amount") or 0); row_values.append(fmt(current_amount))
                        else: row_values.append("—")
                        continue
                    if not step:
                        if is_removed: row_values.append("убрано ранее")
                        elif current_amount is None: row_values.append("—")
                        else: row_values.append("не меняется")
                        continue
                    diff = step.get("diff", {})
                    removed = any(rem.get("district","").strip() == dist and rem.get("works","").strip() == name for rem in diff.get("removed", []))
                    if removed: row_values.append(f"убрано от {step['date']}"); is_removed = True; current_amount = None; continue
                    added = next((it for it in diff.get("added", []) if it.get("district","").strip() == dist and it.get("works","").strip() == name), None)
                    if added: current_amount = float(added.get("amount") or 0); row_values.append(fmt(current_amount)); is_removed = False; continue
                    changed = next((c for c in diff.get("changed", []) if c["after"].get("district","").strip() == dist and c["after"].get("works","").strip() == name), None)
                    if changed: current_amount = float(changed["after"].get("amount") or 0); row_values.append(fmt(current_amount)); continue
                    if is_removed: row_values.append("убрано ранее")
                    elif current_amount is None: row_values.append("—")
                    else: row_values.append("не меняется")
                import textwrap
                wrapped_name = "\n".join([name])
                display_values = [dist, wrapped_name] + row_values[2:]
                final_rows.append(display_values)
            self.nakazy_tree.set_sheet_data(final_rows)
            for i, row in enumerate(final_rows):
                if row[1] == "": self.nakazy_tree.highlight_cells(row=i, bg="#eef2f7", fg="#000")
        except Exception as e:
            self.logger.error(f"Ошибка в _populate_nakazy_tab: {e}\n{traceback.format_exc()}")

    def _populate_postanovlenie_tab(self):
        """Строит матрицу: строки — мероприятия, столбцы — редакции постановления."""
        if not self.data or not self.data.get("editions"):
            return
        
        editions = self.data["editions"]
        headers = ["Округ", "Мероприятие"] + [f"{ed.get('date','?')}\n{ed.get('label','?')[:25]}" for ed in editions]
        
        # Собираем ВСЕ мероприятия (по всем редакциям)
        all_events = []
        seen = set()
        for idx in range(len(editions)):
            for ev in get_effective_events(self.data, idx):
                if ev.get("source") == "app3" and ev["id"] not in seen:
                    seen.add(ev["id"])
                    all_events.append(ev)
        
        def sort_key(ev):
            g = ev.get("group", "99")
            try:
                g_num = int(g)
            except:
                g_num = 99
            return (g_num, ev.get("name", ""))
        
        all_events.sort(key=sort_key)
        
        final_rows = []
        current_group = None
        
        for ev in all_events:
            g = ev.get("group", "?")
            
            if g != current_group:
                current_group = g
                group_name = GROUPS_DICT.get(g, f"Округ {g}")
                final_rows.append([group_name, ""] + [""] * len(editions))
            
            name = get_effective_name(ev, self.data, len(editions) - 1)
            m = re.search(r'«(.*)»', name)
            short_name = m.group(1) if m else name
            
            row = [g, short_name]
            prev_val = None
            
            for idx in range(len(editions)):
                ev_exists = True
                for k in range(1, idx + 1):
                    if k >= len(editions): break
                    if ev["id"] in editions[k].get("deleted", []):
                        ev_exists = False
                        break
                
                if not ev_exists:
                    if prev_val is not None:
                        row.append(f"убрано от {editions[idx].get('date','?')}")
                        prev_val = None
                    else:
                        row.append("—")
                    continue
                
                val = get_event_value_at(ev, 2026, self.data, idx)
                if prev_val is None:
                    row.append(fmt(val))
                elif abs(val - prev_val) < 0.01:
                    row.append("не меняется")
                else:
                    row.append(fmt(val))
                prev_val = val
            
            final_rows.append(row)
        
        self.post_tree.headers(headers)
        self.post_tree.column_width(0, width=100)
        self.post_tree.column_width(1, width=350)
        for i in range(2, len(headers)):
            self.post_tree.column_width(i, width=130)
        
        self.post_tree.set_sheet_data(final_rows)
        
        for i, row in enumerate(final_rows):
            if row[1] == "":
                self.post_tree.highlight_cells(row=i, bg="#eef2f7", fg="#000")

    def _compare_with_selected_duma(self):
        sel_idx = self.decision_cb.current()
        if sel_idx < 0 or not hasattr(self, 'all_duma_files') or sel_idx >= len(self.all_duma_files): return
        sel_file = self.all_duma_files[sel_idx]; changes_path = Path("changes.json")
        if not changes_path.exists(): return
        data = json.loads(changes_path.read_text(encoding="utf-8")); timeline = data.get("timeline", [])
        selected_step = next((s for s in timeline if s.get("date") == sel_file["date"] and s.get("number") == sel_file["number"]), None)
        if not selected_step:
            self.err_tree.set_sheet_data([["Нет данных", f"В выбранном решении Думы от {sel_file['date']} № {sel_file['number']} не содержится информация по разделу ТОС (Наказы)", "—", "—", "—", "—"]])
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой"); return
        target_items = selected_step.get("items", []); duma_map = {}
        group_mapping = {"10": "1", "12": "2", "20": "3", "27": "4", "31": "5", "33": "6", "МИО Галушко В.Ф.": "7"}
        for item in target_items:
            if item.get("status") != "ok": continue
            dist = item.get("district", "").strip(); g = group_mapping.get(dist)
            if not g: continue
            name = item.get("works", "").strip(); amount = float(item.get("amount") or 0)
            duma_map[(g, name)] = (amount, item.get("institution", ""))
        error_details = []; found_keys = set(); postanovlenie = self.data["editions"][self.selected_edition]["label"]
        app3_events = [e for e in get_effective_events(self.data, self.selected_edition) if e.get("source") == "app3"]
        if len(duma_map) < max(3, len(app3_events) * 0.2):
            self.err_tree.set_sheet_data([["Неполные данные", f"В выбранном решении Думы от {sel_file['date']} № {sel_file['number']} не содержится полная информация по разделу ТОС. Найдено {len(duma_map)} мероприятий из {len(app3_events)}. Сравнение невозможно.", "—", "—", "—", "—"]])
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой"); self.notebook.select(self.tab_errors); return
        def get_duma_source(g, name):
            for step in reversed(timeline):
                if step["kind"] == "amendment":
                    diff = step.get("diff", {})
                    for lst in (diff.get("added", []), diff.get("changed", [])):
                        for it in lst:
                            if group_mapping.get(it.get("district", "").strip()) == g and it.get("works", "").strip() == name: return f"от {step['date']} № {step['number']}"
            base = timeline[0]; return f"от {base['date']} № {base['number']} (база)"
        for ev in app3_events:
            g = ev.get("group"); m = re.search(r'«(.*)»', ev["name"]); name = m.group(1) if m else ev["name"]; key = (g, name)
            if key in duma_map:
                found_keys.add(key); expected = duma_map[key][0]; current = get_event_value_at(ev, 2026, self.data, self.selected_edition)
                if abs(current - expected) > 0.01:
                    error_details.append({"id": ev["id"], "name": ev["name"], "type": "Неверная сумма", "current": fmt(current), "expected": fmt(expected), "duma_source": get_duma_source(g, name), "postanovlenie": postanovlenie})
            else:
                error_details.append({"id": ev["id"], "name": ev["name"], "type": "Нет в Думе (лишнее)", "current": fmt(get_event_value_at(ev, 2026, self.data, self.selected_edition)), "expected": "—", "duma_source": get_duma_source(g, name), "postanovlenie": postanovlenie})
        added_details = []; is_latest = (selected_step == timeline[-1])
        if is_latest:
            for (g, name), (amount, inst) in duma_map.items():
                if (g, name) not in found_keys:
                    existing_nums = [int(re.search(r'п\.\s*\d+\.(\d+)', e["name"]).group(1)) for e in app3_events if e.get("group")==g and re.search(r'п\.\s*\d+\.(\d+)', e["name"])]
                    next_num = max(existing_nums) + 1 if existing_nums else 1; new_id = f"duma_{g}_{next_num}"
                    ed = self.data["editions"][self.selected_edition]
                    existing = any(e.get("name") == f"п. {g}.{next_num} «{name}»" for e in ed.get("added", []))
                    if not existing:
                        ed.setdefault("added", []).append({"id": new_id, "source": "app3", "parent": "e_1_1_3", "group": g, "name": f"п. {g}.{next_num} «{name}»", "old_value": amount, "years": {"2026": amount, "2027": 0.0, "2028": 0.0}, "executor": inst, "is_custom": True})
                        added_details.append({"name": f"п. {g}.{next_num} «{name}»", "amount": fmt(amount)})
        self.data["duma_errors"] = [e["id"] for e in error_details]
        self._save_data(explicit=True); self.refresh_table(); self.refresh_totals(); self._update_duma_errors_tab(error_details, added_details)

    def _update_duma_errors_tab(self, errors, added):
        # Сохраняем ошибки в память программы
        self.last_errors = errors
        self.last_added = added
        
        # 1. Заполняем таблицу "Расхождения"
        data = []
        for e in errors: 
            data.append([e.get("type","—"), e.get("name","—"), e.get("current","—"), e.get("expected","—"), e.get("duma_source","—"), e.get("postanovlenie","—")])
        for a in added: 
            data.append(["Добавлено из Думы", a.get("name","—"), "—", a.get("amount","—"), "—", "—"])
        if not errors and not added: 
            data.append(["Успех", "Расхождений с Думой не найдено.", "—", "—", "—", "—"])
        
        self.err_tree.set_sheet_data(data)
        
        import textwrap
        heights = []
        for row in data:
            text = str(row[1]) if len(row) > 1 else ""
            lines = [text]
            heights.append(max(25, len(lines) * 18 + 5))
        if heights: 
            self.err_tree.set_row_heights(heights)

        # 2. Обновляем текстовый отчет
        self._display_error_report()
        
        # 3. Обновляем заголовки вкладок
        # Восстанавливаем ширины столбцов после перезаполнения
        self.root.after(100, self._load_ui_settings)
        
        if errors:
            self.notebook.tab(self.tab_errors, text=f"Расхождения ({len(errors)}) ⚠")
            self.notebook.tab(self.tab_error_details, text=f"Ошибки: подробно ({len(errors)}) ⚠")
            self.notebook.select(self.tab_errors)
        elif added:
            self.notebook.tab(self.tab_errors, text=f"Добавлено ({len(added)})")
            self.notebook.tab(self.tab_error_details, text=f"Добавлено ({len(added)})")
            self.notebook.select(self.tab_errors)
        else:
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой (OK)")
            self.notebook.tab(self.tab_error_details, text="Ошибки: подробно")
            self.notebook.select(self.tab_main)

    def _on_duma_decision_change(self, event):
        sel = self.decision_cb.get()
        self.logger.info(f"Выбрано решение Думы для сравнения: «{sel}»")
        self._compare_with_selected_duma()

    def _update_errors_button(self):
        if hasattr(self, 'unresolved_districts') and self.unresolved_districts: self.btn_errors.configure(state="normal")
        else: self.btn_errors.configure(state="disabled")

    def _show_errors_dialog(self):
        if hasattr(self, 'unresolved_districts') and self.unresolved_districts: self._ask_for_missing_districts()
        else: messagebox.showinfo("Ошибки парсинга", "Все округа успешно определены.")

    def _ask_for_missing_districts(self):
        if not hasattr(self, 'unresolved_districts') or not self.unresolved_districts: return
        if hasattr(self, '_error_win') and self._error_win.winfo_exists(): self._error_win.lift(); return
        self._error_win = tk.Toplevel(self.root); self._error_win.title("Ошибка парсинга: не указан округ"); self._error_win.geometry("850x450"); self._error_win.transient(self.root)
        ttk.Label(self._error_win, text="В решениях Думы не удалось определить округ для следующих мероприятий.\nПожалуйста, укажите его (программа запомнит ваш выбор):", font=("TkDefaultFont", 10, "bold"), padding=10).pack()
        canvas = tk.Canvas(self._error_win); scrollbar = ttk.Scrollbar(self._error_win, orient="vertical", command=canvas.yview); scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))); canvas.create_window((0, 0), window=scrollable_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5); scrollbar.pack(side="right", fill="y")
        vars = {}; row = 0; fixes_file = Path("district_fixes.json"); fixes = {}
        if fixes_file.exists():
            try: fixes = json.loads(fixes_file.read_text(encoding="utf-8"))
            except Exception: pass
        for works, data in self.unresolved_districts.items():
            sources_str = ", ".join(data["sources"]); lbl_text = f"{works}\n(Встречается в: {sources_str})"
            ttk.Label(scrollable_frame, text=lbl_text, wraplength=500, justify="left").grid(row=row, column=0, sticky="w", pady=5, padx=5)
            var = tk.StringVar()
            if works in fixes: gid = fixes[works]; val = next((g[1] for g in GROUPS if g[0] == gid), ""); var.set(val)
            choices = [g[1] for g in GROUPS] + ["Без округа"]; cb = ttk.Combobox(scrollable_frame, textvariable=var, state="readonly", values=choices, width=40)
            cb.grid(row=row, column=1, sticky="w", padx=10, pady=5); vars[works] = var; row += 1
        def save():
            for works, var in vars.items():
                val = var.get()
                if not val: messagebox.showwarning("Ошибка", f"Пожалуйста, укажите округ для:\n{works}", parent=self._error_win); return
                if val == "Без округа": gid = "0"
                else: gid = next((g[0] for g in GROUPS if g[1] == val), "")
                if gid is not None: fixes[works] = gid
                if works in self.unresolved_districts: del self.unresolved_districts[works]
            fixes_file.write_text(json.dumps(fixes, ensure_ascii=False, indent=2), encoding="utf-8"); self._update_errors_button(); self._error_win.destroy(); self._sync_from_duma(silent=True)
        ttk.Button(self._error_win, text="💾 Сохранить и продолжить", command=save).pack(pady=10)

    def _populate_nakazy_tab(self, timeline):
        try:
            if not timeline: return
            master_decisions = []
            try:
                data = json.loads(Path("changes.json").read_text(encoding="utf-8"))
                base = timeline[0]; master_decisions.append({"date": base["date"], "number": base["number"], "is_base": True})
                for ch in data.get("changes", []): master_decisions.append({"date": ch["date"], "number": ch["number"], "is_base": False})
                for step in timeline[1:]:
                    if not any(m["date"] == step["date"] and m["number"] == step["number"] for m in master_decisions): master_decisions.append({"date": step["date"], "number": step["number"], "is_base": False})
                def parse_date(d_str):
                    try: return datetime.strptime(d_str, "%d.%m.%Y")
                    except: return datetime.min
                master_decisions.sort(key=lambda x: parse_date(x["date"]))
            except Exception as e: self.logger.error(f"Ошибка чтения changes.json: {e}"); return
            all_events = set()
            for step in timeline:
                for item in step.get("items", []):
                    if item.get("status") == "ok":
                        dist = item.get("district", "").strip()
                        if not dist: dist = "Без округа"
                        all_events.add((dist, item.get("works", "").strip()))
            def sort_key(x):
                dist = x[0]
                if dist.isdigit(): return (int(dist), x[1])
                return (999, x[1])
            sorted_events = sorted(all_events, key=sort_key)
            headers = ["Округ", "Мероприятие"] + [f"{m['date']} N {m['number']}" for m in master_decisions]
            self.nakazy_tree.headers(headers)
            self.nakazy_tree.column_width(0, width=100); self.nakazy_tree.column_width(1, width=300)
            for i in range(2, len(headers)): self.nakazy_tree.column_width(i, width=110)
            timeline_steps = {(s["date"], s["number"]): s for s in timeline}
            final_rows = []; current_district = None
            for event in sorted_events:
                dist, name = event
                if dist != current_district:
                    current_district = dist
                    group_name = f"Округ {dist}" if dist and dist != "0" else "Без округа"
                    final_rows.append([group_name, "", ""] + [""] * len(master_decisions))
                row_values = [dist, name]; current_amount = None; is_removed = False
                for m_dec in master_decisions:
                    step = timeline_steps.get((m_dec["date"], m_dec["number"]))
                    if m_dec["is_base"]:
                        item_in_step = next((it for it in step.get("items", []) if it.get("district","").strip() == dist and it.get("works","").strip() == name and it.get("status") == "ok"), None) if step else None
                        if item_in_step: current_amount = float(item_in_step.get("amount") or 0); row_values.append(fmt(current_amount))
                        else: row_values.append("—")
                        continue
                    if not step:
                        if is_removed: row_values.append("убрано ранее")
                        elif current_amount is None: row_values.append("—")
                        else: row_values.append("не меняется")
                        continue
                    diff = step.get("diff", {})
                    removed = any(rem.get("district","").strip() == dist and rem.get("works","").strip() == name for rem in diff.get("removed", []))
                    if removed: row_values.append(f"убрано от {step['date']}"); is_removed = True; current_amount = None; continue
                    added = next((it for it in diff.get("added", []) if it.get("district","").strip() == dist and it.get("works","").strip() == name), None)
                    if added: current_amount = float(added.get("amount") or 0); row_values.append(fmt(current_amount)); is_removed = False; continue
                    changed = next((c for c in diff.get("changed", []) if c["after"].get("district","").strip() == dist and c["after"].get("works","").strip() == name), None)
                    if changed: current_amount = float(changed["after"].get("amount") or 0); row_values.append(fmt(current_amount)); continue
                    if is_removed: row_values.append("убрано ранее")
                    elif current_amount is None: row_values.append("—")
                    else: row_values.append("не меняется")
                import textwrap
                wrapped_name = "\n".join([name])
                display_values = [dist, wrapped_name] + row_values[2:]
                final_rows.append(display_values)
            self.nakazy_tree.set_sheet_data(final_rows)
            for i, row in enumerate(final_rows):
                if row[1] == "": self.nakazy_tree.highlight_cells(row=i, bg="#eef2f7", fg="#000")
        except Exception as e:
            self.logger.error(f"Ошибка в _populate_nakazy_tab: {e}\n{traceback.format_exc()}")

    def _populate_history_tab(self, timeline):
        rows = []
        for step in timeline:
            d, n = step.get("date", ""), step.get("number", "")
            if step["kind"] == "base":
                base_items = step.get("items", [])
                groups = {}
                for item in base_items:
                    if item.get("status") != "ok": continue
                    dist = item.get("district", "").strip()
                    if not dist: dist = "Без округа"
                    groups.setdefault(dist, []).append(item)
                for dist in sorted(groups.keys()):
                    rows.append([d, n, "БАЗА", f"Округ {dist}", "", ""])
                    for item in groups[dist]: rows.append([d, n, "", dist, item.get("works", ""), fmt(item.get("amount", 0))])
                continue
            diff = step.get("diff", {}); changes_by_dist = {}
            for item in diff.get("added", []):
                dist = item.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("ДОБАВЛЕНО", item, item.get("amount", 0)))
            for item in diff.get("removed", []):
                dist = item.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("УДАЛЕНО", item, item.get("amount", 0)))
            for c in diff.get("changed", []):
                b, a = c["before"], c["after"]; dist = a.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("ИЗМЕНЕНО", a, (b.get("amount", 0), a.get("amount", 0))))
            if not changes_by_dist: continue
            for dist in sorted(changes_by_dist.keys()):
                rows.append([d, n, "", f"Округ {dist}", "", ""])
                for action, item, val in changes_by_dist[dist]:
                    amount_str = f"{fmt(val[0])} → {fmt(val[1])}" if action == "ИЗМЕНЕНО" else fmt(val)
                    rows.append([d, n, action, dist, item.get("works", ""), amount_str])
        self.post_tree.set_sheet_data(rows)
        for i, row in enumerate(rows):
            if row[3].startswith("Округ") or row[3] == "Без округа":
                if not row[2] and not row[4] and not row[5]: self.post_tree.highlight_cells(row=i, bg="#eef2f7", fg="#000")

    def _compare_with_selected_duma(self):
        sel_idx = self.decision_cb.current()
        if sel_idx < 0 or not hasattr(self, 'all_duma_files') or sel_idx >= len(self.all_duma_files): return
        sel_file = self.all_duma_files[sel_idx]; changes_path = Path("changes.json")
        if not changes_path.exists(): return
        data = json.loads(changes_path.read_text(encoding="utf-8")); timeline = data.get("timeline", [])
        selected_step = next((s for s in timeline if s.get("date") == sel_file["date"] and s.get("number") == sel_file["number"]), None)
        if not selected_step:
            self.err_tree.set_sheet_data([["Нет данных", f"В выбранном решении Думы от {sel_file['date']} № {sel_file['number']} не содержится информация по разделу ТОС (Наказы)", "—", "—", "—", "—"]])
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой"); return
        target_items = selected_step.get("items", []); duma_map = {}
        group_mapping = {"10": "1", "12": "2", "20": "3", "27": "4", "31": "5", "33": "6", "МИО Галушко В.Ф.": "7"}
        for item in target_items:
            if item.get("status") != "ok": continue
            dist = item.get("district", "").strip(); g = group_mapping.get(dist)
            if not g: continue
            name = item.get("works", "").strip(); amount = float(item.get("amount") or 0)
            duma_map[(g, name)] = (amount, item.get("institution", ""))
        error_details = []; found_keys = set(); postanovlenie = self.data["editions"][self.selected_edition]["label"]
        app3_events = [e for e in get_effective_events(self.data, self.selected_edition) if e.get("source") == "app3"]
        if len(duma_map) < len(app3_events) * 0.5:
            self.err_tree.set_sheet_data([["Неполные данные", f"В выбранном решении Думы от {sel_file['date']} № {sel_file['number']} не содержится полная информация по разделу ТОС. Найдено {len(duma_map)} мероприятий из {len(app3_events)}. Сравнение невозможно.", "—", "—", "—", "—"]])
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой"); self.notebook.select(self.tab_errors); return
        def get_duma_source(g, name):
            for step in reversed(timeline):
                if step["kind"] == "amendment":
                    diff = step.get("diff", {})
                    for lst in (diff.get("added", []), diff.get("changed", [])):
                        for it in lst:
                            if group_mapping.get(it.get("district", "").strip()) == g and it.get("works", "").strip() == name: return f"от {step['date']} № {step['number']}"
            base = timeline[0]; return f"от {base['date']} № {base['number']} (база)"
        for ev in app3_events:
            g = ev.get("group"); m = re.search(r'«(.*)»', ev["name"]); name = m.group(1) if m else ev["name"]; key = (g, name)
            if key in duma_map:
                found_keys.add(key); expected = duma_map[key][0]; current = get_event_value_at(ev, 2026, self.data, self.selected_edition)
                if abs(current - expected) > 0.01:
                    error_details.append({"id": ev["id"], "name": ev["name"], "type": "Неверная сумма", "current": fmt(current), "expected": fmt(expected), "duma_source": get_duma_source(g, name), "postanovlenie": postanovlenie})
            else:
                error_details.append({"id": ev["id"], "name": ev["name"], "type": "Нет в Думе (лишнее)", "current": fmt(get_event_value_at(ev, 2026, self.data, self.selected_edition)), "expected": "—", "duma_source": get_duma_source(g, name), "postanovlenie": postanovlenie})
        added_details = []; is_latest = (selected_step == timeline[-1])
        if is_latest:
            for (g, name), (amount, inst) in duma_map.items():
                if (g, name) not in found_keys:
                    existing_nums = [int(re.search(r'п\.\s*\d+\.(\d+)', e["name"]).group(1)) for e in app3_events if e.get("group")==g and re.search(r'п\.\s*\d+\.(\d+)', e["name"])]
                    next_num = max(existing_nums) + 1 if existing_nums else 1; new_id = f"duma_{g}_{next_num}"
                    ed = self.data["editions"][self.selected_edition]
                    existing = any(e.get("name") == f"п. {g}.{next_num} «{name}»" for e in ed.get("added", []))
                    if not existing:
                        ed.setdefault("added", []).append({"id": new_id, "source": "app3", "parent": "e_1_1_3", "group": g, "name": f"п. {g}.{next_num} «{name}»", "old_value": amount, "years": {"2026": amount, "2027": 0.0, "2028": 0.0}, "executor": inst, "is_custom": True})
                        added_details.append({"name": f"п. {g}.{next_num} «{name}»", "amount": fmt(amount)})
        self.data["duma_errors"] = [e["id"] for e in error_details]
        self._save_data(explicit=True); self.refresh_table(); self.refresh_totals(); self._update_duma_errors_tab(error_details, added_details)

    def _update_duma_errors_tab(self, errors, added):
        # 1. Сохраняем ошибки
        self.last_errors = errors
        self.last_added = added
        
        # 2. Заполняем таблицу
        data = []
        for e in errors: 
            data.append([e.get("type","—"), e.get("name","—"), e.get("current","—"), e.get("expected","—"), e.get("duma_source","—"), e.get("postanovlenie","—")])
        for a in added: 
            data.append(["Добавлено из Думы", a.get("name","—"), "—", a.get("amount","—"), "—", "—"])
        if not errors and not added: 
            data.append(["Успех", "Расхождений с Думой не найдено.", "—", "—", "—", "—"])
        
        self.err_tree.set_sheet_data(data)
        
        import textwrap
        heights = []
        for row in data:
            text = str(row[1]) if len(row) > 1 else ""
            lines = [text]
            heights.append(max(25, len(lines) * 18 + 5))
        if heights: self.err_tree.set_row_heights(heights)

        # 3. ГЕНЕРИРУЕМ ТЕКСТ И СОХРАНЯЕМ В ПЕРЕМЕННУЮ
        if not errors and not added:
            text_lines = ["✅ РАСХОЖДЕНИЙ НЕ НАЙДЕНО\n\n"]
            text_lines.append("Все мероприятия в Конструкторе полностью совпадают с выбранным решением Думы.\n")
            text_lines.append("Если вы хотите внести изменения, создайте новую редакцию постановления.")
        else:
            text_lines = [f"ВНИМАНИЕ! Найдено проблем: {len(errors) + len(added)}\n"]
            text_lines.append("=" * 60 + "\n\n")
            
            for i, e in enumerate(errors, start=1):
                et = e.get('type', 'Ошибка')
                nm = e.get('name', '—')
                cur = e.get('current', '—')
                exp = e.get('expected', '—')
                src_txt = e.get('duma_source', '—')
                post = e.get('postanovlenie', '—')
                
                text_lines.append(f"❌ ПРОБЛЕМА №{i}: {et.upper()}\n")
                text_lines.append(f"Мероприятие: {nm}\n")
                text_lines.append(f"Сейчас в Конструкторе: {cur}\n")
                text_lines.append(f"По данным Думы: {exp}\n")
                text_lines.append(f"Источник в Думе: {src_txt}\n")
                text_lines.append(f"Редакция Конструктора: {post}\n")
                
                if "Неверная сумма" in et:
                    text_lines.append("\nПОЧЕМУ: Сумма в Конструкторе не совпадает с официальной цифрой из решения Думы.\n")
                    text_lines.append("КАК ИСПРАВИТЬ: Перейдите на вкладку «Мероприятия», дважды кликните по колонке «Станет» для этого мероприятия и введите правильную сумму.\n")
                elif "лишнее" in et:
                    text_lines.append("\nПОЧЕМУ: Этого мероприятия нет в официальном решении Думы. Возможно, оно было отменено или его ошибочно добавили вручную.\n")
                    text_lines.append("КАК ИСПРАВИТЬ: Нажмите правой кнопкой мыши на это мероприятие в таблице и выберите «🗑 Удалить / Утратило силу».\n")
                text_lines.append("-" * 60 + "\n\n")
                
            for a in added:
                text_lines.append(f"✅ ДОБАВЛЕНО ИЗ ДУМЫ: {a.get('name', '—')}\n")
                text_lines.append(f"Сумма: {a.get('amount', '—')}\n")
                text_lines.append("ПОЧЕМУ: Этого мероприятия не хватало в Конструкторе, но оно есть в решении Думы.\n")
                text_lines.append("КАК ИСПРАВИТЬ: Ничего делать не нужно, программа уже добавила его.\n")
                text_lines.append("-" * 60 + "\n\n")
        
        # СОХРАНЯЕМ ТЕКСТ В ПЕРЕМЕННУЮ
        
        # Сразу отображаем его
        self._display_error_report()
        
        # 4. Обновляем заголовки вкладок
        if errors:
            self.notebook.tab(self.tab_errors, text=f"Расхождения ({len(errors)}) ⚠")
            self.notebook.tab(self.tab_error_details, text=f"Ошибки: подробно ({len(errors)}) ⚠")
            self.notebook.select(self.tab_errors)
        elif added:
            self.notebook.tab(self.tab_errors, text=f"Добавлено ({len(added)})")
            self.notebook.tab(self.tab_error_details, text=f"Добавлено ({len(added)})")
            self.notebook.select(self.tab_errors)
        else:
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой (OK)")
            self.notebook.tab(self.tab_error_details, text="Ошибки: подробно")
            self.notebook.select(self.tab_main)

    def _on_duma_decision_change(self, event):
        sel = self.decision_cb.get()
        self.logger.info(f"Выбрано решение Думы для сравнения: «{sel}»")
        self._compare_with_selected_duma()

    def _update_errors_button(self):
        if hasattr(self, 'unresolved_districts') and self.unresolved_districts: self.btn_errors.configure(state="normal")
        else: self.btn_errors.configure(state="disabled")

    def _show_errors_dialog(self):
        if hasattr(self, 'unresolved_districts') and self.unresolved_districts: self._ask_for_missing_districts()
        else: messagebox.showinfo("Ошибки парсинга", "Все округа успешно определены.")

    def _ask_for_missing_districts(self):
        if not hasattr(self, 'unresolved_districts') or not self.unresolved_districts: return
        if hasattr(self, '_error_win') and self._error_win.winfo_exists(): self._error_win.lift(); return
        self._error_win = tk.Toplevel(self.root); self._error_win.title("Ошибка парсинга: не указан округ"); self._error_win.geometry("850x450"); self._error_win.transient(self.root)
        ttk.Label(self._error_win, text="В решениях Думы не удалось определить округ для следующих мероприятий.\nПожалуйста, укажите его (программа запомнит ваш выбор):", font=("TkDefaultFont", 10, "bold"), padding=10).pack()
        canvas = tk.Canvas(self._error_win); scrollbar = ttk.Scrollbar(self._error_win, orient="vertical", command=canvas.yview); scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))); canvas.create_window((0, 0), window=scrollable_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5); scrollbar.pack(side="right", fill="y")
        vars = {}; row = 0; fixes_file = Path("district_fixes.json"); fixes = {}
        if fixes_file.exists():
            try: fixes = json.loads(fixes_file.read_text(encoding="utf-8"))
            except Exception: pass
        for works, data in self.unresolved_districts.items():
            sources_str = ", ".join(data["sources"]); lbl_text = f"{works}\n(Встречается в: {sources_str})"
            ttk.Label(scrollable_frame, text=lbl_text, wraplength=500, justify="left").grid(row=row, column=0, sticky="w", pady=5, padx=5)
            var = tk.StringVar()
            if works in fixes: gid = fixes[works]; val = next((g[1] for g in GROUPS if g[0] == gid), ""); var.set(val)
            choices = [g[1] for g in GROUPS] + ["Без округа"]; cb = ttk.Combobox(scrollable_frame, textvariable=var, state="readonly", values=choices, width=40)
            cb.grid(row=row, column=1, sticky="w", padx=10, pady=5); vars[works] = var; row += 1
        def save():
            for works, var in vars.items():
                val = var.get()
                if not val: messagebox.showwarning("Ошибка", f"Пожалуйста, укажите округ для:\n{works}", parent=self._error_win); return
                if val == "Без округа": gid = "0"
                else: gid = next((g[0] for g in GROUPS if g[1] == val), "")
                if gid is not None: fixes[works] = gid
                if works in self.unresolved_districts: del self.unresolved_districts[works]
            fixes_file.write_text(json.dumps(fixes, ensure_ascii=False, indent=2), encoding="utf-8"); self._update_errors_button(); self._error_win.destroy(); self._sync_from_duma(silent=True)
        ttk.Button(self._error_win, text="💾 Сохранить и продолжить", command=save).pack(pady=10)

    def _populate_nakazy_tab(self, timeline):
        try:
            if not timeline: return
            master_decisions = []
            try:
                data = json.loads(Path("changes.json").read_text(encoding="utf-8"))
                base = timeline[0]; master_decisions.append({"date": base["date"], "number": base["number"], "is_base": True})
                for ch in data.get("changes", []): master_decisions.append({"date": ch["date"], "number": ch["number"], "is_base": False})
                for step in timeline[1:]:
                    if not any(m["date"] == step["date"] and m["number"] == step["number"] for m in master_decisions): master_decisions.append({"date": step["date"], "number": step["number"], "is_base": False})
                def parse_date(d_str):
                    try: return datetime.strptime(d_str, "%d.%m.%Y")
                    except: return datetime.min
                master_decisions.sort(key=lambda x: parse_date(x["date"]))
            except Exception as e: self.logger.error(f"Ошибка чтения changes.json: {e}"); return
            all_events = set()
            for step in timeline:
                for item in step.get("items", []):
                    if item.get("status") == "ok":
                        dist = item.get("district", "").strip()
                        if not dist: dist = "Без округа"
                        all_events.add((dist, item.get("works", "").strip()))
            def sort_key(x):
                dist = x[0]
                if dist.isdigit(): return (int(dist), x[1])
                return (999, x[1])
            sorted_events = sorted(all_events, key=sort_key)
            headers = ["Округ", "Мероприятие"] + [f"{m['date']} N {m['number']}" for m in master_decisions]
            self.nakazy_tree.headers(headers)
            self.nakazy_tree.column_width(0, width=100); self.nakazy_tree.column_width(1, width=300)
            for i in range(2, len(headers)): self.nakazy_tree.column_width(i, width=110)
            timeline_steps = {(s["date"], s["number"]): s for s in timeline}
            final_rows = []; current_district = None
            for event in sorted_events:
                dist, name = event
                if dist != current_district:
                    current_district = dist
                    group_name = f"Округ {dist}" if dist and dist != "0" else "Без округа"
                    final_rows.append([group_name, "", ""] + [""] * len(master_decisions))
                row_values = [dist, name]; current_amount = None; is_removed = False
                for m_dec in master_decisions:
                    step = timeline_steps.get((m_dec["date"], m_dec["number"]))
                    if m_dec["is_base"]:
                        item_in_step = next((it for it in step.get("items", []) if it.get("district","").strip() == dist and it.get("works","").strip() == name and it.get("status") == "ok"), None) if step else None
                        if item_in_step: current_amount = float(item_in_step.get("amount") or 0); row_values.append(fmt(current_amount))
                        else: row_values.append("—")
                        continue
                    if not step:
                        if is_removed: row_values.append("убрано ранее")
                        elif current_amount is None: row_values.append("—")
                        else: row_values.append("не меняется")
                        continue
                    diff = step.get("diff", {})
                    removed = any(rem.get("district","").strip() == dist and rem.get("works","").strip() == name for rem in diff.get("removed", []))
                    if removed: row_values.append(f"убрано от {step['date']}"); is_removed = True; current_amount = None; continue
                    added = next((it for it in diff.get("added", []) if it.get("district","").strip() == dist and it.get("works","").strip() == name), None)
                    if added: current_amount = float(added.get("amount") or 0); row_values.append(fmt(current_amount)); is_removed = False; continue
                    changed = next((c for c in diff.get("changed", []) if c["after"].get("district","").strip() == dist and c["after"].get("works","").strip() == name), None)
                    if changed: current_amount = float(changed["after"].get("amount") or 0); row_values.append(fmt(current_amount)); continue
                    if is_removed: row_values.append("убрано ранее")
                    elif current_amount is None: row_values.append("—")
                    else: row_values.append("не меняется")
                import textwrap
                wrapped_name = "\n".join([name])
                display_values = [dist, wrapped_name] + row_values[2:]
                final_rows.append(display_values)
            self.nakazy_tree.set_sheet_data(final_rows)
            for i, row in enumerate(final_rows):
                if row[1] == "": self.nakazy_tree.highlight_cells(row=i, bg="#eef2f7", fg="#000")
        except Exception as e:
            self.logger.error(f"Ошибка в _populate_nakazy_tab: {e}\n{traceback.format_exc()}")

    def _populate_history_tab(self, timeline):
        rows = []
        for step in timeline:
            d, n = step.get("date", ""), step.get("number", "")
            if step["kind"] == "base":
                base_items = step.get("items", [])
                groups = {}
                for item in base_items:
                    if item.get("status") != "ok": continue
                    dist = item.get("district", "").strip()
                    if not dist: dist = "Без округа"
                    groups.setdefault(dist, []).append(item)
                for dist in sorted(groups.keys()):
                    rows.append([d, n, "БАЗА", f"Округ {dist}", "", ""])
                    for item in groups[dist]: rows.append([d, n, "", dist, item.get("works", ""), fmt(item.get("amount", 0))])
                continue
            diff = step.get("diff", {}); changes_by_dist = {}
            for item in diff.get("added", []):
                dist = item.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("ДОБАВЛЕНО", item, item.get("amount", 0)))
            for item in diff.get("removed", []):
                dist = item.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("УДАЛЕНО", item, item.get("amount", 0)))
            for c in diff.get("changed", []):
                b, a = c["before"], c["after"]; dist = a.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("ИЗМЕНЕНО", a, (b.get("amount", 0), a.get("amount", 0))))
            if not changes_by_dist: continue
            for dist in sorted(changes_by_dist.keys()):
                rows.append([d, n, "", f"Округ {dist}", "", ""])
                for action, item, val in changes_by_dist[dist]:
                    amount_str = f"{fmt(val[0])} → {fmt(val[1])}" if action == "ИЗМЕНЕНО" else fmt(val)
                    rows.append([d, n, action, dist, item.get("works", ""), amount_str])
        self.post_tree.set_sheet_data(rows)
        for i, row in enumerate(rows):
            if row[3].startswith("Округ") or row[3] == "Без округа":
                if not row[2] and not row[4] and not row[5]: self.post_tree.highlight_cells(row=i, bg="#eef2f7", fg="#000")

    def _compare_with_selected_duma(self):
        sel_idx = self.decision_cb.current()
        if sel_idx < 0 or not hasattr(self, 'all_duma_files') or sel_idx >= len(self.all_duma_files): return
        sel_file = self.all_duma_files[sel_idx]; changes_path = Path("changes.json")
        if not changes_path.exists(): return
        data = json.loads(changes_path.read_text(encoding="utf-8")); timeline = data.get("timeline", [])
        selected_step = next((s for s in timeline if s.get("date") == sel_file["date"] and s.get("number") == sel_file["number"]), None)
        if not selected_step:
            self.err_tree.set_sheet_data([["Нет данных", f"В выбранном решении Думы от {sel_file['date']} № {sel_file['number']} не содержится информация по разделу ТОС (Наказы)", "—", "—", "—", "—"]])
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой"); return
        target_items = selected_step.get("items", []); duma_map = {}
        group_mapping = {"10": "1", "12": "2", "20": "3", "27": "4", "31": "5", "33": "6", "МИО Галушко В.Ф.": "7"}
        for item in target_items:
            if item.get("status") != "ok": continue
            dist = item.get("district", "").strip(); g = group_mapping.get(dist)
            if not g: continue
            name = item.get("works", "").strip(); amount = float(item.get("amount") or 0)
            duma_map[(g, name)] = (amount, item.get("institution", ""))
        error_details = []; found_keys = set(); postanovlenie = self.data["editions"][self.selected_edition]["label"]
        app3_events = [e for e in get_effective_events(self.data, self.selected_edition) if e.get("source") == "app3"]
        if len(duma_map) < len(app3_events) * 0.5:
            self.err_tree.set_sheet_data([["Неполные данные", f"В выбранном решении Думы от {sel_file['date']} № {sel_file['number']} не содержится полная информация по разделу ТОС. Найдено {len(duma_map)} мероприятий из {len(app3_events)}. Сравнение невозможно.", "—", "—", "—", "—"]])
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой"); self.notebook.select(self.tab_errors); return
        def get_duma_source(g, name):
            for step in reversed(timeline):
                if step["kind"] == "amendment":
                    diff = step.get("diff", {})
                    for lst in (diff.get("added", []), diff.get("changed", [])):
                        for it in lst:
                            if group_mapping.get(it.get("district", "").strip()) == g and it.get("works", "").strip() == name: return f"от {step['date']} № {step['number']}"
            base = timeline[0]; return f"от {base['date']} № {base['number']} (база)"
        for ev in app3_events:
            g = ev.get("group"); m = re.search(r'«(.*)»', ev["name"]); name = m.group(1) if m else ev["name"]; key = (g, name)
            if key in duma_map:
                found_keys.add(key); expected = duma_map[key][0]; current = get_event_value_at(ev, 2026, self.data, self.selected_edition)
                if abs(current - expected) > 0.01:
                    error_details.append({"id": ev["id"], "name": ev["name"], "type": "Неверная сумма", "current": fmt(current), "expected": fmt(expected), "duma_source": get_duma_source(g, name), "postanovlenie": postanovlenie})
            else:
                error_details.append({"id": ev["id"], "name": ev["name"], "type": "Нет в Думе (лишнее)", "current": fmt(get_event_value_at(ev, 2026, self.data, self.selected_edition)), "expected": "—", "duma_source": get_duma_source(g, name), "postanovlenie": postanovlenie})
        added_details = []; is_latest = (selected_step == timeline[-1])
        if is_latest:
            for (g, name), (amount, inst) in duma_map.items():
                if (g, name) not in found_keys:
                    existing_nums = [int(re.search(r'п\.\s*\d+\.(\d+)', e["name"]).group(1)) for e in app3_events if e.get("group")==g and re.search(r'п\.\s*\d+\.(\d+)', e["name"])]
                    next_num = max(existing_nums) + 1 if existing_nums else 1; new_id = f"duma_{g}_{next_num}"
                    ed = self.data["editions"][self.selected_edition]
                    existing = any(e.get("name") == f"п. {g}.{next_num} «{name}»" for e in ed.get("added", []))
                    if not existing:
                        ed.setdefault("added", []).append({"id": new_id, "source": "app3", "parent": "e_1_1_3", "group": g, "name": f"п. {g}.{next_num} «{name}»", "old_value": amount, "years": {"2026": amount, "2027": 0.0, "2028": 0.0}, "executor": inst, "is_custom": True})
                        added_details.append({"name": f"п. {g}.{next_num} «{name}»", "amount": fmt(amount)})
        self.data["duma_errors"] = [e["id"] for e in error_details]
        self._save_data(explicit=True); self.refresh_table(); self.refresh_totals(); self._update_duma_errors_tab(error_details, added_details)

    def _update_duma_errors_tab(self, errors, added):
        # 1. Заполняем таблицу
        data = []
        for e in errors: data.append([e["type"], e["name"], e["current"], e["expected"], e.get("duma_source", "—"), e.get("postanovlenie", "—")])
        for a in added: data.append(["Добавлено из Думы", a["name"], "—", a["amount"], "—", "—"])
        if not errors and not added: data.append(["Успех", "Расхождений с Думой не найдено.", "—", "—", "—", "—"])
        
        self.err_tree.set_sheet_data(data)
        
        self._auto_resize_rows_in_sheet(self.err_tree)

        # 2. Генерируем текст (теперь метод читает прямо из таблицы)
        self._display_error_report()

        # 3. Переключаем вкладки
        if errors:
            self.notebook.tab(self.tab_errors, text=f"Расхождения ({len(errors)}) ⚠")
            self.notebook.tab(self.tab_error_details, text=f"Ошибки: подробно ({len(errors)}) ⚠")
            self.notebook.select(self.tab_errors)
        elif added:
            self.notebook.tab(self.tab_errors, text=f"Добавлено ({len(added)})")
            self.notebook.tab(self.tab_error_details, text=f"Добавлено ({len(added)})")
            self.notebook.select(self.tab_errors)
        else:
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой (OK)")
            self.notebook.tab(self.tab_error_details, text="Ошибки: подробно")
            self.notebook.select(self.tab_main)

    def _generate_error_report(self, event=None):
        if not hasattr(self, 'error_details_text'): return
        
        self.error_details_text.configure(state="normal")
        self.error_details_text.delete("1.0", tk.END)
        
        # Читаем данные НАПРЯМУЮ из таблицы расхождений
        table_data = []
        if hasattr(self, 'err_tree'):
            try:
                table_data = self.err_tree.get_sheet_data()
            except Exception as e:
                print("DEBUG: ошибка чтения таблицы:", e)
        
        # Фильтруем служебные строки
        real_errors = []
        for row in table_data:
            if not row or len(row) < 4: continue
            if row[0] in ("Успех", "Нет данных", "Неполные данные"): continue
            real_errors.append(row)
        
        if not real_errors:
            self.error_details_text.insert(tk.END, "✅ РАСХОЖДЕНИЙ НЕ НАЙДЕНО\n\n")
            self.error_details_text.insert(tk.END, "Все мероприятия в Конструкторе полностью совпадают с выбранным решением Думы.\n")
            self.error_details_text.insert(tk.END, "Если вы хотите внести изменения, создайте новую редакцию постановления.")
        else:
            self.error_details_text.insert(tk.END, f"ВНИМАНИЕ! Найдено проблем: {len(real_errors)}\n")
            self.error_details_text.insert(tk.END, "=" * 60 + "\n\n")
            
            for i, row in enumerate(real_errors, start=1):
                error_type = row[0] if len(row) > 0 else "—"
                name = row[1] if len(row) > 1 else "—"
                current = row[2] if len(row) > 2 else "—"
                expected = row[3] if len(row) > 3 else "—"
                source = row[4] if len(row) > 4 else "—"
                postanovlenie = row[5] if len(row) > 5 else "—"
                
                self.error_details_text.insert(tk.END, f"❌ ПРОБЛЕМА №{i}: {error_type.upper()}\n")
                self.error_details_text.insert(tk.END, f"Мероприятие: {name}\n")
                self.error_details_text.insert(tk.END, f"Сейчас в Конструкторе: {current}\n")
                self.error_details_text.insert(tk.END, f"По данным Думы: {expected}\n")
                self.error_details_text.insert(tk.END, f"Источник в Думе: {source}\n")
                self.error_details_text.insert(tk.END, f"Редакция Конструктора: {postanovlenie}\n")
                
                if "Неверная сумма" in error_type:
                    self.error_details_text.insert(tk.END, "\nПОЧЕМУ: Сумма в Конструкторе не совпадает с официальной цифрой из решения Думы.\n")
                    self.error_details_text.insert(tk.END, "КАК ИСПРАВИТЬ: Перейдите на вкладку «Мероприятия», дважды кликните по колонке «Станет» для этого мероприятия и введите правильную сумму.\n")
                elif "лишнее" in error_type:
                    self.error_details_text.insert(tk.END, "\nПОЧЕМУ: Этого мероприятия нет в официальном решении Думы. Возможно, оно было отменено или его ошибочно добавили вручную.\n")
                    self.error_details_text.insert(tk.END, "КАК ИСПРАВИТЬ: Нажмите правой кнопкой мыши на это мероприятие в таблице и выберите «🗑 Удалить / Утратило силу» (оно обнулится в текущей редакции).\n")
                self.error_details_text.insert(tk.END, "-" * 60 + "\n\n")
                
        self.error_details_text.configure(state="disabled")
        self.error_details_text.see(tk.END)

    def _on_duma_decision_change(self, event):
        sel = self.decision_cb.get()
        self.logger.info(f"Выбрано решение Думы для сравнения: «{sel}»")
        self._compare_with_selected_duma()

    def _update_errors_button(self):
        if hasattr(self, 'unresolved_districts') and self.unresolved_districts: self.btn_errors.configure(state="normal")
        else: self.btn_errors.configure(state="disabled")

    def _show_errors_dialog(self):
        if hasattr(self, 'unresolved_districts') and self.unresolved_districts: self._ask_for_missing_districts()
        else: messagebox.showinfo("Ошибки парсинга", "Все округа успешно определены.")

    def _ask_for_missing_districts(self):
        if not hasattr(self, 'unresolved_districts') or not self.unresolved_districts: return
        if hasattr(self, '_error_win') and self._error_win.winfo_exists(): self._error_win.lift(); return
        self._error_win = tk.Toplevel(self.root); self._error_win.title("Ошибка парсинга: не указан округ"); self._error_win.geometry("850x450"); self._error_win.transient(self.root)
        ttk.Label(self._error_win, text="В решениях Думы не удалось определить округ для следующих мероприятий.\nПожалуйста, укажите его (программа запомнит ваш выбор):", font=("TkDefaultFont", 10, "bold"), padding=10).pack()
        canvas = tk.Canvas(self._error_win); scrollbar = ttk.Scrollbar(self._error_win, orient="vertical", command=canvas.yview); scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))); canvas.create_window((0, 0), window=scrollable_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5); scrollbar.pack(side="right", fill="y")
        vars = {}; row = 0; fixes_file = Path("district_fixes.json"); fixes = {}
        if fixes_file.exists():
            try: fixes = json.loads(fixes_file.read_text(encoding="utf-8"))
            except Exception: pass
        for works, data in self.unresolved_districts.items():
            sources_str = ", ".join(data["sources"]); lbl_text = f"{works}\n(Встречается в: {sources_str})"
            ttk.Label(scrollable_frame, text=lbl_text, wraplength=500, justify="left").grid(row=row, column=0, sticky="w", pady=5, padx=5)
            var = tk.StringVar()
            if works in fixes: gid = fixes[works]; val = next((g[1] for g in GROUPS if g[0] == gid), ""); var.set(val)
            choices = [g[1] for g in GROUPS] + ["Без округа"]; cb = ttk.Combobox(scrollable_frame, textvariable=var, state="readonly", values=choices, width=40)
            cb.grid(row=row, column=1, sticky="w", padx=10, pady=5); vars[works] = var; row += 1
        def save():
            for works, var in vars.items():
                val = var.get()
                if not val: messagebox.showwarning("Ошибка", f"Пожалуйста, укажите округ для:\n{works}", parent=self._error_win); return
                if val == "Без округа": gid = "0"
                else: gid = next((g[0] for g in GROUPS if g[1] == val), "")
                if gid is not None: fixes[works] = gid
                if works in self.unresolved_districts: del self.unresolved_districts[works]
            fixes_file.write_text(json.dumps(fixes, ensure_ascii=False, indent=2), encoding="utf-8"); self._update_errors_button(); self._error_win.destroy(); self._sync_from_duma(silent=True)
        ttk.Button(self._error_win, text="💾 Сохранить и продолжить", command=save).pack(pady=10)

    def _populate_nakazy_tab(self, timeline):
        try:
            if not timeline: return
            master_decisions = []
            try:
                data = json.loads(Path("changes.json").read_text(encoding="utf-8"))
                base = timeline[0]; master_decisions.append({"date": base["date"], "number": base["number"], "is_base": True})
                for ch in data.get("changes", []): master_decisions.append({"date": ch["date"], "number": ch["number"], "is_base": False})
                for step in timeline[1:]:
                    if not any(m["date"] == step["date"] and m["number"] == step["number"] for m in master_decisions): master_decisions.append({"date": step["date"], "number": step["number"], "is_base": False})
                def parse_date(d_str):
                    try: return datetime.strptime(d_str, "%d.%m.%Y")
                    except: return datetime.min
                master_decisions.sort(key=lambda x: parse_date(x["date"]))
            except Exception as e: self.logger.error(f"Ошибка чтения changes.json: {e}"); return
            all_events = set()
            for step in timeline:
                for item in step.get("items", []):
                    if item.get("status") == "ok":
                        dist = item.get("district", "").strip()
                        if not dist: dist = "Без округа"
                        all_events.add((dist, item.get("works", "").strip()))
            def sort_key(x):
                dist = x[0]
                if dist.isdigit(): return (int(dist), x[1])
                return (999, x[1])
            sorted_events = sorted(all_events, key=sort_key)
            headers = ["Округ", "Мероприятие"] + [f"{m['date']} N {m['number']}" for m in master_decisions]
            self.nakazy_tree.headers(headers)
            self.nakazy_tree.column_width(0, width=100); self.nakazy_tree.column_width(1, width=300)
            for i in range(2, len(headers)): self.nakazy_tree.column_width(i, width=110)
            timeline_steps = {(s["date"], s["number"]): s for s in timeline}
            final_rows = []; current_district = None
            for event in sorted_events:
                dist, name = event
                if dist != current_district:
                    current_district = dist
                    group_name = f"Округ {dist}" if dist and dist != "0" else "Без округа"
                    final_rows.append([group_name, "", ""] + [""] * len(master_decisions))
                row_values = [dist, name]; current_amount = None; is_removed = False
                for m_dec in master_decisions:
                    step = timeline_steps.get((m_dec["date"], m_dec["number"]))
                    if m_dec["is_base"]:
                        item_in_step = next((it for it in step.get("items", []) if it.get("district","").strip() == dist and it.get("works","").strip() == name and it.get("status") == "ok"), None) if step else None
                        if item_in_step: current_amount = float(item_in_step.get("amount") or 0); row_values.append(fmt(current_amount))
                        else: row_values.append("—")
                        continue
                    if not step:
                        if is_removed: row_values.append("убрано ранее")
                        elif current_amount is None: row_values.append("—")
                        else: row_values.append("не меняется")
                        continue
                    diff = step.get("diff", {})
                    removed = any(rem.get("district","").strip() == dist and rem.get("works","").strip() == name for rem in diff.get("removed", []))
                    if removed: row_values.append(f"убрано от {step['date']}"); is_removed = True; current_amount = None; continue
                    added = next((it for it in diff.get("added", []) if it.get("district","").strip() == dist and it.get("works","").strip() == name), None)
                    if added: current_amount = float(added.get("amount") or 0); row_values.append(fmt(current_amount)); is_removed = False; continue
                    changed = next((c for c in diff.get("changed", []) if c["after"].get("district","").strip() == dist and c["after"].get("works","").strip() == name), None)
                    if changed: current_amount = float(changed["after"].get("amount") or 0); row_values.append(fmt(current_amount)); continue
                    if is_removed: row_values.append("убрано ранее")
                    elif current_amount is None: row_values.append("—")
                    else: row_values.append("не меняется")
                import textwrap
                wrapped_name = "\n".join([name])
                display_values = [dist, wrapped_name] + row_values[2:]
                final_rows.append(display_values)
            self.nakazy_tree.set_sheet_data(final_rows)
            for i, row in enumerate(final_rows):
                if row[1] == "": self.nakazy_tree.highlight_cells(row=i, bg="#eef2f7", fg="#000")
        except Exception as e:
            self.logger.error(f"Ошибка в _populate_nakazy_tab: {e}\n{traceback.format_exc()}")

    def _populate_history_tab(self, timeline):
        rows = []
        for step in timeline:
            d, n = step.get("date", ""), step.get("number", "")
            if step["kind"] == "base":
                base_items = step.get("items", [])
                groups = {}
                for item in base_items:
                    if item.get("status") != "ok": continue
                    dist = item.get("district", "").strip()
                    if not dist: dist = "Без округа"
                    groups.setdefault(dist, []).append(item)
                for dist in sorted(groups.keys()):
                    rows.append([d, n, "БАЗА", f"Округ {dist}", "", ""])
                    for item in groups[dist]: rows.append([d, n, "", dist, item.get("works", ""), fmt(item.get("amount", 0))])
                continue
            diff = step.get("diff", {}); changes_by_dist = {}
            for item in diff.get("added", []):
                dist = item.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("ДОБАВЛЕНО", item, item.get("amount", 0)))
            for item in diff.get("removed", []):
                dist = item.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("УДАЛЕНО", item, item.get("amount", 0)))
            for c in diff.get("changed", []):
                b, a = c["before"], c["after"]; dist = a.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("ИЗМЕНЕНО", a, (b.get("amount", 0), a.get("amount", 0))))
            if not changes_by_dist: continue
            for dist in sorted(changes_by_dist.keys()):
                rows.append([d, n, "", f"Округ {dist}", "", ""])
                for action, item, val in changes_by_dist[dist]:
                    amount_str = f"{fmt(val[0])} → {fmt(val[1])}" if action == "ИЗМЕНЕНО" else fmt(val)
                    rows.append([d, n, action, dist, item.get("works", ""), amount_str])
        self.post_tree.set_sheet_data(rows)
        for i, row in enumerate(rows):
            if row[3].startswith("Округ") or row[3] == "Без округа":
                if not row[2] and not row[4] and not row[5]: self.post_tree.highlight_cells(row=i, bg="#eef2f7", fg="#000")

    def _compare_with_selected_duma(self):
        sel_idx = self.decision_cb.current()
        if sel_idx < 0 or not hasattr(self, 'all_duma_files') or sel_idx >= len(self.all_duma_files): return
        sel_file = self.all_duma_files[sel_idx]; changes_path = Path("changes.json")
        if not changes_path.exists(): return
        data = json.loads(changes_path.read_text(encoding="utf-8")); timeline = data.get("timeline", [])
        selected_step = next((s for s in timeline if s.get("date") == sel_file["date"] and s.get("number") == sel_file["number"]), None)
        if not selected_step:
            self.err_tree.set_sheet_data([["Нет данных", f"В выбранном решении Думы от {sel_file['date']} № {sel_file['number']} не содержится информация по разделу ТОС (Наказы)", "—", "—", "—", "—"]])
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой"); return
        target_items = selected_step.get("items", []); duma_map = {}
        group_mapping = {"10": "1", "12": "2", "20": "3", "27": "4", "31": "5", "33": "6", "МИО Галушко В.Ф.": "7"}
        for item in target_items:
            if item.get("status") != "ok": continue
            dist = item.get("district", "").strip(); g = group_mapping.get(dist)
            if not g: continue
            name = item.get("works", "").strip(); amount = float(item.get("amount") or 0)
            duma_map[(g, name)] = (amount, item.get("institution", ""))
        error_details = []; found_keys = set(); postanovlenie = self.data["editions"][self.selected_edition]["label"]
        app3_events = [e for e in get_effective_events(self.data, self.selected_edition) if e.get("source") == "app3"]
        if len(duma_map) < len(app3_events) * 0.5:
            self.err_tree.set_sheet_data([["Неполные данные", f"В выбранном решении Думы от {sel_file['date']} № {sel_file['number']} не содержится полная информация по разделу ТОС. Найдено {len(duma_map)} мероприятий из {len(app3_events)}. Сравнение невозможно.", "—", "—", "—", "—"]])
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой"); self.notebook.select(self.tab_errors); return
        def get_duma_source(g, name):
            for step in reversed(timeline):
                if step["kind"] == "amendment":
                    diff = step.get("diff", {})
                    for lst in (diff.get("added", []), diff.get("changed", [])):
                        for it in lst:
                            if group_mapping.get(it.get("district", "").strip()) == g and it.get("works", "").strip() == name: return f"от {step['date']} № {step['number']}"
            base = timeline[0]; return f"от {base['date']} № {base['number']} (база)"
        for ev in app3_events:
            g = ev.get("group"); m = re.search(r'«(.*)»', ev["name"]); name = m.group(1) if m else ev["name"]; key = (g, name)
            if key in duma_map:
                found_keys.add(key); expected = duma_map[key][0]; current = get_event_value_at(ev, 2026, self.data, self.selected_edition)
                if abs(current - expected) > 0.01:
                    error_details.append({"id": ev["id"], "name": ev["name"], "type": "Неверная сумма", "current": fmt(current), "expected": fmt(expected), "duma_source": get_duma_source(g, name), "postanovlenie": postanovlenie})
            else:
                error_details.append({"id": ev["id"], "name": ev["name"], "type": "Нет в Думе (лишнее)", "current": fmt(get_event_value_at(ev, 2026, self.data, self.selected_edition)), "expected": "—", "duma_source": get_duma_source(g, name), "postanovlenie": postanovlenie})
        added_details = []; is_latest = (selected_step == timeline[-1])
        if is_latest:
            for (g, name), (amount, inst) in duma_map.items():
                if (g, name) not in found_keys:
                    existing_nums = [int(re.search(r'п\.\s*\d+\.(\d+)', e["name"]).group(1)) for e in app3_events if e.get("group")==g and re.search(r'п\.\s*\d+\.(\d+)', e["name"])]
                    next_num = max(existing_nums) + 1 if existing_nums else 1; new_id = f"duma_{g}_{next_num}"
                    ed = self.data["editions"][self.selected_edition]
                    existing = any(e.get("name") == f"п. {g}.{next_num} «{name}»" for e in ed.get("added", []))
                    if not existing:
                        ed.setdefault("added", []).append({"id": new_id, "source": "app3", "parent": "e_1_1_3", "group": g, "name": f"п. {g}.{next_num} «{name}»", "old_value": amount, "years": {"2026": amount, "2027": 0.0, "2028": 0.0}, "executor": inst, "is_custom": True})
                        added_details.append({"name": f"п. {g}.{next_num} «{name}»", "amount": fmt(amount)})
        self.data["duma_errors"] = [e["id"] for e in error_details]
        self._save_data(explicit=True); self.refresh_table(); self.refresh_totals(); self._update_duma_errors_tab(error_details, added_details)

    def _update_duma_errors_tab(self, errors, added):
        self.last_errors = errors
        self.last_added = added
        
        # 1. Таблица
        data = []
        for e in errors: data.append([e["type"], e["name"], e["current"], e["expected"], e.get("duma_source", "—"), e.get("postanovlenie", "—")])
        for a in added: data.append(["Добавлено из Думы", a["name"], "—", a["amount"], "—", "—"])
        if not errors and not added: data.append(["Успех", "Расхождений с Думой не найдено.", "—", "—", "—", "—"])
        
        self.err_tree.set_sheet_data(data)
        
        import textwrap
        heights = []
        for row in data:
            text = str(row[1]) if len(row) > 1 else ""; lines = [text]
            heights.append(max(25, len(lines) * 18 + 5))
        if heights: self.err_tree.set_row_heights(heights)

        # 2. Сохраняем и генерируем текст
        self.last_errors = errors
        self.last_added = added
        self._generate_error_report(errors, added)

        # 3. Переключение вкладок
        if errors:
            self.notebook.tab(self.tab_errors, text=f"Расхождения ({len(errors)}) ⚠")
            self.notebook.tab(self.tab_error_details, text=f"Ошибки: подробно ({len(errors)}) ⚠")
            self.notebook.select(self.tab_errors)
        elif added:
            self.notebook.tab(self.tab_errors, text=f"Добавлено ({len(added)})")
            self.notebook.tab(self.tab_error_details, text=f"Добавлено ({len(added)})")
            self.notebook.select(self.tab_errors)
        else:
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой (OK)")
            self.notebook.tab(self.tab_error_details, text="Ошибки: подробно")
            self.notebook.select(self.tab_main)

    def _generate_error_report(self, errors=None, added=None):
        if not hasattr(self, 'error_details_text'): return
        
        # Пытаемся взять из памяти, если не передали
        if errors is None: errors = getattr(self, 'last_errors', [])
        if added is None: added = getattr(self, 'last_added', [])
        
        # Если в памяти пусто, но таблица полна — восстанавливаем из таблицы
        if not errors and hasattr(self, 'err_tree'):
            try:
                sheet_data = self.err_tree.get_sheet_data()
                # Пропускаем заголовки, если они есть (у tksheet заголовки отдельно)
                for row in sheet_data:
                    if not row or len(row) < 4: continue
                    if row[0] == "Успех" or row[0] == "Нет данных" or row[0] == "Неполные данные": continue
                    
                    errors.append({
                        "type": row[0],
                        "name": row[1],
                        "current": row[2],
                        "expected": row[3],
                        "duma_source": row[4] if len(row) > 4 else "—",
                        "postanovlenie": row[5] if len(row) > 5 else "—"
                    })
            except Exception:
                pass

        self.error_details_text.configure(state="normal")
        self.error_details_text.delete("1.0", tk.END)
        
        if not errors and not added:
            self.error_details_text.insert(tk.END, "✅ РАСХОЖДЕНИЙ НЕ НАЙДЕНО\n\n")
            self.error_details_text.insert(tk.END, "Все мероприятия в Конструкторе полностью совпадают с выбранным решением Думы.\n")
            self.error_details_text.insert(tk.END, "Если вы хотите внести изменения, создайте новую редакцию постановления.")
        else:
            self.error_details_text.insert(tk.END, f"ВНИМАНИЕ! Найдено проблем: {len(errors) + len(added)}\n")
            self.error_details_text.insert(tk.END, "=" * 60 + "\n\n")
            
            for i, e in enumerate(errors, start=1):
                self.error_details_text.insert(tk.END, f"❌ ПРОБЛЕМА №{i}: {e.get('type', 'Ошибка').upper()}\n")
                self.error_details_text.insert(tk.END, f"Мероприятие: {e.get('name', '—')}\n")
                self.error_details_text.insert(tk.END, f"Сейчас в Конструкторе: {e.get('current', '—')}\n")
                self.error_details_text.insert(tk.END, f"По данным Думы: {e.get('expected', '—')}\n")
                self.error_details_text.insert(tk.END, f"Источник в Думе: {e.get('duma_source', '—')}\n")
                self.error_details_text.insert(tk.END, f"Редакция Конструктора: {e.get('postanovlenie', '—')}\n")
                
                if e.get('type') == "Неверная сумма":
                    self.error_details_text.insert(tk.END, "\nПОЧЕМУ: Сумма в Конструкторе не совпадает с официальной цифрой из решения Думы.\n")
                    self.error_details_text.insert(tk.END, "КАК ИСПРАВИТЬ: Перейдите на вкладку «Мероприятия», дважды кликните по колонке «Станет» для этого мероприятия и введите правильную сумму.\n")
                elif e.get('type') == "Нет в Думе (лишнее)":
                    self.error_details_text.insert(tk.END, "\nПОЧЕМУ: Этого мероприятия нет в официальном решении Думы. Возможно, оно было отменено или его ошибочно добавили вручную.\n")
                    self.error_details_text.insert(tk.END, "КАК ИСПРАВИТЬ: Нажмите правой кнопкой мыши на это мероприятие в таблице и выберите «🗑 Удалить / Утратило силу» (оно обнулится в текущей редакции).\n")
                self.error_details_text.insert(tk.END, "-" * 60 + "\n\n")
                
            for a in added:
                self.error_details_text.insert(tk.END, f"✅ ДОБАВЛЕНО ИЗ ДУМЫ: {a.get('name', '—')}\n")
                self.error_details_text.insert(tk.END, f"Сумма: {a.get('amount', '—')}\n")
                self.error_details_text.insert(tk.END, "ПОЧЕМУ: Этого мероприятия не хватало в Конструкторе, но оно есть в решении Думы.\n")
                self.error_details_text.insert(tk.END, "КАК ИСПРАВИТЬ: Ничего делать не нужно, программа уже добавила его в текущую редакцию.\n")
                self.error_details_text.insert(tk.END, "-" * 60 + "\n\n")
                
        self.error_details_text.configure(state="disabled")
        self.error_details_text.see(tk.END)

    def _on_duma_decision_change(self, event):
        sel = self.decision_cb.get()
        self.logger.info(f"Выбрано решение Думы для сравнения: «{sel}»")
        self._compare_with_selected_duma()

    def _update_errors_button(self):
        if hasattr(self, 'unresolved_districts') and self.unresolved_districts: self.btn_errors.configure(state="normal")
        else: self.btn_errors.configure(state="disabled")

    def _show_errors_dialog(self):
        if hasattr(self, 'unresolved_districts') and self.unresolved_districts: self._ask_for_missing_districts()
        else: messagebox.showinfo("Ошибки парсинга", "Все округа успешно определены.")

    def _ask_for_missing_districts(self):
        if not hasattr(self, 'unresolved_districts') or not self.unresolved_districts: return
        if hasattr(self, '_error_win') and self._error_win.winfo_exists(): self._error_win.lift(); return
        self._error_win = tk.Toplevel(self.root); self._error_win.title("Ошибка парсинга: не указан округ"); self._error_win.geometry("850x450"); self._error_win.transient(self.root)
        ttk.Label(self._error_win, text="В решениях Думы не удалось определить округ для следующих мероприятий.\nПожалуйста, укажите его (программа запомнит ваш выбор):", font=("TkDefaultFont", 10, "bold"), padding=10).pack()
        canvas = tk.Canvas(self._error_win); scrollbar = ttk.Scrollbar(self._error_win, orient="vertical", command=canvas.yview); scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))); canvas.create_window((0, 0), window=scrollable_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5); scrollbar.pack(side="right", fill="y")
        vars = {}; row = 0; fixes_file = Path("district_fixes.json"); fixes = {}
        if fixes_file.exists():
            try: fixes = json.loads(fixes_file.read_text(encoding="utf-8"))
            except Exception: pass
        for works, data in self.unresolved_districts.items():
            sources_str = ", ".join(data["sources"]); lbl_text = f"{works}\n(Встречается в: {sources_str})"
            ttk.Label(scrollable_frame, text=lbl_text, wraplength=500, justify="left").grid(row=row, column=0, sticky="w", pady=5, padx=5)
            var = tk.StringVar()
            if works in fixes: gid = fixes[works]; val = next((g[1] for g in GROUPS if g[0] == gid), ""); var.set(val)
            choices = [g[1] for g in GROUPS] + ["Без округа"]; cb = ttk.Combobox(scrollable_frame, textvariable=var, state="readonly", values=choices, width=40)
            cb.grid(row=row, column=1, sticky="w", padx=10, pady=5); vars[works] = var; row += 1
        def save():
            for works, var in vars.items():
                val = var.get()
                if not val: messagebox.showwarning("Ошибка", f"Пожалуйста, укажите округ для:\n{works}", parent=self._error_win); return
                if val == "Без округа": gid = "0"
                else: gid = next((g[0] for g in GROUPS if g[1] == val), "")
                if gid is not None: fixes[works] = gid
                if works in self.unresolved_districts: del self.unresolved_districts[works]
            fixes_file.write_text(json.dumps(fixes, ensure_ascii=False, indent=2), encoding="utf-8"); self._update_errors_button(); self._error_win.destroy(); self._sync_from_duma(silent=True)
        ttk.Button(self._error_win, text="💾 Сохранить и продолжить", command=save).pack(pady=10)

    def _populate_nakazy_tab(self, timeline):
        try:
            if not timeline: return
            master_decisions = []
            try:
                data = json.loads(Path("changes.json").read_text(encoding="utf-8"))
                base = timeline[0]; master_decisions.append({"date": base["date"], "number": base["number"], "is_base": True})
                for ch in data.get("changes", []): master_decisions.append({"date": ch["date"], "number": ch["number"], "is_base": False})
                for step in timeline[1:]:
                    if not any(m["date"] == step["date"] and m["number"] == step["number"] for m in master_decisions): master_decisions.append({"date": step["date"], "number": step["number"], "is_base": False})
                def parse_date(d_str):
                    try: return datetime.strptime(d_str, "%d.%m.%Y")
                    except: return datetime.min
                master_decisions.sort(key=lambda x: parse_date(x["date"]))
            except Exception as e: self.logger.error(f"Ошибка чтения changes.json: {e}"); return
            all_events = set()
            for step in timeline:
                for item in step.get("items", []):
                    if item.get("status") == "ok":
                        dist = item.get("district", "").strip()
                        if not dist: dist = "Без округа"
                        all_events.add((dist, item.get("works", "").strip()))
            def sort_key(x):
                dist = x[0]
                if dist.isdigit(): return (int(dist), x[1])
                return (999, x[1])
            sorted_events = sorted(all_events, key=sort_key)
            headers = ["Округ", "Мероприятие"] + [f"{m['date']} N {m['number']}" for m in master_decisions]
            self.nakazy_tree.headers(headers)
            self.nakazy_tree.column_width(0, width=100); self.nakazy_tree.column_width(1, width=300)
            for i in range(2, len(headers)): self.nakazy_tree.column_width(i, width=110)
            timeline_steps = {(s["date"], s["number"]): s for s in timeline}
            final_rows = []; current_district = None
            for event in sorted_events:
                dist, name = event
                if dist != current_district:
                    current_district = dist
                    group_name = f"Округ {dist}" if dist and dist != "0" else "Без округа"
                    final_rows.append([group_name, "", ""] + [""] * len(master_decisions))
                row_values = [dist, name]; current_amount = None; is_removed = False
                for m_dec in master_decisions:
                    step = timeline_steps.get((m_dec["date"], m_dec["number"]))
                    if m_dec["is_base"]:
                        item_in_step = next((it for it in step.get("items", []) if it.get("district","").strip() == dist and it.get("works","").strip() == name and it.get("status") == "ok"), None) if step else None
                        if item_in_step: current_amount = float(item_in_step.get("amount") or 0); row_values.append(fmt(current_amount))
                        else: row_values.append("—")
                        continue
                    if not step:
                        if is_removed: row_values.append("убрано ранее")
                        elif current_amount is None: row_values.append("—")
                        else: row_values.append("не меняется")
                        continue
                    diff = step.get("diff", {})
                    removed = any(rem.get("district","").strip() == dist and rem.get("works","").strip() == name for rem in diff.get("removed", []))
                    if removed: row_values.append(f"убрано от {step['date']}"); is_removed = True; current_amount = None; continue
                    added = next((it for it in diff.get("added", []) if it.get("district","").strip() == dist and it.get("works","").strip() == name), None)
                    if added: current_amount = float(added.get("amount") or 0); row_values.append(fmt(current_amount)); is_removed = False; continue
                    changed = next((c for c in diff.get("changed", []) if c["after"].get("district","").strip() == dist and c["after"].get("works","").strip() == name), None)
                    if changed: current_amount = float(changed["after"].get("amount") or 0); row_values.append(fmt(current_amount)); continue
                    if is_removed: row_values.append("убрано ранее")
                    elif current_amount is None: row_values.append("—")
                    else: row_values.append("не меняется")
                import textwrap
                wrapped_name = "\n".join([name])
                display_values = [dist, wrapped_name] + row_values[2:]
                final_rows.append(display_values)
            self.nakazy_tree.set_sheet_data(final_rows)
            for i, row in enumerate(final_rows):
                if row[1] == "": self.nakazy_tree.highlight_cells(row=i, bg="#eef2f7", fg="#000")
        except Exception as e:
            self.logger.error(f"Ошибка в _populate_nakazy_tab: {e}\n{traceback.format_exc()}")

    def _populate_history_tab(self, timeline):
        rows = []
        for step in timeline:
            d, n = step.get("date", ""), step.get("number", "")
            if step["kind"] == "base":
                base_items = step.get("items", [])
                groups = {}
                for item in base_items:
                    if item.get("status") != "ok": continue
                    dist = item.get("district", "").strip()
                    if not dist: dist = "Без округа"
                    groups.setdefault(dist, []).append(item)
                for dist in sorted(groups.keys()):
                    rows.append([d, n, "БАЗА", f"Округ {dist}", "", ""])
                    for item in groups[dist]: rows.append([d, n, "", dist, item.get("works", ""), fmt(item.get("amount", 0))])
                continue
            diff = step.get("diff", {}); changes_by_dist = {}
            for item in diff.get("added", []):
                dist = item.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("ДОБАВЛЕНО", item, item.get("amount", 0)))
            for item in diff.get("removed", []):
                dist = item.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("УДАЛЕНО", item, item.get("amount", 0)))
            for c in diff.get("changed", []):
                b, a = c["before"], c["after"]; dist = a.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("ИЗМЕНЕНО", a, (b.get("amount", 0), a.get("amount", 0))))
            if not changes_by_dist: continue
            for dist in sorted(changes_by_dist.keys()):
                rows.append([d, n, "", f"Округ {dist}", "", ""])
                for action, item, val in changes_by_dist[dist]:
                    amount_str = f"{fmt(val[0])} → {fmt(val[1])}" if action == "ИЗМЕНЕНО" else fmt(val)
                    rows.append([d, n, action, dist, item.get("works", ""), amount_str])
        self.post_tree.set_sheet_data(rows)
        for i, row in enumerate(rows):
            if row[3].startswith("Округ") or row[3] == "Без округа":
                if not row[2] and not row[4] and not row[5]: self.post_tree.highlight_cells(row=i, bg="#eef2f7", fg="#000")

    def _compare_with_selected_duma(self):
        sel_idx = self.decision_cb.current()
        if sel_idx < 0 or not hasattr(self, 'all_duma_files') or sel_idx >= len(self.all_duma_files): return
        sel_file = self.all_duma_files[sel_idx]; changes_path = Path("changes.json")
        if not changes_path.exists(): return
        data = json.loads(changes_path.read_text(encoding="utf-8")); timeline = data.get("timeline", [])
        selected_step = next((s for s in timeline if s.get("date") == sel_file["date"] and s.get("number") == sel_file["number"]), None)
        if not selected_step:
            self.err_tree.set_sheet_data([["Нет данных", f"В выбранном решении Думы от {sel_file['date']} № {sel_file['number']} не содержится информация по разделу ТОС (Наказы)", "—", "—", "—", "—"]])
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой"); return
        target_items = selected_step.get("items", []); duma_map = {}
        group_mapping = {"10": "1", "12": "2", "20": "3", "27": "4", "31": "5", "33": "6", "МИО Галушко В.Ф.": "7"}
        for item in target_items:
            if item.get("status") != "ok": continue
            dist = item.get("district", "").strip(); g = group_mapping.get(dist)
            if not g: continue
            name = item.get("works", "").strip(); amount = float(item.get("amount") or 0)
            duma_map[(g, name)] = (amount, item.get("institution", ""))
        error_details = []; found_keys = set(); postanovlenie = self.data["editions"][self.selected_edition]["label"]
        app3_events = [e for e in get_effective_events(self.data, self.selected_edition) if e.get("source") == "app3"]
        if len(duma_map) < len(app3_events) * 0.5:
            self.err_tree.set_sheet_data([["Неполные данные", f"В выбранном решении Думы от {sel_file['date']} № {sel_file['number']} не содержится полная информация по разделу ТОС. Найдено {len(duma_map)} мероприятий из {len(app3_events)}. Сравнение невозможно.", "—", "—", "—", "—"]])
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой"); self.notebook.select(self.tab_errors); return
        def get_duma_source(g, name):
            for step in reversed(timeline):
                if step["kind"] == "amendment":
                    diff = step.get("diff", {})
                    for lst in (diff.get("added", []), diff.get("changed", [])):
                        for it in lst:
                            if group_mapping.get(it.get("district", "").strip()) == g and it.get("works", "").strip() == name: return f"от {step['date']} № {step['number']}"
            base = timeline[0]; return f"от {base['date']} № {base['number']} (база)"
        for ev in app3_events:
            g = ev.get("group"); m = re.search(r'«(.*)»', ev["name"]); name = m.group(1) if m else ev["name"]; key = (g, name)
            if key in duma_map:
                found_keys.add(key); expected = duma_map[key][0]; current = get_event_value_at(ev, 2026, self.data, self.selected_edition)
                if abs(current - expected) > 0.01:
                    error_details.append({"id": ev["id"], "name": ev["name"], "type": "Неверная сумма", "current": fmt(current), "expected": fmt(expected), "duma_source": get_duma_source(g, name), "postanovlenie": postanovlenie})
            else:
                error_details.append({"id": ev["id"], "name": ev["name"], "type": "Нет в Думе (лишнее)", "current": fmt(get_event_value_at(ev, 2026, self.data, self.selected_edition)), "expected": "—", "duma_source": get_duma_source(g, name), "postanovlenie": postanovlenie})
        added_details = []; is_latest = (selected_step == timeline[-1])
        if is_latest:
            for (g, name), (amount, inst) in duma_map.items():
                if (g, name) not in found_keys:
                    existing_nums = [int(re.search(r'п\.\s*\d+\.(\d+)', e["name"]).group(1)) for e in app3_events if e.get("group")==g and re.search(r'п\.\s*\d+\.(\d+)', e["name"])]
                    next_num = max(existing_nums) + 1 if existing_nums else 1; new_id = f"duma_{g}_{next_num}"
                    ed = self.data["editions"][self.selected_edition]
                    existing = any(e.get("name") == f"п. {g}.{next_num} «{name}»" for e in ed.get("added", []))
                    if not existing:
                        ed.setdefault("added", []).append({"id": new_id, "source": "app3", "parent": "e_1_1_3", "group": g, "name": f"п. {g}.{next_num} «{name}»", "old_value": amount, "years": {"2026": amount, "2027": 0.0, "2028": 0.0}, "executor": inst, "is_custom": True})
                        added_details.append({"name": f"п. {g}.{next_num} «{name}»", "amount": fmt(amount)})
        self.data["duma_errors"] = [e["id"] for e in error_details]
        self._save_data(explicit=True); self.refresh_table(); self.refresh_totals(); self._update_duma_errors_tab(error_details, added_details)

    def _update_duma_errors_tab(self, errors, added):
        self.last_errors = errors
        self.last_added = added
        
        # 1. Таблица
        data = []
        for e in errors: data.append([e["type"], e["name"], e["current"], e["expected"], e.get("duma_source", "—"), e.get("postanovlenie", "—")])
        for a in added: data.append(["Добавлено из Думы", a["name"], "—", a["amount"], "—", "—"])
        if not errors and not added: data.append(["Успех", "Расхождений с Думой не найдено.", "—", "—", "—", "—"])
        
        self.err_tree.set_sheet_data(data)
        
        import textwrap
        heights = []
        for row in data:
            text = str(row[1]) if len(row) > 1 else ""; lines = [text]
            heights.append(max(25, len(lines) * 18 + 5))
        if heights: self.err_tree.set_row_heights(heights)

        # 2. Генерируем текст и ПЕРЕДАЕМ туда ошибки явно
        self._generate_error_report(errors, added)

        # 3. Переключение вкладок
        if errors:
            self.notebook.tab(self.tab_errors, text=f"Расхождения ({len(errors)}) ⚠")
            self.notebook.tab(self.tab_error_details, text=f"Ошибки: подробно ({len(errors)}) ⚠")
            self.notebook.select(self.tab_errors)
        elif added:
            self.notebook.tab(self.tab_errors, text=f"Добавлено ({len(added)})")
            self.notebook.tab(self.tab_error_details, text=f"Добавлено ({len(added)})")
            self.notebook.select(self.tab_errors)
        else:
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой (OK)")
            self.notebook.tab(self.tab_error_details, text="Ошибки: подробно")
            self.notebook.select(self.tab_main)

    def _generate_error_report(self, errors=None, added=None):
        if not hasattr(self, 'error_details_text'): return
        
        if errors is None: errors = getattr(self, 'last_errors', [])
        if added is None: added = getattr(self, 'last_added', [])
        
        self.error_details_text.configure(state="normal")
        self.error_details_text.delete("1.0", tk.END)
        
        if not errors and not added:
            self.error_details_text.insert(tk.END, "✅ РАСХОЖДЕНИЙ НЕ НАЙДЕНО\n\n")
            self.error_details_text.insert(tk.END, "Все мероприятия в Конструкторе полностью совпадают с выбранным решением Думы.\n")
            self.error_details_text.insert(tk.END, "Если вы хотите внести изменения, создайте новую редакцию постановления.")
        else:
            self.error_details_text.insert(tk.END, f"ВНИМАНИЕ! Найдено проблем: {len(errors) + len(added)}\n")
            self.error_details_text.insert(tk.END, "=" * 60 + "\n\n")
            
            for i, e in enumerate(errors, start=1):
                self.error_details_text.insert(tk.END, f"❌ ПРОБЛЕМА №{i}: {e.get('type', 'Ошибка').upper()}\n")
                self.error_details_text.insert(tk.END, f"Мероприятие: {e.get('name', '—')}\n")
                self.error_details_text.insert(tk.END, f"Сейчас в Конструкторе: {e.get('current', '—')}\n")
                self.error_details_text.insert(tk.END, f"По данным Думы: {e.get('expected', '—')}\n")
                self.error_details_text.insert(tk.END, f"Источник в Думе: {e.get('duma_source', '—')}\n")
                self.error_details_text.insert(tk.END, f"Редакция Конструктора: {e.get('postanovlenie', '—')}\n")
                
                if e.get('type') == "Неверная сумма":
                    self.error_details_text.insert(tk.END, "\nПОЧЕМУ: Сумма в Конструкторе не совпадает с официальной цифрой из решения Думы.\n")
                    self.error_details_text.insert(tk.END, "КАК ИСПРАВИТЬ: Перейдите на вкладку «Мероприятия», дважды кликните по колонке «Станет» для этого мероприятия и введите правильную сумму.\n")
                elif e.get('type') == "Нет в Думе (лишнее)":
                    self.error_details_text.insert(tk.END, "\nПОЧЕМУ: Этого мероприятия нет в официальном решении Думы. Возможно, оно было отменено или его ошибочно добавили вручную.\n")
                    self.error_details_text.insert(tk.END, "КАК ИСПРАВИТЬ: Нажмите правой кнопкой мыши на это мероприятие в таблице и выберите «🗑 Удалить / Утратило силу» (оно обнулится в текущей редакции).\n")
                self.error_details_text.insert(tk.END, "-" * 60 + "\n\n")
                
            for a in added:
                self.error_details_text.insert(tk.END, f"✅ ДОБАВЛЕНО ИЗ ДУМЫ: {a.get('name', '—')}\n")
                self.error_details_text.insert(tk.END, f"Сумма: {a.get('amount', '—')}\n")
                self.error_details_text.insert(tk.END, "ПОЧЕМУ: Этого мероприятия не хватало в Конструкторе, но оно есть в решении Думы.\n")
                self.error_details_text.insert(tk.END, "КАК ИСПРАВИТЬ: Ничего делать не нужно, программа уже добавила его в текущую редакцию.\n")
                self.error_details_text.insert(tk.END, "-" * 60 + "\n\n")
                
        self.error_details_text.configure(state="disabled")
        self.error_details_text.see(tk.END)

    def _on_duma_decision_change(self, event):
        sel = self.decision_cb.get()
        self.logger.info(f"Выбрано решение Думы для сравнения: «{sel}»")
        self._compare_with_selected_duma()

    def _update_errors_button(self):
        if hasattr(self, 'unresolved_districts') and self.unresolved_districts: self.btn_errors.configure(state="normal")
        else: self.btn_errors.configure(state="disabled")

    def _show_errors_dialog(self):
        if hasattr(self, 'unresolved_districts') and self.unresolved_districts: self._ask_for_missing_districts()
        else: messagebox.showinfo("Ошибки парсинга", "Все округа успешно определены.")

    def _ask_for_missing_districts(self):
        if not hasattr(self, 'unresolved_districts') or not self.unresolved_districts: return
        if hasattr(self, '_error_win') and self._error_win.winfo_exists(): self._error_win.lift(); return
        self._error_win = tk.Toplevel(self.root); self._error_win.title("Ошибка парсинга: не указан округ"); self._error_win.geometry("850x450"); self._error_win.transient(self.root)
        ttk.Label(self._error_win, text="В решениях Думы не удалось определить округ для следующих мероприятий.\nПожалуйста, укажите его (программа запомнит ваш выбор):", font=("TkDefaultFont", 10, "bold"), padding=10).pack()
        canvas = tk.Canvas(self._error_win); scrollbar = ttk.Scrollbar(self._error_win, orient="vertical", command=canvas.yview); scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))); canvas.create_window((0, 0), window=scrollable_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5); scrollbar.pack(side="right", fill="y")
        vars = {}; row = 0; fixes_file = Path("district_fixes.json"); fixes = {}
        if fixes_file.exists():
            try: fixes = json.loads(fixes_file.read_text(encoding="utf-8"))
            except Exception: pass
        for works, data in self.unresolved_districts.items():
            sources_str = ", ".join(data["sources"]); lbl_text = f"{works}\n(Встречается в: {sources_str})"
            ttk.Label(scrollable_frame, text=lbl_text, wraplength=500, justify="left").grid(row=row, column=0, sticky="w", pady=5, padx=5)
            var = tk.StringVar()
            if works in fixes: gid = fixes[works]; val = next((g[1] for g in GROUPS if g[0] == gid), ""); var.set(val)
            choices = [g[1] for g in GROUPS] + ["Без округа"]; cb = ttk.Combobox(scrollable_frame, textvariable=var, state="readonly", values=choices, width=40)
            cb.grid(row=row, column=1, sticky="w", padx=10, pady=5); vars[works] = var; row += 1
        def save():
            for works, var in vars.items():
                val = var.get()
                if not val: messagebox.showwarning("Ошибка", f"Пожалуйста, укажите округ для:\n{works}", parent=self._error_win); return
                if val == "Без округа": gid = "0"
                else: gid = next((g[0] for g in GROUPS if g[1] == val), "")
                if gid is not None: fixes[works] = gid
                if works in self.unresolved_districts: del self.unresolved_districts[works]
            fixes_file.write_text(json.dumps(fixes, ensure_ascii=False, indent=2), encoding="utf-8"); self._update_errors_button(); self._error_win.destroy(); self._sync_from_duma(silent=True)
        ttk.Button(self._error_win, text="💾 Сохранить и продолжить", command=save).pack(pady=10)

    def _populate_nakazy_tab(self, timeline):
        try:
            if not timeline: return
            master_decisions = []
            try:
                data = json.loads(Path("changes.json").read_text(encoding="utf-8"))
                base = timeline[0]; master_decisions.append({"date": base["date"], "number": base["number"], "is_base": True})
                for ch in data.get("changes", []): master_decisions.append({"date": ch["date"], "number": ch["number"], "is_base": False})
                for step in timeline[1:]:
                    if not any(m["date"] == step["date"] and m["number"] == step["number"] for m in master_decisions): master_decisions.append({"date": step["date"], "number": step["number"], "is_base": False})
                def parse_date(d_str):
                    try: return datetime.strptime(d_str, "%d.%m.%Y")
                    except: return datetime.min
                master_decisions.sort(key=lambda x: parse_date(x["date"]))
            except Exception as e: self.logger.error(f"Ошибка чтения changes.json: {e}"); return
            all_events = set()
            for step in timeline:
                for item in step.get("items", []):
                    if item.get("status") == "ok":
                        dist = item.get("district", "").strip()
                        if not dist: dist = "Без округа"
                        all_events.add((dist, item.get("works", "").strip()))
            def sort_key(x):
                dist = x[0]
                if dist.isdigit(): return (int(dist), x[1])
                return (999, x[1])
            sorted_events = sorted(all_events, key=sort_key)
            headers = ["Округ", "Мероприятие"] + [f"{m['date']} N {m['number']}" for m in master_decisions]
            self.nakazy_tree.headers(headers)
            self.nakazy_tree.column_width(0, width=100); self.nakazy_tree.column_width(1, width=300)
            for i in range(2, len(headers)): self.nakazy_tree.column_width(i, width=110)
            timeline_steps = {(s["date"], s["number"]): s for s in timeline}
            final_rows = []; current_district = None
            for event in sorted_events:
                dist, name = event
                if dist != current_district:
                    current_district = dist
                    group_name = f"Округ {dist}" if dist and dist != "0" else "Без округа"
                    final_rows.append([group_name, "", ""] + [""] * len(master_decisions))
                row_values = [dist, name]; current_amount = None; is_removed = False
                for m_dec in master_decisions:
                    step = timeline_steps.get((m_dec["date"], m_dec["number"]))
                    if m_dec["is_base"]:
                        item_in_step = next((it for it in step.get("items", []) if it.get("district","").strip() == dist and it.get("works","").strip() == name and it.get("status") == "ok"), None) if step else None
                        if item_in_step: current_amount = float(item_in_step.get("amount") or 0); row_values.append(fmt(current_amount))
                        else: row_values.append("—")
                        continue
                    if not step:
                        if is_removed: row_values.append("убрано ранее")
                        elif current_amount is None: row_values.append("—")
                        else: row_values.append("не меняется")
                        continue
                    diff = step.get("diff", {})
                    removed = any(rem.get("district","").strip() == dist and rem.get("works","").strip() == name for rem in diff.get("removed", []))
                    if removed: row_values.append(f"убрано от {step['date']}"); is_removed = True; current_amount = None; continue
                    added = next((it for it in diff.get("added", []) if it.get("district","").strip() == dist and it.get("works","").strip() == name), None)
                    if added: current_amount = float(added.get("amount") or 0); row_values.append(fmt(current_amount)); is_removed = False; continue
                    changed = next((c for c in diff.get("changed", []) if c["after"].get("district","").strip() == dist and c["after"].get("works","").strip() == name), None)
                    if changed: current_amount = float(changed["after"].get("amount") or 0); row_values.append(fmt(current_amount)); continue
                    if is_removed: row_values.append("убрано ранее")
                    elif current_amount is None: row_values.append("—")
                    else: row_values.append("не меняется")
                import textwrap
                wrapped_name = "\n".join([name])
                display_values = [dist, wrapped_name] + row_values[2:]
                final_rows.append(display_values)
            self.nakazy_tree.set_sheet_data(final_rows)
            for i, row in enumerate(final_rows):
                if row[1] == "": self.nakazy_tree.highlight_cells(row=i, bg="#eef2f7", fg="#000")
        except Exception as e:
            self.logger.error(f"Ошибка в _populate_nakazy_tab: {e}\n{traceback.format_exc()}")

    def _populate_history_tab(self, timeline):
        rows = []
        for step in timeline:
            d, n = step.get("date", ""), step.get("number", "")
            if step["kind"] == "base":
                base_items = step.get("items", [])
                groups = {}
                for item in base_items:
                    if item.get("status") != "ok": continue
                    dist = item.get("district", "").strip()
                    if not dist: dist = "Без округа"
                    groups.setdefault(dist, []).append(item)
                for dist in sorted(groups.keys()):
                    rows.append([d, n, "БАЗА", f"Округ {dist}", "", ""])
                    for item in groups[dist]: rows.append([d, n, "", dist, item.get("works", ""), fmt(item.get("amount", 0))])
                continue
            diff = step.get("diff", {}); changes_by_dist = {}
            for item in diff.get("added", []):
                dist = item.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("ДОБАВЛЕНО", item, item.get("amount", 0)))
            for item in diff.get("removed", []):
                dist = item.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("УДАЛЕНО", item, item.get("amount", 0)))
            for c in diff.get("changed", []):
                b, a = c["before"], c["after"]; dist = a.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("ИЗМЕНЕНО", a, (b.get("amount", 0), a.get("amount", 0))))
            if not changes_by_dist: continue
            for dist in sorted(changes_by_dist.keys()):
                rows.append([d, n, "", f"Округ {dist}", "", ""])
                for action, item, val in changes_by_dist[dist]:
                    amount_str = f"{fmt(val[0])} → {fmt(val[1])}" if action == "ИЗМЕНЕНО" else fmt(val)
                    rows.append([d, n, action, dist, item.get("works", ""), amount_str])
        self.post_tree.set_sheet_data(rows)
        for i, row in enumerate(rows):
            if row[3].startswith("Округ") or row[3] == "Без округа":
                if not row[2] and not row[4] and not row[5]: self.post_tree.highlight_cells(row=i, bg="#eef2f7", fg="#000")

    def _compare_with_selected_duma(self):
        sel_idx = self.decision_cb.current()
        if sel_idx < 0 or not hasattr(self, 'all_duma_files') or sel_idx >= len(self.all_duma_files): return
        sel_file = self.all_duma_files[sel_idx]; changes_path = Path("changes.json")
        if not changes_path.exists(): return
        data = json.loads(changes_path.read_text(encoding="utf-8")); timeline = data.get("timeline", [])
        selected_step = next((s for s in timeline if s.get("date") == sel_file["date"] and s.get("number") == sel_file["number"]), None)
        if not selected_step:
            self.err_tree.set_sheet_data([["Нет данных", f"В выбранном решении Думы от {sel_file['date']} № {sel_file['number']} не содержится информация по разделу ТОС (Наказы)", "—", "—", "—", "—"]])
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой"); return
        target_items = selected_step.get("items", []); duma_map = {}
        group_mapping = {"10": "1", "12": "2", "20": "3", "27": "4", "31": "5", "33": "6", "МИО Галушко В.Ф.": "7"}
        for item in target_items:
            if item.get("status") != "ok": continue
            dist = item.get("district", "").strip(); g = group_mapping.get(dist)
            if not g: continue
            name = item.get("works", "").strip(); amount = float(item.get("amount") or 0)
            duma_map[(g, name)] = (amount, item.get("institution", ""))
        error_details = []; found_keys = set(); postanovlenie = self.data["editions"][self.selected_edition]["label"]
        app3_events = [e for e in get_effective_events(self.data, self.selected_edition) if e.get("source") == "app3"]
        if len(duma_map) < len(app3_events) * 0.5:
            self.err_tree.set_sheet_data([["Неполные данные", f"В выбранном решении Думы от {sel_file['date']} № {sel_file['number']} не содержится полная информация по разделу ТОС. Найдено {len(duma_map)} мероприятий из {len(app3_events)}. Сравнение невозможно.", "—", "—", "—", "—"]])
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой"); self.notebook.select(self.tab_errors); return
        def get_duma_source(g, name):
            for step in reversed(timeline):
                if step["kind"] == "amendment":
                    diff = step.get("diff", {})
                    for lst in (diff.get("added", []), diff.get("changed", [])):
                        for it in lst:
                            if group_mapping.get(it.get("district", "").strip()) == g and it.get("works", "").strip() == name: return f"от {step['date']} № {step['number']}"
            base = timeline[0]; return f"от {base['date']} № {base['number']} (база)"
        for ev in app3_events:
            g = ev.get("group"); m = re.search(r'«(.*)»', ev["name"]); name = m.group(1) if m else ev["name"]; key = (g, name)
            if key in duma_map:
                found_keys.add(key); expected = duma_map[key][0]; current = get_event_value_at(ev, 2026, self.data, self.selected_edition)
                if abs(current - expected) > 0.01:
                    error_details.append({"id": ev["id"], "name": ev["name"], "type": "Неверная сумма", "current": fmt(current), "expected": fmt(expected), "duma_source": get_duma_source(g, name), "postanovlenie": postanovlenie})
            else:
                error_details.append({"id": ev["id"], "name": ev["name"], "type": "Нет в Думе (лишнее)", "current": fmt(get_event_value_at(ev, 2026, self.data, self.selected_edition)), "expected": "—", "duma_source": get_duma_source(g, name), "postanovlenie": postanovlenie})
        added_details = []; is_latest = (selected_step == timeline[-1])
        if is_latest:
            for (g, name), (amount, inst) in duma_map.items():
                if (g, name) not in found_keys:
                    existing_nums = [int(re.search(r'п\.\s*\d+\.(\d+)', e["name"]).group(1)) for e in app3_events if e.get("group")==g and re.search(r'п\.\s*\d+\.(\d+)', e["name"])]
                    next_num = max(existing_nums) + 1 if existing_nums else 1; new_id = f"duma_{g}_{next_num}"
                    ed = self.data["editions"][self.selected_edition]
                    existing = any(e.get("name") == f"п. {g}.{next_num} «{name}»" for e in ed.get("added", []))
                    if not existing:
                        ed.setdefault("added", []).append({"id": new_id, "source": "app3", "parent": "e_1_1_3", "group": g, "name": f"п. {g}.{next_num} «{name}»", "old_value": amount, "years": {"2026": amount, "2027": 0.0, "2028": 0.0}, "executor": inst, "is_custom": True})
                        added_details.append({"name": f"п. {g}.{next_num} «{name}»", "amount": fmt(amount)})
        self.data["duma_errors"] = [e["id"] for e in error_details]
        self._save_data(explicit=True); self.refresh_table(); self.refresh_totals(); self._update_duma_errors_tab(error_details, added_details)

    def _update_duma_errors_tab(self, errors, added):
        self.last_errors = errors
        self.last_added = added
        
        # 1. Таблица
        data = []
        for e in errors: data.append([e["type"], e["name"], e["current"], e["expected"], e.get("duma_source", "—"), e.get("postanovlenie", "—")])
        for a in added: data.append(["Добавлено из Думы", a["name"], "—", a["amount"], "—", "—"])
        if not errors and not added: data.append(["Успех", "Расхождений с Думой не найдено.", "—", "—", "—", "—"])
        
        self.err_tree.set_sheet_data(data)
        
        import textwrap
        heights = []
        for row in data:
            text = str(row[1]) if len(row) > 1 else ""; lines = [text]
            heights.append(max(25, len(lines) * 18 + 5))
        if heights: self.err_tree.set_row_heights(heights)

        # 2. Генерируем текст
        self._display_error_report()

        # 3. Переключение вкладок
        if errors:
            self.notebook.tab(self.tab_errors, text=f"Расхождения ({len(errors)}) ⚠")
            self.notebook.tab(self.tab_error_details, text=f"Ошибки: подробно ({len(errors)}) ⚠")
            self.notebook.select(self.tab_errors)
        elif added:
            self.notebook.tab(self.tab_errors, text=f"Добавлено ({len(added)})")
            self.notebook.tab(self.tab_error_details, text=f"Добавлено ({len(added)})")
            self.notebook.select(self.tab_errors)
        else:
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой (OK)")
            self.notebook.tab(self.tab_error_details, text="Ошибки: подробно")
            self.notebook.select(self.tab_main)

    def _generate_error_report(self):
        if not hasattr(self, 'error_details_text'): return
        
        self.error_details_text.configure(state="normal")
        self.error_details_text.delete("1.0", tk.END)
        
        errors = getattr(self, 'last_errors', [])
        added = getattr(self, 'last_added', [])
        
        if not errors and not added:
            self.error_details_text.insert(tk.END, "✅ РАСХОЖДЕНИЙ НЕ НАЙДЕНО\n\n")
            self.error_details_text.insert(tk.END, "Все мероприятия в Конструкторе полностью совпадают с выбранным решением Думы.\n")
            self.error_details_text.insert(tk.END, "Если вы хотите внести изменения, создайте новую редакцию постановления.")
        else:
            self.error_details_text.insert(tk.END, f"ВНИМАНИЕ! Найдено проблем: {len(errors) + len(added)}\n")
            self.error_details_text.insert(tk.END, "=" * 60 + "\n\n")
            
            for i, e in enumerate(errors, start=1):
                self.error_details_text.insert(tk.END, f"❌ ПРОБЛЕМА №{i}: {e.get('type', 'Ошибка').upper()}\n")
                self.error_details_text.insert(tk.END, f"Мероприятие: {e.get('name', '—')}\n")
                self.error_details_text.insert(tk.END, f"Сейчас в Конструкторе: {e.get('current', '—')}\n")
                self.error_details_text.insert(tk.END, f"По данным Думы: {e.get('expected', '—')}\n")
                self.error_details_text.insert(tk.END, f"Источник в Думе: {e.get('duma_source', '—')}\n")
                self.error_details_text.insert(tk.END, f"Редакция Конструктора: {e.get('postanovlenie', '—')}\n")
                
                if e.get('type') == "Неверная сумма":
                    self.error_details_text.insert(tk.END, "\nПОЧЕМУ: Сумма в Конструкторе не совпадает с официальной цифрой из решения Думы.\n")
                    self.error_details_text.insert(tk.END, "КАК ИСПРАВИТЬ: Перейдите на вкладку «Мероприятия», дважды кликните по колонке «Станет» для этого мероприятия и введите правильную сумму.\n")
                elif e.get('type') == "Нет в Думе (лишнее)":
                    self.error_details_text.insert(tk.END, "\nПОЧЕМУ: Этого мероприятия нет в официальном решении Думы. Возможно, оно было отменено или его ошибочно добавили вручную.\n")
                    self.error_details_text.insert(tk.END, "КАК ИСПРАВИТЬ: Нажмите правой кнопкой мыши на это мероприятие в таблице и выберите «🗑 Удалить / Утратило силу» (оно обнулится в текущей редакции).\n")
                self.error_details_text.insert(tk.END, "-" * 60 + "\n\n")
                
            for a in added:
                self.error_details_text.insert(tk.END, f"✅ ДОБАВЛЕНО ИЗ ДУМЫ: {a.get('name', '—')}\n")
                self.error_details_text.insert(tk.END, f"Сумма: {a.get('amount', '—')}\n")
                self.error_details_text.insert(tk.END, "ПОЧЕМУ: Этого мероприятия не хватало в Конструкторе, но оно есть в решении Думы.\n")
                self.error_details_text.insert(tk.END, "КАК ИСПРАВИТЬ: Ничего делать не нужно, программа уже добавила его в текущую редакцию.\n")
                self.error_details_text.insert(tk.END, "-" * 60 + "\n\n")
                
        self.error_details_text.configure(state="disabled")
        self.error_details_text.see(tk.END)

    def _on_duma_decision_change(self, event):
        sel = self.decision_cb.get()
        self.logger.info(f"Выбрано решение Думы для сравнения: «{sel}»")
        self._compare_with_selected_duma()

    def _update_errors_button(self):
        if hasattr(self, 'unresolved_districts') and self.unresolved_districts: self.btn_errors.configure(state="normal")
        else: self.btn_errors.configure(state="disabled")

    def _show_errors_dialog(self):
        if hasattr(self, 'unresolved_districts') and self.unresolved_districts: self._ask_for_missing_districts()
        else: messagebox.showinfo("Ошибки парсинга", "Все округа успешно определены.")

    def _ask_for_missing_districts(self):
        if not hasattr(self, 'unresolved_districts') or not self.unresolved_districts: return
        if hasattr(self, '_error_win') and self._error_win.winfo_exists(): self._error_win.lift(); return
        self._error_win = tk.Toplevel(self.root); self._error_win.title("Ошибка парсинга: не указан округ"); self._error_win.geometry("850x450"); self._error_win.transient(self.root)
        ttk.Label(self._error_win, text="В решениях Думы не удалось определить округ для следующих мероприятий.\nПожалуйста, укажите его (программа запомнит ваш выбор):", font=("TkDefaultFont", 10, "bold"), padding=10).pack()
        canvas = tk.Canvas(self._error_win); scrollbar = ttk.Scrollbar(self._error_win, orient="vertical", command=canvas.yview); scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))); canvas.create_window((0, 0), window=scrollable_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5); scrollbar.pack(side="right", fill="y")
        vars = {}; row = 0; fixes_file = Path("district_fixes.json"); fixes = {}
        if fixes_file.exists():
            try: fixes = json.loads(fixes_file.read_text(encoding="utf-8"))
            except Exception: pass
        for works, data in self.unresolved_districts.items():
            sources_str = ", ".join(data["sources"]); lbl_text = f"{works}\n(Встречается в: {sources_str})"
            ttk.Label(scrollable_frame, text=lbl_text, wraplength=500, justify="left").grid(row=row, column=0, sticky="w", pady=5, padx=5)
            var = tk.StringVar()
            if works in fixes: gid = fixes[works]; val = next((g[1] for g in GROUPS if g[0] == gid), ""); var.set(val)
            choices = [g[1] for g in GROUPS] + ["Без округа"]; cb = ttk.Combobox(scrollable_frame, textvariable=var, state="readonly", values=choices, width=40)
            cb.grid(row=row, column=1, sticky="w", padx=10, pady=5); vars[works] = var; row += 1
        def save():
            for works, var in vars.items():
                val = var.get()
                if not val: messagebox.showwarning("Ошибка", f"Пожалуйста, укажите округ для:\n{works}", parent=self._error_win); return
                if val == "Без округа": gid = "0"
                else: gid = next((g[0] for g in GROUPS if g[1] == val), "")
                if gid is not None: fixes[works] = gid
                if works in self.unresolved_districts: del self.unresolved_districts[works]
            fixes_file.write_text(json.dumps(fixes, ensure_ascii=False, indent=2), encoding="utf-8"); self._update_errors_button(); self._error_win.destroy(); self._sync_from_duma(silent=True)
        ttk.Button(self._error_win, text="💾 Сохранить и продолжить", command=save).pack(pady=10)

    def _populate_nakazy_tab(self, timeline):
        try:
            if not timeline: return
            master_decisions = []
            try:
                data = json.loads(Path("changes.json").read_text(encoding="utf-8"))
                base = timeline[0]; master_decisions.append({"date": base["date"], "number": base["number"], "is_base": True})
                for ch in data.get("changes", []): master_decisions.append({"date": ch["date"], "number": ch["number"], "is_base": False})
                for step in timeline[1:]:
                    if not any(m["date"] == step["date"] and m["number"] == step["number"] for m in master_decisions): master_decisions.append({"date": step["date"], "number": step["number"], "is_base": False})
                def parse_date(d_str):
                    try: return datetime.strptime(d_str, "%d.%m.%Y")
                    except: return datetime.min
                master_decisions.sort(key=lambda x: parse_date(x["date"]))
            except Exception as e: self.logger.error(f"Ошибка чтения changes.json: {e}"); return
            all_events = set()
            for step in timeline:
                for item in step.get("items", []):
                    if item.get("status") == "ok":
                        dist = item.get("district", "").strip()
                        if not dist: dist = "Без округа"
                        all_events.add((dist, item.get("works", "").strip()))
            def sort_key(x):
                dist = x[0]
                if dist.isdigit(): return (int(dist), x[1])
                return (999, x[1])
            sorted_events = sorted(all_events, key=sort_key)
            headers = ["Округ", "Мероприятие"] + [f"{m['date']} N {m['number']}" for m in master_decisions]
            self.nakazy_tree.headers(headers)
            self.nakazy_tree.column_width(0, width=100); self.nakazy_tree.column_width(1, width=300)
            for i in range(2, len(headers)): self.nakazy_tree.column_width(i, width=110)
            timeline_steps = {(s["date"], s["number"]): s for s in timeline}
            final_rows = []; current_district = None
            for event in sorted_events:
                dist, name = event
                if dist != current_district:
                    current_district = dist
                    group_name = f"Округ {dist}" if dist and dist != "0" else "Без округа"
                    final_rows.append([group_name, "", ""] + [""] * len(master_decisions))
                row_values = [dist, name]; current_amount = None; is_removed = False
                for m_dec in master_decisions:
                    step = timeline_steps.get((m_dec["date"], m_dec["number"]))
                    if m_dec["is_base"]:
                        item_in_step = next((it for it in step.get("items", []) if it.get("district","").strip() == dist and it.get("works","").strip() == name and it.get("status") == "ok"), None) if step else None
                        if item_in_step: current_amount = float(item_in_step.get("amount") or 0); row_values.append(fmt(current_amount))
                        else: row_values.append("—")
                        continue
                    if not step:
                        if is_removed: row_values.append("убрано ранее")
                        elif current_amount is None: row_values.append("—")
                        else: row_values.append("не меняется")
                        continue
                    diff = step.get("diff", {})
                    removed = any(rem.get("district","").strip() == dist and rem.get("works","").strip() == name for rem in diff.get("removed", []))
                    if removed: row_values.append(f"убрано от {step['date']}"); is_removed = True; current_amount = None; continue
                    added = next((it for it in diff.get("added", []) if it.get("district","").strip() == dist and it.get("works","").strip() == name), None)
                    if added: current_amount = float(added.get("amount") or 0); row_values.append(fmt(current_amount)); is_removed = False; continue
                    changed = next((c for c in diff.get("changed", []) if c["after"].get("district","").strip() == dist and c["after"].get("works","").strip() == name), None)
                    if changed: current_amount = float(changed["after"].get("amount") or 0); row_values.append(fmt(current_amount)); continue
                    if is_removed: row_values.append("убрано ранее")
                    elif current_amount is None: row_values.append("—")
                    else: row_values.append("не меняется")
                import textwrap
                wrapped_name = "\n".join([name])
                display_values = [dist, wrapped_name] + row_values[2:]
                final_rows.append(display_values)
            self.nakazy_tree.set_sheet_data(final_rows)
            for i, row in enumerate(final_rows):
                if row[1] == "": self.nakazy_tree.highlight_cells(row=i, bg="#eef2f7", fg="#000")
        except Exception as e:
            self.logger.error(f"Ошибка в _populate_nakazy_tab: {e}\n{traceback.format_exc()}")

    def _populate_history_tab(self, timeline):
        rows = []
        for step in timeline:
            d, n = step.get("date", ""), step.get("number", "")
            if step["kind"] == "base":
                base_items = step.get("items", [])
                groups = {}
                for item in base_items:
                    if item.get("status") != "ok": continue
                    dist = item.get("district", "").strip()
                    if not dist: dist = "Без округа"
                    groups.setdefault(dist, []).append(item)
                for dist in sorted(groups.keys()):
                    rows.append([d, n, "БАЗА", f"Округ {dist}", "", ""])
                    for item in groups[dist]: rows.append([d, n, "", dist, item.get("works", ""), fmt(item.get("amount", 0))])
                continue
            diff = step.get("diff", {}); changes_by_dist = {}
            for item in diff.get("added", []):
                dist = item.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("ДОБАВЛЕНО", item, item.get("amount", 0)))
            for item in diff.get("removed", []):
                dist = item.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("УДАЛЕНО", item, item.get("amount", 0)))
            for c in diff.get("changed", []):
                b, a = c["before"], c["after"]; dist = a.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("ИЗМЕНЕНО", a, (b.get("amount", 0), a.get("amount", 0))))
            if not changes_by_dist: continue
            for dist in sorted(changes_by_dist.keys()):
                rows.append([d, n, "", f"Округ {dist}", "", ""])
                for action, item, val in changes_by_dist[dist]:
                    amount_str = f"{fmt(val[0])} → {fmt(val[1])}" if action == "ИЗМЕНЕНО" else fmt(val)
                    rows.append([d, n, action, dist, item.get("works", ""), amount_str])
        self.post_tree.set_sheet_data(rows)
        for i, row in enumerate(rows):
            if row[3].startswith("Округ") or row[3] == "Без округа":
                if not row[2] and not row[4] and not row[5]: self.post_tree.highlight_cells(row=i, bg="#eef2f7", fg="#000")

    def _compare_with_selected_duma(self):
        sel_idx = self.decision_cb.current()
        if sel_idx < 0 or not hasattr(self, 'all_duma_files') or sel_idx >= len(self.all_duma_files): return
        sel_file = self.all_duma_files[sel_idx]; changes_path = Path("changes.json")
        if not changes_path.exists(): return
        data = json.loads(changes_path.read_text(encoding="utf-8")); timeline = data.get("timeline", [])
        selected_step = next((s for s in timeline if s.get("date") == sel_file["date"] and s.get("number") == sel_file["number"]), None)
        if not selected_step:
            self.err_tree.set_sheet_data([["Нет данных", f"В выбранном решении Думы от {sel_file['date']} № {sel_file['number']} не содержится информация по разделу ТОС (Наказы)", "—", "—", "—", "—"]])
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой"); return
        target_items = selected_step.get("items", []); duma_map = {}
        group_mapping = {"10": "1", "12": "2", "20": "3", "27": "4", "31": "5", "33": "6", "МИО Галушко В.Ф.": "7"}
        for item in target_items:
            if item.get("status") != "ok": continue
            dist = item.get("district", "").strip(); g = group_mapping.get(dist)
            if not g: continue
            name = item.get("works", "").strip(); amount = float(item.get("amount") or 0)
            duma_map[(g, name)] = (amount, item.get("institution", ""))
        error_details = []; found_keys = set(); postanovlenie = self.data["editions"][self.selected_edition]["label"]
        app3_events = [e for e in get_effective_events(self.data, self.selected_edition) if e.get("source") == "app3"]
        if len(duma_map) < len(app3_events) * 0.5:
            self.err_tree.set_sheet_data([["Неполные данные", f"В выбранном решении Думы от {sel_file['date']} № {sel_file['number']} не содержится полная информация по разделу ТОС. Найдено {len(duma_map)} мероприятий из {len(app3_events)}. Сравнение невозможно.", "—", "—", "—", "—"]])
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой"); self.notebook.select(self.tab_errors); return
        def get_duma_source(g, name):
            for step in reversed(timeline):
                if step["kind"] == "amendment":
                    diff = step.get("diff", {})
                    for lst in (diff.get("added", []), diff.get("changed", [])):
                        for it in lst:
                            if group_mapping.get(it.get("district", "").strip()) == g and it.get("works", "").strip() == name: return f"от {step['date']} № {step['number']}"
            base = timeline[0]; return f"от {base['date']} № {base['number']} (база)"
        for ev in app3_events:
            g = ev.get("group"); m = re.search(r'«(.*)»', ev["name"]); name = m.group(1) if m else ev["name"]; key = (g, name)
            if key in duma_map:
                found_keys.add(key); expected = duma_map[key][0]; current = get_event_value_at(ev, 2026, self.data, self.selected_edition)
                if abs(current - expected) > 0.01:
                    error_details.append({"id": ev["id"], "name": ev["name"], "type": "Неверная сумма", "current": fmt(current), "expected": fmt(expected), "duma_source": get_duma_source(g, name), "postanovlenie": postanovlenie})
            else:
                error_details.append({"id": ev["id"], "name": ev["name"], "type": "Нет в Думе (лишнее)", "current": fmt(get_event_value_at(ev, 2026, self.data, self.selected_edition)), "expected": "—", "duma_source": get_duma_source(g, name), "postanovlenie": postanovlenie})
        added_details = []; is_latest = (selected_step == timeline[-1])
        if is_latest:
            for (g, name), (amount, inst) in duma_map.items():
                if (g, name) not in found_keys:
                    existing_nums = [int(re.search(r'п\.\s*\d+\.(\d+)', e["name"]).group(1)) for e in app3_events if e.get("group")==g and re.search(r'п\.\s*\d+\.(\d+)', e["name"])]
                    next_num = max(existing_nums) + 1 if existing_nums else 1; new_id = f"duma_{g}_{next_num}"
                    ed = self.data["editions"][self.selected_edition]
                    existing = any(e.get("name") == f"п. {g}.{next_num} «{name}»" for e in ed.get("added", []))
                    if not existing:
                        ed.setdefault("added", []).append({"id": new_id, "source": "app3", "parent": "e_1_1_3", "group": g, "name": f"п. {g}.{next_num} «{name}»", "old_value": amount, "years": {"2026": amount, "2027": 0.0, "2028": 0.0}, "executor": inst, "is_custom": True})
                        added_details.append({"name": f"п. {g}.{next_num} «{name}»", "amount": fmt(amount)})
        self.data["duma_errors"] = [e["id"] for e in error_details]
        self._save_data(explicit=True); self.refresh_table(); self.refresh_totals(); self._update_duma_errors_tab(error_details, added_details)

    def _update_duma_errors_tab(self, errors, added):
        # 1. Таблица
        data = []
        for e in errors: data.append([e["type"], e["name"], e["current"], e["expected"], e.get("duma_source", "—"), e.get("postanovlenie", "—")])
        for a in added: data.append(["Добавлено из Думы", a["name"], "—", a["amount"], "—", "—"])
        if not errors and not added: data.append(["Успех", "Расхождений с Думой не найдено.", "—", "—", "—", "—"])
        
        self.err_tree.set_sheet_data(data)
        
        import textwrap
        heights = []
        for row in data:
            text = str(row[1]) if len(row) > 1 else ""; lines = [text]
            heights.append(max(25, len(lines) * 18 + 5))
        if heights: self.err_tree.set_row_heights(heights)

        # 2. Текстовый отчет (генерируем прямо здесь!)
        if hasattr(self, 'error_details_text'):
            self.error_details_text.configure(state="normal")
            self.error_details_text.delete("1.0", tk.END)
            
            if not errors and not added:
                self.error_details_text.insert(tk.END, "✅ РАСХОЖДЕНИЙ НЕ НАЙДЕНО\n\n")
                self.error_details_text.insert(tk.END, "Все мероприятия в Конструкторе полностью совпадают с выбранным решением Думы.\n\n")
                self.error_details_text.insert(tk.END, "Если вы хотите внести изменения, создайте новую редакцию постановления.")
            else:
                self.error_details_text.insert(tk.END, f"ВНИМАНИЕ! Найдено проблем: {len(errors) + len(added)}\n")
                self.error_details_text.insert(tk.END, "=" * 60 + "\n\n")
                
                for i, e in enumerate(errors, start=1):
                    self.error_details_text.insert(tk.END, f"❌ ПРОБЛЕМА №{i}: {e.get('type', 'Ошибка').upper()}\n")
                    self.error_details_text.insert(tk.END, f"Мероприятие: {e.get('name', '—')}\n")
                    self.error_details_text.insert(tk.END, f"Сейчас в Конструкторе: {e.get('current', '—')}\n")
                    self.error_details_text.insert(tk.END, f"По данным Думы: {e.get('expected', '—')}\n")
                    self.error_details_text.insert(tk.END, f"Источник в Думе: {e.get('duma_source', '—')}\n")
                    self.error_details_text.insert(tk.END, f"Редакция Конструктора: {e.get('postanovlenie', '—')}\n")
                    
                    if e.get('type') == "Неверная сумма":
                        self.error_details_text.insert(tk.END, "\nПОЧЕМУ: Сумма в Конструкторе не совпадает с официальной цифрой из решения Думы.\n")
                        self.error_details_text.insert(tk.END, "КАК ИСПРАВИТЬ: Перейдите на вкладку «Мероприятия», дважды кликните по колонке «Станет» для этого мероприятия и введите правильную сумму.\n")
                    elif e.get('type') == "Нет в Думе (лишнее)":
                        self.error_details_text.insert(tk.END, "\nПОЧЕМУ: Этого мероприятия нет в официальном решении Думы. Возможно, оно было отменено или его ошибочно добавили вручную.\n")
                        self.error_details_text.insert(tk.END, "КАК ИСПРАВИТЬ: Нажмите правой кнопкой мыши на это мероприятие в таблице и выберите «🗑 Удалить / Утратило силу» (оно обнулится в текущей редакции).\n")
                    self.error_details_text.insert(tk.END, "-" * 60 + "\n\n")
                    
                for a in added:
                    self.error_details_text.insert(tk.END, f"✅ ДОБАВЛЕНО ИЗ ДУМЫ: {a.get('name', '—')}\n")
                    self.error_details_text.insert(tk.END, f"Сумма: {a.get('amount', '—')}\n")
                    self.error_details_text.insert(tk.END, "ПОЧЕМУ: Этого мероприятия не хватало в Конструкторе, но оно есть в решении Думы.\n")
                    self.error_details_text.insert(tk.END, "КАК ИСПРАВИТЬ: Ничего делать не нужно, программа уже добавила его в текущую редакцию.\n")
                    self.error_details_text.insert(tk.END, "-" * 60 + "\n\n")
                    
            self.error_details_text.configure(state="disabled")
            self.error_details_text.see(tk.END)

        # 3. Переключение вкладок
        if errors:
            self.notebook.tab(self.tab_errors, text=f"Расхождения ({len(errors)}) ⚠")
            self.notebook.tab(self.tab_error_details, text=f"Ошибки: подробно ({len(errors)}) ⚠")
            self.notebook.select(self.tab_errors)
        elif added:
            self.notebook.tab(self.tab_errors, text=f"Добавлено ({len(added)})")
            self.notebook.tab(self.tab_error_details, text=f"Добавлено ({len(added)})")
            self.notebook.select(self.tab_errors)
        else:
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой (OK)")
            self.notebook.tab(self.tab_error_details, text="Ошибки: подробно")
            self.notebook.select(self.tab_main)

    def _on_duma_decision_change(self, event):
        sel = self.decision_cb.get()
        self.logger.info(f"Выбрано решение Думы для сравнения: «{sel}»")
        self._compare_with_selected_duma()

    def _update_errors_button(self):
        if hasattr(self, 'unresolved_districts') and self.unresolved_districts: self.btn_errors.configure(state="normal")
        else: self.btn_errors.configure(state="disabled")

    def _show_errors_dialog(self):
        if hasattr(self, 'unresolved_districts') and self.unresolved_districts: self._ask_for_missing_districts()
        else: messagebox.showinfo("Ошибки парсинга", "Все округа успешно определены.")

    def _ask_for_missing_districts(self):
        if not hasattr(self, 'unresolved_districts') or not self.unresolved_districts: return
        if hasattr(self, '_error_win') and self._error_win.winfo_exists(): self._error_win.lift(); return
        self._error_win = tk.Toplevel(self.root); self._error_win.title("Ошибка парсинга: не указан округ"); self._error_win.geometry("850x450"); self._error_win.transient(self.root)
        ttk.Label(self._error_win, text="В решениях Думы не удалось определить округ для следующих мероприятий.\nПожалуйста, укажите его (программа запомнит ваш выбор):", font=("TkDefaultFont", 10, "bold"), padding=10).pack()
        canvas = tk.Canvas(self._error_win); scrollbar = ttk.Scrollbar(self._error_win, orient="vertical", command=canvas.yview); scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))); canvas.create_window((0, 0), window=scrollable_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5); scrollbar.pack(side="right", fill="y")
        vars = {}; row = 0; fixes_file = Path("district_fixes.json"); fixes = {}
        if fixes_file.exists():
            try: fixes = json.loads(fixes_file.read_text(encoding="utf-8"))
            except Exception: pass
        for works, data in self.unresolved_districts.items():
            sources_str = ", ".join(data["sources"]); lbl_text = f"{works}\n(Встречается в: {sources_str})"
            ttk.Label(scrollable_frame, text=lbl_text, wraplength=500, justify="left").grid(row=row, column=0, sticky="w", pady=5, padx=5)
            var = tk.StringVar()
            if works in fixes: gid = fixes[works]; val = next((g[1] for g in GROUPS if g[0] == gid), ""); var.set(val)
            choices = [g[1] for g in GROUPS] + ["Без округа"]; cb = ttk.Combobox(scrollable_frame, textvariable=var, state="readonly", values=choices, width=40)
            cb.grid(row=row, column=1, sticky="w", padx=10, pady=5); vars[works] = var; row += 1
        def save():
            for works, var in vars.items():
                val = var.get()
                if not val: messagebox.showwarning("Ошибка", f"Пожалуйста, укажите округ для:\n{works}", parent=self._error_win); return
                if val == "Без округа": gid = "0"
                else: gid = next((g[0] for g in GROUPS if g[1] == val), "")
                if gid is not None: fixes[works] = gid
                if works in self.unresolved_districts: del self.unresolved_districts[works]
            fixes_file.write_text(json.dumps(fixes, ensure_ascii=False, indent=2), encoding="utf-8"); self._update_errors_button(); self._error_win.destroy(); self._sync_from_duma(silent=True)
        ttk.Button(self._error_win, text="💾 Сохранить и продолжить", command=save).pack(pady=10)

    def _populate_nakazy_tab(self, timeline):
        try:
            if not timeline: return
            master_decisions = []
            try:
                data = json.loads(Path("changes.json").read_text(encoding="utf-8"))
                base = timeline[0]; master_decisions.append({"date": base["date"], "number": base["number"], "is_base": True})
                for ch in data.get("changes", []): master_decisions.append({"date": ch["date"], "number": ch["number"], "is_base": False})
                for step in timeline[1:]:
                    if not any(m["date"] == step["date"] and m["number"] == step["number"] for m in master_decisions): master_decisions.append({"date": step["date"], "number": step["number"], "is_base": False})
                def parse_date(d_str):
                    try: return datetime.strptime(d_str, "%d.%m.%Y")
                    except: return datetime.min
                master_decisions.sort(key=lambda x: parse_date(x["date"]))
            except Exception as e: self.logger.error(f"Ошибка чтения changes.json: {e}"); return
            all_events = set()
            for step in timeline:
                for item in step.get("items", []):
                    if item.get("status") == "ok":
                        dist = item.get("district", "").strip()
                        if not dist: dist = "Без округа"
                        all_events.add((dist, item.get("works", "").strip()))
            def sort_key(x):
                dist = x[0]
                if dist.isdigit(): return (int(dist), x[1])
                return (999, x[1])
            sorted_events = sorted(all_events, key=sort_key)
            headers = ["Округ", "Мероприятие"] + [f"{m['date']} N {m['number']}" for m in master_decisions]
            self.nakazy_tree.headers(headers)
            self.nakazy_tree.column_width(0, width=100); self.nakazy_tree.column_width(1, width=300)
            for i in range(2, len(headers)): self.nakazy_tree.column_width(i, width=110)
            timeline_steps = {(s["date"], s["number"]): s for s in timeline}
            final_rows = []; current_district = None
            for event in sorted_events:
                dist, name = event
                if dist != current_district:
                    current_district = dist
                    group_name = f"Округ {dist}" if dist and dist != "0" else "Без округа"
                    final_rows.append([group_name, "", ""] + [""] * len(master_decisions))
                row_values = [dist, name]; current_amount = None; is_removed = False
                for m_dec in master_decisions:
                    step = timeline_steps.get((m_dec["date"], m_dec["number"]))
                    if m_dec["is_base"]:
                        item_in_step = next((it for it in step.get("items", []) if it.get("district","").strip() == dist and it.get("works","").strip() == name and it.get("status") == "ok"), None) if step else None
                        if item_in_step: current_amount = float(item_in_step.get("amount") or 0); row_values.append(fmt(current_amount))
                        else: row_values.append("—")
                        continue
                    if not step:
                        if is_removed: row_values.append("убрано ранее")
                        elif current_amount is None: row_values.append("—")
                        else: row_values.append("не меняется")
                        continue
                    diff = step.get("diff", {})
                    removed = any(rem.get("district","").strip() == dist and rem.get("works","").strip() == name for rem in diff.get("removed", []))
                    if removed: row_values.append(f"убрано от {step['date']}"); is_removed = True; current_amount = None; continue
                    added = next((it for it in diff.get("added", []) if it.get("district","").strip() == dist and it.get("works","").strip() == name), None)
                    if added: current_amount = float(added.get("amount") or 0); row_values.append(fmt(current_amount)); is_removed = False; continue
                    changed = next((c for c in diff.get("changed", []) if c["after"].get("district","").strip() == dist and c["after"].get("works","").strip() == name), None)
                    if changed: current_amount = float(changed["after"].get("amount") or 0); row_values.append(fmt(current_amount)); continue
                    if is_removed: row_values.append("убрано ранее")
                    elif current_amount is None: row_values.append("—")
                    else: row_values.append("не меняется")
                import textwrap
                wrapped_name = "\n".join([name])
                display_values = [dist, wrapped_name] + row_values[2:]
                final_rows.append(display_values)
            self.nakazy_tree.set_sheet_data(final_rows)
            for i, row in enumerate(final_rows):
                if row[1] == "": self.nakazy_tree.highlight_cells(row=i, bg="#eef2f7", fg="#000")
        except Exception as e:
            self.logger.error(f"Ошибка в _populate_nakazy_tab: {e}\n{traceback.format_exc()}")

    def _populate_history_tab(self, timeline):
        rows = []
        for step in timeline:
            d, n = step.get("date", ""), step.get("number", "")
            if step["kind"] == "base":
                base_items = step.get("items", [])
                groups = {}
                for item in base_items:
                    if item.get("status") != "ok": continue
                    dist = item.get("district", "").strip()
                    if not dist: dist = "Без округа"
                    groups.setdefault(dist, []).append(item)
                for dist in sorted(groups.keys()):
                    rows.append([d, n, "БАЗА", f"Округ {dist}", "", ""])
                    for item in groups[dist]: rows.append([d, n, "", dist, item.get("works", ""), fmt(item.get("amount", 0))])
                continue
            diff = step.get("diff", {}); changes_by_dist = {}
            for item in diff.get("added", []):
                dist = item.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("ДОБАВЛЕНО", item, item.get("amount", 0)))
            for item in diff.get("removed", []):
                dist = item.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("УДАЛЕНО", item, item.get("amount", 0)))
            for c in diff.get("changed", []):
                b, a = c["before"], c["after"]; dist = a.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("ИЗМЕНЕНО", a, (b.get("amount", 0), a.get("amount", 0))))
            if not changes_by_dist: continue
            for dist in sorted(changes_by_dist.keys()):
                rows.append([d, n, "", f"Округ {dist}", "", ""])
                for action, item, val in changes_by_dist[dist]:
                    amount_str = f"{fmt(val[0])} → {fmt(val[1])}" if action == "ИЗМЕНЕНО" else fmt(val)
                    rows.append([d, n, action, dist, item.get("works", ""), amount_str])
        self.post_tree.set_sheet_data(rows)
        for i, row in enumerate(rows):
            if row[3].startswith("Округ") or row[3] == "Без округа":
                if not row[2] and not row[4] and not row[5]: self.post_tree.highlight_cells(row=i, bg="#eef2f7", fg="#000")

    def _compare_with_selected_duma(self):
        sel_idx = self.decision_cb.current()
        if sel_idx < 0 or not hasattr(self, 'all_duma_files') or sel_idx >= len(self.all_duma_files): return
        sel_file = self.all_duma_files[sel_idx]; changes_path = Path("changes.json")
        if not changes_path.exists(): return
        data = json.loads(changes_path.read_text(encoding="utf-8")); timeline = data.get("timeline", [])
        selected_step = next((s for s in timeline if s.get("date") == sel_file["date"] and s.get("number") == sel_file["number"]), None)
        if not selected_step:
            self.err_tree.set_sheet_data([["Нет данных", f"В выбранном решении Думы от {sel_file['date']} № {sel_file['number']} не содержится информация по разделу ТОС (Наказы)", "—", "—", "—", "—"]])
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой"); return
        target_items = selected_step.get("items", []); duma_map = {}
        group_mapping = {"10": "1", "12": "2", "20": "3", "27": "4", "31": "5", "33": "6", "МИО Галушко В.Ф.": "7"}
        for item in target_items:
            if item.get("status") != "ok": continue
            dist = item.get("district", "").strip(); g = group_mapping.get(dist)
            if not g: continue
            name = item.get("works", "").strip(); amount = float(item.get("amount") or 0)
            duma_map[(g, name)] = (amount, item.get("institution", ""))
        error_details = []; found_keys = set(); postanovlenie = self.data["editions"][self.selected_edition]["label"]
        app3_events = [e for e in get_effective_events(self.data, self.selected_edition) if e.get("source") == "app3"]
        if len(duma_map) < len(app3_events) * 0.5:
            self.err_tree.set_sheet_data([["Неполные данные", f"В выбранном решении Думы от {sel_file['date']} № {sel_file['number']} не содержится полная информация по разделу ТОС. Найдено {len(duma_map)} мероприятий из {len(app3_events)}. Сравнение невозможно.", "—", "—", "—", "—"]])
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой"); self.notebook.select(self.tab_errors); return
        def get_duma_source(g, name):
            for step in reversed(timeline):
                if step["kind"] == "amendment":
                    diff = step.get("diff", {})
                    for lst in (diff.get("added", []), diff.get("changed", [])):
                        for it in lst:
                            if group_mapping.get(it.get("district", "").strip()) == g and it.get("works", "").strip() == name: return f"от {step['date']} № {step['number']}"
            base = timeline[0]; return f"от {base['date']} № {base['number']} (база)"
        for ev in app3_events:
            g = ev.get("group"); m = re.search(r'«(.*)»', ev["name"]); name = m.group(1) if m else ev["name"]; key = (g, name)
            if key in duma_map:
                found_keys.add(key); expected = duma_map[key][0]; current = get_event_value_at(ev, 2026, self.data, self.selected_edition)
                if abs(current - expected) > 0.01:
                    error_details.append({"id": ev["id"], "name": ev["name"], "type": "Неверная сумма", "current": fmt(current), "expected": fmt(expected), "duma_source": get_duma_source(g, name), "postanovlenie": postanovlenie})
            else:
                error_details.append({"id": ev["id"], "name": ev["name"], "type": "Нет в Думе (лишнее)", "current": fmt(get_event_value_at(ev, 2026, self.data, self.selected_edition)), "expected": "—", "duma_source": get_duma_source(g, name), "postanovlenie": postanovlenie})
        added_details = []; is_latest = (selected_step == timeline[-1])
        if is_latest:
            for (g, name), (amount, inst) in duma_map.items():
                if (g, name) not in found_keys:
                    existing_nums = [int(re.search(r'п\.\s*\d+\.(\d+)', e["name"]).group(1)) for e in app3_events if e.get("group")==g and re.search(r'п\.\s*\d+\.(\d+)', e["name"])]
                    next_num = max(existing_nums) + 1 if existing_nums else 1; new_id = f"duma_{g}_{next_num}"
                    ed = self.data["editions"][self.selected_edition]
                    existing = any(e.get("name") == f"п. {g}.{next_num} «{name}»" for e in ed.get("added", []))
                    if not existing:
                        ed.setdefault("added", []).append({"id": new_id, "source": "app3", "parent": "e_1_1_3", "group": g, "name": f"п. {g}.{next_num} «{name}»", "old_value": amount, "years": {"2026": amount, "2027": 0.0, "2028": 0.0}, "executor": inst, "is_custom": True})
                        added_details.append({"name": f"п. {g}.{next_num} «{name}»", "amount": fmt(amount)})
        self.data["duma_errors"] = [e["id"] for e in error_details]
        self._save_data(explicit=True); self.refresh_table(); self.refresh_totals(); self._update_duma_errors_tab(error_details, added_details)

    def _update_duma_errors_tab(self, errors, added):
        # 1. Таблица
        data = []
        for e in errors: data.append([e["type"], e["name"], e["current"], e["expected"], e.get("duma_source", "—"), e.get("postanovlenie", "—")])
        for a in added: data.append(["Добавлено из Думы", a["name"], "—", a["amount"], "—", "—"])
        if not errors and not added: data.append(["Успех", "Расхождений с Думой не найдено.", "—", "—", "—", "—"])
        
        self.err_tree.set_sheet_data(data)
        
        import textwrap
        heights = []
        for row in data:
            text = str(row[1]) if len(row) > 1 else ""; lines = [text]
            heights.append(max(25, len(lines) * 18 + 5))
        if heights: self.err_tree.set_row_heights(heights)

        # 2. Текстовый отчет (генерируем прямо здесь!)
        if hasattr(self, 'error_details_text'):
            self.error_details_text.configure(state="normal")
            self.error_details_text.delete("1.0", tk.END)
            
            if not errors and not added:
                self.error_details_text.insert(tk.END, "✅ РАСХОЖДЕНИЙ НЕ НАЙДЕНО\n\n")
                self.error_details_text.insert(tk.END, "Все мероприятия в Конструкторе полностью совпадают с выбранным решением Думы.\n\n")
                self.error_details_text.insert(tk.END, "Если вы хотите внести изменения, создайте новую редакцию постановления.")
            else:
                self.error_details_text.insert(tk.END, f"ВНИМАНИЕ! Найдено проблем: {len(errors) + len(added)}\n")
                self.error_details_text.insert(tk.END, "=" * 60 + "\n\n")
                
                for i, e in enumerate(errors, start=1):
                    self.error_details_text.insert(tk.END, f"❌ ПРОБЛЕМА №{i}: {e.get('type', 'Ошибка').upper()}\n")
                    self.error_details_text.insert(tk.END, f"Мероприятие: {e.get('name', '—')}\n")
                    self.error_details_text.insert(tk.END, f"Сейчас в Конструкторе: {e.get('current', '—')}\n")
                    self.error_details_text.insert(tk.END, f"По данным Думы: {e.get('expected', '—')}\n")
                    self.error_details_text.insert(tk.END, f"Источник в Думе: {e.get('duma_source', '—')}\n")
                    self.error_details_text.insert(tk.END, f"Редакция Конструктора: {e.get('postanovlenie', '—')}\n")
                    
                    if e.get('type') == "Неверная сумма":
                        self.error_details_text.insert(tk.END, "\nПОЧЕМУ: Сумма в Конструкторе не совпадает с официальной цифрой из решения Думы.\n")
                        self.error_details_text.insert(tk.END, "КАК ИСПРАВИТЬ: Перейдите на вкладку «Мероприятия», дважды кликните по колонке «Станет» для этого мероприятия и введите правильную сумму.\n")
                    elif e.get('type') == "Нет в Думе (лишнее)":
                        self.error_details_text.insert(tk.END, "\nПОЧЕМУ: Этого мероприятия нет в официальном решении Думы. Возможно, оно было отменено или его ошибочно добавили вручную.\n")
                        self.error_details_text.insert(tk.END, "КАК ИСПРАВИТЬ: Нажмите правой кнопкой мыши на это мероприятие в таблице и выберите «🗑 Удалить / Утратило силу» (оно обнулится в текущей редакции).\n")
                    self.error_details_text.insert(tk.END, "-" * 60 + "\n\n")
                    
                for a in added:
                    self.error_details_text.insert(tk.END, f"✅ ДОБАВЛЕНО ИЗ ДУМЫ: {a.get('name', '—')}\n")
                    self.error_details_text.insert(tk.END, f"Сумма: {a.get('amount', '—')}\n")
                    self.error_details_text.insert(tk.END, "ПОЧЕМУ: Этого мероприятия не хватало в Конструкторе, но оно есть в решении Думы.\n")
                    self.error_details_text.insert(tk.END, "КАК ИСПРАВИТЬ: Ничего делать не нужно, программа уже добавила его в текущую редакцию.\n")
                    self.error_details_text.insert(tk.END, "-" * 60 + "\n\n")
                    
            self.error_details_text.configure(state="disabled")
            self.error_details_text.see(tk.END)

        # 3. Переключение вкладок
        if errors:
            self.notebook.tab(self.tab_errors, text=f"Расхождения ({len(errors)}) ⚠")
            self.notebook.tab(self.tab_error_details, text=f"Ошибки: подробно ({len(errors)}) ⚠")
            self.notebook.select(self.tab_errors)
        elif added:
            self.notebook.tab(self.tab_errors, text=f"Добавлено ({len(added)})")
            self.notebook.tab(self.tab_error_details, text=f"Добавлено ({len(added)})")
            self.notebook.select(self.tab_errors)
        else:
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой (OK)")
            self.notebook.tab(self.tab_error_details, text="Ошибки: подробно")
            self.notebook.select(self.tab_main)

    def _on_duma_decision_change(self, event):
        sel = self.decision_cb.get()
        self.logger.info(f"Выбрано решение Думы для сравнения: «{sel}»")
        self._compare_with_selected_duma()

    def _update_errors_button(self):
        if hasattr(self, 'unresolved_districts') and self.unresolved_districts: self.btn_errors.configure(state="normal")
        else: self.btn_errors.configure(state="disabled")

    def _show_errors_dialog(self):
        if hasattr(self, 'unresolved_districts') and self.unresolved_districts: self._ask_for_missing_districts()
        else: messagebox.showinfo("Ошибки парсинга", "Все округа успешно определены.")

    def _ask_for_missing_districts(self):
        if not hasattr(self, 'unresolved_districts') or not self.unresolved_districts: return
        if hasattr(self, '_error_win') and self._error_win.winfo_exists(): self._error_win.lift(); return
        self._error_win = tk.Toplevel(self.root); self._error_win.title("Ошибка парсинга: не указан округ"); self._error_win.geometry("850x450"); self._error_win.transient(self.root)
        ttk.Label(self._error_win, text="В решениях Думы не удалось определить округ для следующих мероприятий.\nПожалуйста, укажите его (программа запомнит ваш выбор):", font=("TkDefaultFont", 10, "bold"), padding=10).pack()
        canvas = tk.Canvas(self._error_win); scrollbar = ttk.Scrollbar(self._error_win, orient="vertical", command=canvas.yview); scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))); canvas.create_window((0, 0), window=scrollable_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5); scrollbar.pack(side="right", fill="y")
        vars = {}; row = 0; fixes_file = Path("district_fixes.json"); fixes = {}
        if fixes_file.exists():
            try: fixes = json.loads(fixes_file.read_text(encoding="utf-8"))
            except Exception: pass
        for works, data in self.unresolved_districts.items():
            sources_str = ", ".join(data["sources"]); lbl_text = f"{works}\n(Встречается в: {sources_str})"
            ttk.Label(scrollable_frame, text=lbl_text, wraplength=500, justify="left").grid(row=row, column=0, sticky="w", pady=5, padx=5)
            var = tk.StringVar()
            if works in fixes: gid = fixes[works]; val = next((g[1] for g in GROUPS if g[0] == gid), ""); var.set(val)
            choices = [g[1] for g in GROUPS] + ["Без округа"]; cb = ttk.Combobox(scrollable_frame, textvariable=var, state="readonly", values=choices, width=40)
            cb.grid(row=row, column=1, sticky="w", padx=10, pady=5); vars[works] = var; row += 1
        def save():
            for works, var in vars.items():
                val = var.get()
                if not val: messagebox.showwarning("Ошибка", f"Пожалуйста, укажите округ для:\n{works}", parent=self._error_win); return
                if val == "Без округа": gid = "0"
                else: gid = next((g[0] for g in GROUPS if g[1] == val), "")
                if gid is not None: fixes[works] = gid
                if works in self.unresolved_districts: del self.unresolved_districts[works]
            fixes_file.write_text(json.dumps(fixes, ensure_ascii=False, indent=2), encoding="utf-8"); self._update_errors_button(); self._error_win.destroy(); self._sync_from_duma(silent=True)
        ttk.Button(self._error_win, text="💾 Сохранить и продолжить", command=save).pack(pady=10)

    def _populate_nakazy_tab(self, timeline):
        try:
            if not timeline: return
            master_decisions = []
            try:
                data = json.loads(Path("changes.json").read_text(encoding="utf-8"))
                base = timeline[0]; master_decisions.append({"date": base["date"], "number": base["number"], "is_base": True})
                for ch in data.get("changes", []): master_decisions.append({"date": ch["date"], "number": ch["number"], "is_base": False})
                for step in timeline[1:]:
                    if not any(m["date"] == step["date"] and m["number"] == step["number"] for m in master_decisions): master_decisions.append({"date": step["date"], "number": step["number"], "is_base": False})
                def parse_date(d_str):
                    try: return datetime.strptime(d_str, "%d.%m.%Y")
                    except: return datetime.min
                master_decisions.sort(key=lambda x: parse_date(x["date"]))
            except Exception as e: self.logger.error(f"Ошибка чтения changes.json: {e}"); return
            all_events = set()
            for step in timeline:
                for item in step.get("items", []):
                    if item.get("status") == "ok":
                        dist = item.get("district", "").strip()
                        if not dist: dist = "Без округа"
                        all_events.add((dist, item.get("works", "").strip()))
            def sort_key(x):
                dist = x[0]
                if dist.isdigit(): return (int(dist), x[1])
                return (999, x[1])
            sorted_events = sorted(all_events, key=sort_key)
            headers = ["Округ", "Мероприятие"] + [f"{m['date']} N {m['number']}" for m in master_decisions]
            self.nakazy_tree.headers(headers)
            self.nakazy_tree.column_width(0, width=100); self.nakazy_tree.column_width(1, width=300)
            for i in range(2, len(headers)): self.nakazy_tree.column_width(i, width=110)
            timeline_steps = {(s["date"], s["number"]): s for s in timeline}
            final_rows = []; current_district = None
            for event in sorted_events:
                dist, name = event
                if dist != current_district:
                    current_district = dist
                    group_name = f"Округ {dist}" if dist and dist != "0" else "Без округа"
                    final_rows.append([group_name, "", ""] + [""] * len(master_decisions))
                row_values = [dist, name]; current_amount = None; is_removed = False
                for m_dec in master_decisions:
                    step = timeline_steps.get((m_dec["date"], m_dec["number"]))
                    if m_dec["is_base"]:
                        item_in_step = next((it for it in step.get("items", []) if it.get("district","").strip() == dist and it.get("works","").strip() == name and it.get("status") == "ok"), None) if step else None
                        if item_in_step: current_amount = float(item_in_step.get("amount") or 0); row_values.append(fmt(current_amount))
                        else: row_values.append("—")
                        continue
                    if not step:
                        if is_removed: row_values.append("убрано ранее")
                        elif current_amount is None: row_values.append("—")
                        else: row_values.append("не меняется")
                        continue
                    diff = step.get("diff", {})
                    removed = any(rem.get("district","").strip() == dist and rem.get("works","").strip() == name for rem in diff.get("removed", []))
                    if removed: row_values.append(f"убрано от {step['date']}"); is_removed = True; current_amount = None; continue
                    added = next((it for it in diff.get("added", []) if it.get("district","").strip() == dist and it.get("works","").strip() == name), None)
                    if added: current_amount = float(added.get("amount") or 0); row_values.append(fmt(current_amount)); is_removed = False; continue
                    changed = next((c for c in diff.get("changed", []) if c["after"].get("district","").strip() == dist and c["after"].get("works","").strip() == name), None)
                    if changed: current_amount = float(changed["after"].get("amount") or 0); row_values.append(fmt(current_amount)); continue
                    if is_removed: row_values.append("убрано ранее")
                    elif current_amount is None: row_values.append("—")
                    else: row_values.append("не меняется")
                import textwrap
                wrapped_name = "\n".join([name])
                display_values = [dist, wrapped_name] + row_values[2:]
                final_rows.append(display_values)
            self.nakazy_tree.set_sheet_data(final_rows)
            for i, row in enumerate(final_rows):
                if row[1] == "": self.nakazy_tree.highlight_cells(row=i, bg="#eef2f7", fg="#000")
        except Exception as e:
            self.logger.error(f"Ошибка в _populate_nakazy_tab: {e}\n{traceback.format_exc()}")

    def _populate_history_tab(self, timeline):
        rows = []
        for step in timeline:
            d, n = step.get("date", ""), step.get("number", "")
            if step["kind"] == "base":
                base_items = step.get("items", [])
                groups = {}
                for item in base_items:
                    if item.get("status") != "ok": continue
                    dist = item.get("district", "").strip()
                    if not dist: dist = "Без округа"
                    groups.setdefault(dist, []).append(item)
                for dist in sorted(groups.keys()):
                    rows.append([d, n, "БАЗА", f"Округ {dist}", "", ""])
                    for item in groups[dist]: rows.append([d, n, "", dist, item.get("works", ""), fmt(item.get("amount", 0))])
                continue
            diff = step.get("diff", {}); changes_by_dist = {}
            for item in diff.get("added", []):
                dist = item.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("ДОБАВЛЕНО", item, item.get("amount", 0)))
            for item in diff.get("removed", []):
                dist = item.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("УДАЛЕНО", item, item.get("amount", 0)))
            for c in diff.get("changed", []):
                b, a = c["before"], c["after"]; dist = a.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("ИЗМЕНЕНО", a, (b.get("amount", 0), a.get("amount", 0))))
            if not changes_by_dist: continue
            for dist in sorted(changes_by_dist.keys()):
                rows.append([d, n, "", f"Округ {dist}", "", ""])
                for action, item, val in changes_by_dist[dist]:
                    amount_str = f"{fmt(val[0])} → {fmt(val[1])}" if action == "ИЗМЕНЕНО" else fmt(val)
                    rows.append([d, n, action, dist, item.get("works", ""), amount_str])
        self.post_tree.set_sheet_data(rows)
        for i, row in enumerate(rows):
            if row[3].startswith("Округ") or row[3] == "Без округа":
                if not row[2] and not row[4] and not row[5]: self.post_tree.highlight_cells(row=i, bg="#eef2f7", fg="#000")

    def _compare_with_selected_duma(self):
        sel_idx = self.decision_cb.current()
        if sel_idx < 0 or not hasattr(self, 'all_duma_files') or sel_idx >= len(self.all_duma_files): return
        sel_file = self.all_duma_files[sel_idx]; changes_path = Path("changes.json")
        if not changes_path.exists(): return
        data = json.loads(changes_path.read_text(encoding="utf-8")); timeline = data.get("timeline", [])
        selected_step = next((s for s in timeline if s.get("date") == sel_file["date"] and s.get("number") == sel_file["number"]), None)
        if not selected_step:
            self.err_tree.set_sheet_data([["Нет данных", f"В выбранном решении Думы от {sel_file['date']} № {sel_file['number']} не содержится информация по разделу ТОС (Наказы)", "—", "—", "—", "—"]])
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой"); return
        target_items = selected_step.get("items", []); duma_map = {}
        group_mapping = {"10": "1", "12": "2", "20": "3", "27": "4", "31": "5", "33": "6", "МИО Галушко В.Ф.": "7"}
        for item in target_items:
            if item.get("status") != "ok": continue
            dist = item.get("district", "").strip(); g = group_mapping.get(dist)
            if not g: continue
            name = item.get("works", "").strip(); amount = float(item.get("amount") or 0)
            duma_map[(g, name)] = (amount, item.get("institution", ""))
        error_details = []; found_keys = set(); postanovlenie = self.data["editions"][self.selected_edition]["label"]
        app3_events = [e for e in get_effective_events(self.data, self.selected_edition) if e.get("source") == "app3"]
        if len(duma_map) < len(app3_events) * 0.5:
            self.err_tree.set_sheet_data([["Неполные данные", f"В выбранном решении Думы от {sel_file['date']} № {sel_file['number']} не содержится полная информация по разделу ТОС. Найдено {len(duma_map)} мероприятий из {len(app3_events)}. Сравнение невозможно.", "—", "—", "—", "—"]])
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой"); self.notebook.select(self.tab_errors); return
        def get_duma_source(g, name):
            for step in reversed(timeline):
                if step["kind"] == "amendment":
                    diff = step.get("diff", {})
                    for lst in (diff.get("added", []), diff.get("changed", [])):
                        for it in lst:
                            if group_mapping.get(it.get("district", "").strip()) == g and it.get("works", "").strip() == name: return f"от {step['date']} № {step['number']}"
            base = timeline[0]; return f"от {base['date']} № {base['number']} (база)"
        for ev in app3_events:
            g = ev.get("group"); m = re.search(r'«(.*)»', ev["name"]); name = m.group(1) if m else ev["name"]; key = (g, name)
            if key in duma_map:
                found_keys.add(key); expected = duma_map[key][0]; current = get_event_value_at(ev, 2026, self.data, self.selected_edition)
                if abs(current - expected) > 0.01:
                    error_details.append({"id": ev["id"], "name": ev["name"], "type": "Неверная сумма", "current": fmt(current), "expected": fmt(expected), "duma_source": get_duma_source(g, name), "postanovlenie": postanovlenie})
            else:
                error_details.append({"id": ev["id"], "name": ev["name"], "type": "Нет в Думе (лишнее)", "current": fmt(get_event_value_at(ev, 2026, self.data, self.selected_edition)), "expected": "—", "duma_source": get_duma_source(g, name), "postanovlenie": postanovlenie})
        added_details = []; is_latest = (selected_step == timeline[-1])
        if is_latest:
            for (g, name), (amount, inst) in duma_map.items():
                if (g, name) not in found_keys:
                    existing_nums = [int(re.search(r'п\.\s*\d+\.(\d+)', e["name"]).group(1)) for e in app3_events if e.get("group")==g and re.search(r'п\.\s*\d+\.(\d+)', e["name"])]
                    next_num = max(existing_nums) + 1 if existing_nums else 1; new_id = f"duma_{g}_{next_num}"
                    ed = self.data["editions"][self.selected_edition]
                    existing = any(e.get("name") == f"п. {g}.{next_num} «{name}»" for e in ed.get("added", []))
                    if not existing:
                        ed.setdefault("added", []).append({"id": new_id, "source": "app3", "parent": "e_1_1_3", "group": g, "name": f"п. {g}.{next_num} «{name}»", "old_value": amount, "years": {"2026": amount, "2027": 0.0, "2028": 0.0}, "executor": inst, "is_custom": True})
                        added_details.append({"name": f"п. {g}.{next_num} «{name}»", "amount": fmt(amount)})
        self.data["duma_errors"] = [e["id"] for e in error_details]
        self._save_data(explicit=True); self.refresh_table(); self.refresh_totals(); self._update_duma_errors_tab(error_details, added_details)

    def _update_duma_errors_tab(self, errors, added):
        # 1. Таблица
        data = []
        for e in errors: data.append([e["type"], e["name"], e["current"], e["expected"], e.get("duma_source", "—"), e.get("postanovlenie", "—")])
        for a in added: data.append(["Добавлено из Думы", a["name"], "—", a["amount"], "—", "—"])
        if not errors and not added: data.append(["Успех", "Расхождений с Думой не найдено.", "—", "—", "—", "—"])
        
        self.err_tree.set_sheet_data(data)
        
        import textwrap
        heights = []
        for row in data:
            text = str(row[1]) if len(row) > 1 else ""; lines = [text]
            heights.append(max(25, len(lines) * 18 + 5))
        if heights: self.err_tree.set_row_heights(heights)

        # 2. Текстовый отчет (генерируем прямо здесь!)
        if hasattr(self, 'error_details_text'):
            self.error_details_text.configure(state="normal")
            self.error_details_text.delete("1.0", tk.END)
            
            if not errors and not added:
                self.error_details_text.insert(tk.END, "✅ РАСХОЖДЕНИЙ НЕ НАЙДЕНО\n\n")
                self.error_details_text.insert(tk.END, "Все мероприятия в Конструкторе полностью совпадают с выбранным решением Думы.\n\n")
                self.error_details_text.insert(tk.END, "Если вы хотите внести изменения, создайте новую редакцию постановления.")
            else:
                self.error_details_text.insert(tk.END, f"ВНИМАНИЕ! Найдено проблем: {len(errors) + len(added)}\n")
                self.error_details_text.insert(tk.END, "=" * 60 + "\n\n")
                
                for i, e in enumerate(errors, start=1):
                    self.error_details_text.insert(tk.END, f"❌ ПРОБЛЕМА №{i}: {e.get('type', 'Ошибка').upper()}\n")
                    self.error_details_text.insert(tk.END, f"Мероприятие: {e.get('name', '—')}\n")
                    self.error_details_text.insert(tk.END, f"Сейчас в Конструкторе: {e.get('current', '—')}\n")
                    self.error_details_text.insert(tk.END, f"По данным Думы: {e.get('expected', '—')}\n")
                    self.error_details_text.insert(tk.END, f"Источник в Думе: {e.get('duma_source', '—')}\n")
                    self.error_details_text.insert(tk.END, f"Редакция Конструктора: {e.get('postanovlenie', '—')}\n")
                    
                    if e.get('type') == "Неверная сумма":
                        self.error_details_text.insert(tk.END, "\nПОЧЕМУ: Сумма в Конструкторе не совпадает с официальной цифрой из решения Думы.\n")
                        self.error_details_text.insert(tk.END, "КАК ИСПРАВИТЬ: Перейдите на вкладку «Мероприятия», дважды кликните по колонке «Станет» для этого мероприятия и введите правильную сумму.\n")
                    elif e.get('type') == "Нет в Думе (лишнее)":
                        self.error_details_text.insert(tk.END, "\nПОЧЕМУ: Этого мероприятия нет в официальном решении Думы. Возможно, оно было отменено или его ошибочно добавили вручную.\n")
                        self.error_details_text.insert(tk.END, "КАК ИСПРАВИТЬ: Нажмите правой кнопкой мыши на это мероприятие в таблице и выберите «🗑 Удалить / Утратило силу» (оно обнулится в текущей редакции).\n")
                    self.error_details_text.insert(tk.END, "-" * 60 + "\n\n")
                    
                for a in added:
                    self.error_details_text.insert(tk.END, f"✅ ДОБАВЛЕНО ИЗ ДУМЫ: {a.get('name', '—')}\n")
                    self.error_details_text.insert(tk.END, f"Сумма: {a.get('amount', '—')}\n")
                    self.error_details_text.insert(tk.END, "ПОЧЕМУ: Этого мероприятия не хватало в Конструкторе, но оно есть в решении Думы.\n")
                    self.error_details_text.insert(tk.END, "КАК ИСПРАВИТЬ: Ничего делать не нужно, программа уже добавила его в текущую редакцию.\n")
                    self.error_details_text.insert(tk.END, "-" * 60 + "\n\n")
                    
            self.error_details_text.configure(state="disabled")
            self.error_details_text.see(tk.END)

        # 3. Переключение вкладок
        if errors:
            self.notebook.tab(self.tab_errors, text=f"Расхождения ({len(errors)}) ⚠")
            self.notebook.tab(self.tab_error_details, text=f"Ошибки: подробно ({len(errors)}) ⚠")
            self.notebook.select(self.tab_errors)
        elif added:
            self.notebook.tab(self.tab_errors, text=f"Добавлено ({len(added)})")
            self.notebook.tab(self.tab_error_details, text=f"Добавлено ({len(added)})")
            self.notebook.select(self.tab_errors)
        else:
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой (OK)")
            self.notebook.tab(self.tab_error_details, text="Ошибки: подробно")
            self.notebook.select(self.tab_main)

    def _on_duma_decision_change(self, event):
        sel = self.decision_cb.get()
        self.logger.info(f"Выбрано решение Думы для сравнения: «{sel}»")
        self._compare_with_selected_duma()

    def _update_errors_button(self):
        if hasattr(self, 'unresolved_districts') and self.unresolved_districts: self.btn_errors.configure(state="normal")
        else: self.btn_errors.configure(state="disabled")

    def _show_errors_dialog(self):
        if hasattr(self, 'unresolved_districts') and self.unresolved_districts: self._ask_for_missing_districts()
        else: messagebox.showinfo("Ошибки парсинга", "Все округа успешно определены.")

    def _ask_for_missing_districts(self):
        if not hasattr(self, 'unresolved_districts') or not self.unresolved_districts: return
        if hasattr(self, '_error_win') and self._error_win.winfo_exists(): self._error_win.lift(); return
        self._error_win = tk.Toplevel(self.root); self._error_win.title("Ошибка парсинга: не указан округ"); self._error_win.geometry("850x450"); self._error_win.transient(self.root)
        ttk.Label(self._error_win, text="В решениях Думы не удалось определить округ для следующих мероприятий.\nПожалуйста, укажите его (программа запомнит ваш выбор):", font=("TkDefaultFont", 10, "bold"), padding=10).pack()
        canvas = tk.Canvas(self._error_win); scrollbar = ttk.Scrollbar(self._error_win, orient="vertical", command=canvas.yview); scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))); canvas.create_window((0, 0), window=scrollable_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5); scrollbar.pack(side="right", fill="y")
        vars = {}; row = 0; fixes_file = Path("district_fixes.json"); fixes = {}
        if fixes_file.exists():
            try: fixes = json.loads(fixes_file.read_text(encoding="utf-8"))
            except Exception: pass
        for works, data in self.unresolved_districts.items():
            sources_str = ", ".join(data["sources"]); lbl_text = f"{works}\n(Встречается в: {sources_str})"
            ttk.Label(scrollable_frame, text=lbl_text, wraplength=500, justify="left").grid(row=row, column=0, sticky="w", pady=5, padx=5)
            var = tk.StringVar()
            if works in fixes: gid = fixes[works]; val = next((g[1] for g in GROUPS if g[0] == gid), ""); var.set(val)
            choices = [g[1] for g in GROUPS] + ["Без округа"]; cb = ttk.Combobox(scrollable_frame, textvariable=var, state="readonly", values=choices, width=40)
            cb.grid(row=row, column=1, sticky="w", padx=10, pady=5); vars[works] = var; row += 1
        def save():
            for works, var in vars.items():
                val = var.get()
                if not val: messagebox.showwarning("Ошибка", f"Пожалуйста, укажите округ для:\n{works}", parent=self._error_win); return
                if val == "Без округа": gid = "0"
                else: gid = next((g[0] for g in GROUPS if g[1] == val), "")
                if gid is not None: fixes[works] = gid
                if works in self.unresolved_districts: del self.unresolved_districts[works]
            fixes_file.write_text(json.dumps(fixes, ensure_ascii=False, indent=2), encoding="utf-8"); self._update_errors_button(); self._error_win.destroy(); self._sync_from_duma(silent=True)
        ttk.Button(self._error_win, text="💾 Сохранить и продолжить", command=save).pack(pady=10)

    def _populate_nakazy_tab(self, timeline):
        try:
            if not timeline: return
            master_decisions = []
            try:
                data = json.loads(Path("changes.json").read_text(encoding="utf-8"))
                base = timeline[0]; master_decisions.append({"date": base["date"], "number": base["number"], "is_base": True})
                for ch in data.get("changes", []): master_decisions.append({"date": ch["date"], "number": ch["number"], "is_base": False})
                for step in timeline[1:]:
                    if not any(m["date"] == step["date"] and m["number"] == step["number"] for m in master_decisions): master_decisions.append({"date": step["date"], "number": step["number"], "is_base": False})
                def parse_date(d_str):
                    try: return datetime.strptime(d_str, "%d.%m.%Y")
                    except: return datetime.min
                master_decisions.sort(key=lambda x: parse_date(x["date"]))
            except Exception as e: self.logger.error(f"Ошибка чтения changes.json: {e}"); return
            all_events = set()
            for step in timeline:
                for item in step.get("items", []):
                    if item.get("status") == "ok":
                        dist = item.get("district", "").strip()
                        if not dist: dist = "Без округа"
                        all_events.add((dist, item.get("works", "").strip()))
            def sort_key(x):
                dist = x[0]
                if dist.isdigit(): return (int(dist), x[1])
                return (999, x[1])
            sorted_events = sorted(all_events, key=sort_key)
            headers = ["Округ", "Мероприятие"] + [f"{m['date']} N {m['number']}" for m in master_decisions]
            self.nakazy_tree.headers(headers)
            self.nakazy_tree.column_width(0, width=100); self.nakazy_tree.column_width(1, width=300)
            for i in range(2, len(headers)): self.nakazy_tree.column_width(i, width=110)
            timeline_steps = {(s["date"], s["number"]): s for s in timeline}
            final_rows = []; current_district = None
            for event in sorted_events:
                dist, name = event
                if dist != current_district:
                    current_district = dist
                    group_name = f"Округ {dist}" if dist and dist != "0" else "Без округа"
                    final_rows.append([group_name, "", ""] + [""] * len(master_decisions))
                row_values = [dist, name]; current_amount = None; is_removed = False
                for m_dec in master_decisions:
                    step = timeline_steps.get((m_dec["date"], m_dec["number"]))
                    if m_dec["is_base"]:
                        item_in_step = next((it for it in step.get("items", []) if it.get("district","").strip() == dist and it.get("works","").strip() == name and it.get("status") == "ok"), None) if step else None
                        if item_in_step: current_amount = float(item_in_step.get("amount") or 0); row_values.append(fmt(current_amount))
                        else: row_values.append("—")
                        continue
                    if not step:
                        if is_removed: row_values.append("убрано ранее")
                        elif current_amount is None: row_values.append("—")
                        else: row_values.append("не меняется")
                        continue
                    diff = step.get("diff", {})
                    removed = any(rem.get("district","").strip() == dist and rem.get("works","").strip() == name for rem in diff.get("removed", []))
                    if removed: row_values.append(f"убрано от {step['date']}"); is_removed = True; current_amount = None; continue
                    added = next((it for it in diff.get("added", []) if it.get("district","").strip() == dist and it.get("works","").strip() == name), None)
                    if added: current_amount = float(added.get("amount") or 0); row_values.append(fmt(current_amount)); is_removed = False; continue
                    changed = next((c for c in diff.get("changed", []) if c["after"].get("district","").strip() == dist and c["after"].get("works","").strip() == name), None)
                    if changed: current_amount = float(changed["after"].get("amount") or 0); row_values.append(fmt(current_amount)); continue
                    if is_removed: row_values.append("убрано ранее")
                    elif current_amount is None: row_values.append("—")
                    else: row_values.append("не меняется")
                import textwrap
                wrapped_name = "\n".join([name])
                display_values = [dist, wrapped_name] + row_values[2:]
                final_rows.append(display_values)
            self.nakazy_tree.set_sheet_data(final_rows)
            for i, row in enumerate(final_rows):
                if row[1] == "": self.nakazy_tree.highlight_cells(row=i, bg="#eef2f7", fg="#000")
        except Exception as e:
            self.logger.error(f"Ошибка в _populate_nakazy_tab: {e}\n{traceback.format_exc()}")

    def _populate_history_tab(self, timeline):
        rows = []
        for step in timeline:
            d, n = step.get("date", ""), step.get("number", "")
            if step["kind"] == "base":
                base_items = step.get("items", [])
                groups = {}
                for item in base_items:
                    if item.get("status") != "ok": continue
                    dist = item.get("district", "").strip()
                    if not dist: dist = "Без округа"
                    groups.setdefault(dist, []).append(item)
                for dist in sorted(groups.keys()):
                    rows.append([d, n, "БАЗА", f"Округ {dist}", "", ""])
                    for item in groups[dist]: rows.append([d, n, "", dist, item.get("works", ""), fmt(item.get("amount", 0))])
                continue
            diff = step.get("diff", {}); changes_by_dist = {}
            for item in diff.get("added", []):
                dist = item.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("ДОБАВЛЕНО", item, item.get("amount", 0)))
            for item in diff.get("removed", []):
                dist = item.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("УДАЛЕНО", item, item.get("amount", 0)))
            for c in diff.get("changed", []):
                b, a = c["before"], c["after"]; dist = a.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("ИЗМЕНЕНО", a, (b.get("amount", 0), a.get("amount", 0))))
            if not changes_by_dist: continue
            for dist in sorted(changes_by_dist.keys()):
                rows.append([d, n, "", f"Округ {dist}", "", ""])
                for action, item, val in changes_by_dist[dist]:
                    amount_str = f"{fmt(val[0])} → {fmt(val[1])}" if action == "ИЗМЕНЕНО" else fmt(val)
                    rows.append([d, n, action, dist, item.get("works", ""), amount_str])
        self.post_tree.set_sheet_data(rows)
        for i, row in enumerate(rows):
            if row[3].startswith("Округ") or row[3] == "Без округа":
                if not row[2] and not row[4] and not row[5]: self.post_tree.highlight_cells(row=i, bg="#eef2f7", fg="#000")

    def _compare_with_selected_duma(self):
        sel_idx = self.decision_cb.current()
        if sel_idx < 0 or not hasattr(self, 'all_duma_files') or sel_idx >= len(self.all_duma_files): return
        sel_file = self.all_duma_files[sel_idx]; changes_path = Path("changes.json")
        if not changes_path.exists(): return
        data = json.loads(changes_path.read_text(encoding="utf-8")); timeline = data.get("timeline", [])
        selected_step = next((s for s in timeline if s.get("date") == sel_file["date"] and s.get("number") == sel_file["number"]), None)
        if not selected_step:
            self.err_tree.set_sheet_data([["Нет данных", f"В выбранном решении Думы от {sel_file['date']} № {sel_file['number']} не содержится информация по разделу ТОС (Наказы)", "—", "—", "—", "—"]])
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой"); return
        target_items = selected_step.get("items", []); duma_map = {}
        group_mapping = {"10": "1", "12": "2", "20": "3", "27": "4", "31": "5", "33": "6", "МИО Галушко В.Ф.": "7"}
        for item in target_items:
            if item.get("status") != "ok": continue
            dist = item.get("district", "").strip(); g = group_mapping.get(dist)
            if not g: continue
            name = item.get("works", "").strip(); amount = float(item.get("amount") or 0)
            duma_map[(g, name)] = (amount, item.get("institution", ""))
        error_details = []; found_keys = set(); postanovlenie = self.data["editions"][self.selected_edition]["label"]
        app3_events = [e for e in get_effective_events(self.data, self.selected_edition) if e.get("source") == "app3"]
        if len(duma_map) < len(app3_events) * 0.5:
            self.err_tree.set_sheet_data([["Неполные данные", f"В выбранном решении Думы от {sel_file['date']} № {sel_file['number']} не содержится полная информация по разделу ТОС. Найдено {len(duma_map)} мероприятий из {len(app3_events)}. Сравнение невозможно.", "—", "—", "—", "—"]])
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой"); self.notebook.select(self.tab_errors); return
        def get_duma_source(g, name):
            for step in reversed(timeline):
                if step["kind"] == "amendment":
                    diff = step.get("diff", {})
                    for lst in (diff.get("added", []), diff.get("changed", [])):
                        for it in lst:
                            if group_mapping.get(it.get("district", "").strip()) == g and it.get("works", "").strip() == name: return f"от {step['date']} № {step['number']}"
            base = timeline[0]; return f"от {base['date']} № {base['number']} (база)"
        for ev in app3_events:
            g = ev.get("group"); m = re.search(r'«(.*)»', ev["name"]); name = m.group(1) if m else ev["name"]; key = (g, name)
            if key in duma_map:
                found_keys.add(key); expected = duma_map[key][0]; current = get_event_value_at(ev, 2026, self.data, self.selected_edition)
                if abs(current - expected) > 0.01:
                    error_details.append({"id": ev["id"], "name": ev["name"], "type": "Неверная сумма", "current": fmt(current), "expected": fmt(expected), "duma_source": get_duma_source(g, name), "postanovlenie": postanovlenie})
            else:
                error_details.append({"id": ev["id"], "name": ev["name"], "type": "Нет в Думе (лишнее)", "current": fmt(get_event_value_at(ev, 2026, self.data, self.selected_edition)), "expected": "—", "duma_source": get_duma_source(g, name), "postanovlenie": postanovlenie})
        added_details = []; is_latest = (selected_step == timeline[-1])
        if is_latest:
            for (g, name), (amount, inst) in duma_map.items():
                if (g, name) not in found_keys:
                    existing_nums = [int(re.search(r'п\.\s*\d+\.(\d+)', e["name"]).group(1)) for e in app3_events if e.get("group")==g and re.search(r'п\.\s*\d+\.(\d+)', e["name"])]
                    next_num = max(existing_nums) + 1 if existing_nums else 1; new_id = f"duma_{g}_{next_num}"
                    ed = self.data["editions"][self.selected_edition]
                    existing = any(e.get("name") == f"п. {g}.{next_num} «{name}»" for e in ed.get("added", []))
                    if not existing:
                        ed.setdefault("added", []).append({"id": new_id, "source": "app3", "parent": "e_1_1_3", "group": g, "name": f"п. {g}.{next_num} «{name}»", "old_value": amount, "years": {"2026": amount, "2027": 0.0, "2028": 0.0}, "executor": inst, "is_custom": True})
                        added_details.append({"name": f"п. {g}.{next_num} «{name}»", "amount": fmt(amount)})
        self.data["duma_errors"] = [e["id"] for e in error_details]
        self._save_data(explicit=True); self.refresh_table(); self.refresh_totals(); self._update_duma_errors_tab(error_details, added_details)

    def _update_duma_errors_tab(self, errors, added):
        self.last_errors = errors
        self.last_added = added
        
        # 1. Таблица
        data = []
        for e in errors: data.append([e["type"], e["name"], e["current"], e["expected"], e.get("duma_source", "—"), e.get("postanovlenie", "—")])
        for a in added: data.append(["Добавлено из Думы", a["name"], "—", a["amount"], "—", "—"])
        if not errors and not added: data.append(["Успех", "Расхождений с Думой не найдено.", "—", "—", "—", "—"])
        
        self.err_tree.set_sheet_data(data)
        
        import textwrap
        heights = []
        for row in data:
            text = str(row[1]) if len(row) > 1 else ""; lines = [text]
            heights.append(max(25, len(lines) * 18 + 5))
        if heights: self.err_tree.set_row_heights(heights)

        # 2. Обновляем текстовый отчет
        self._refresh_error_details_text()

        # 3. Переключение вкладок
        if errors:
            self.notebook.tab(self.tab_errors, text=f"Расхождения ({len(errors)}) ⚠")
            self.notebook.tab(self.tab_error_details, text=f"Ошибки: подробно ({len(errors)}) ⚠")
            self.notebook.select(self.tab_errors)
        elif added:
            self.notebook.tab(self.tab_errors, text=f"Добавлено ({len(added)})")
            self.notebook.tab(self.tab_error_details, text=f"Добавлено ({len(added)})")
            self.notebook.select(self.tab_errors)
        else:
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой (OK)")
            self.notebook.tab(self.tab_error_details, text="Ошибки: подробно")
            self.notebook.select(self.tab_main)

    def _on_duma_decision_change(self, event):
        sel = self.decision_cb.get()
        self.logger.info(f"Выбрано решение Думы для сравнения: «{sel}»")
        self._compare_with_selected_duma()

    def _update_errors_button(self):
        if hasattr(self, 'unresolved_districts') and self.unresolved_districts: self.btn_errors.configure(state="normal")
        else: self.btn_errors.configure(state="disabled")

    def _show_errors_dialog(self):
        if hasattr(self, 'unresolved_districts') and self.unresolved_districts: self._ask_for_missing_districts()
        else: messagebox.showinfo("Ошибки парсинга", "Все округа успешно определены.")

    def _ask_for_missing_districts(self):
        if not hasattr(self, 'unresolved_districts') or not self.unresolved_districts: return
        if hasattr(self, '_error_win') and self._error_win.winfo_exists(): self._error_win.lift(); return
        self._error_win = tk.Toplevel(self.root); self._error_win.title("Ошибка парсинга: не указан округ"); self._error_win.geometry("850x450"); self._error_win.transient(self.root)
        ttk.Label(self._error_win, text="В решениях Думы не удалось определить округ для следующих мероприятий.\nПожалуйста, укажите его (программа запомнит ваш выбор):", font=("TkDefaultFont", 10, "bold"), padding=10).pack()
        canvas = tk.Canvas(self._error_win); scrollbar = ttk.Scrollbar(self._error_win, orient="vertical", command=canvas.yview); scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))); canvas.create_window((0, 0), window=scrollable_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5); scrollbar.pack(side="right", fill="y")
        vars = {}; row = 0; fixes_file = Path("district_fixes.json"); fixes = {}
        if fixes_file.exists():
            try: fixes = json.loads(fixes_file.read_text(encoding="utf-8"))
            except Exception: pass
        for works, data in self.unresolved_districts.items():
            sources_str = ", ".join(data["sources"]); lbl_text = f"{works}\n(Встречается в: {sources_str})"
            ttk.Label(scrollable_frame, text=lbl_text, wraplength=500, justify="left").grid(row=row, column=0, sticky="w", pady=5, padx=5)
            var = tk.StringVar()
            if works in fixes: gid = fixes[works]; val = next((g[1] for g in GROUPS if g[0] == gid), ""); var.set(val)
            choices = [g[1] for g in GROUPS] + ["Без округа"]; cb = ttk.Combobox(scrollable_frame, textvariable=var, state="readonly", values=choices, width=40)
            cb.grid(row=row, column=1, sticky="w", padx=10, pady=5); vars[works] = var; row += 1
        def save():
            for works, var in vars.items():
                val = var.get()
                if not val: messagebox.showwarning("Ошибка", f"Пожалуйста, укажите округ для:\n{works}", parent=self._error_win); return
                if val == "Без округа": gid = "0"
                else: gid = next((g[0] for g in GROUPS if g[1] == val), "")
                if gid is not None: fixes[works] = gid
                if works in self.unresolved_districts: del self.unresolved_districts[works]
            fixes_file.write_text(json.dumps(fixes, ensure_ascii=False, indent=2), encoding="utf-8"); self._update_errors_button(); self._error_win.destroy(); self._sync_from_duma(silent=True)
        ttk.Button(self._error_win, text="💾 Сохранить и продолжить", command=save).pack(pady=10)

    def _populate_nakazy_tab(self, timeline):
        try:
            if not timeline: return
            master_decisions = []
            try:
                data = json.loads(Path("changes.json").read_text(encoding="utf-8"))
                base = timeline[0]; master_decisions.append({"date": base["date"], "number": base["number"], "is_base": True})
                for ch in data.get("changes", []): master_decisions.append({"date": ch["date"], "number": ch["number"], "is_base": False})
                for step in timeline[1:]:
                    if not any(m["date"] == step["date"] and m["number"] == step["number"] for m in master_decisions): master_decisions.append({"date": step["date"], "number": step["number"], "is_base": False})
                def parse_date(d_str):
                    try: return datetime.strptime(d_str, "%d.%m.%Y")
                    except: return datetime.min
                master_decisions.sort(key=lambda x: parse_date(x["date"]))
            except Exception as e: self.logger.error(f"Ошибка чтения changes.json: {e}"); return
            all_events = set()
            for step in timeline:
                for item in step.get("items", []):
                    if item.get("status") == "ok":
                        dist = item.get("district", "").strip()
                        if not dist: dist = "Без округа"
                        all_events.add((dist, item.get("works", "").strip()))
            def sort_key(x):
                dist = x[0]
                if dist.isdigit(): return (int(dist), x[1])
                return (999, x[1])
            sorted_events = sorted(all_events, key=sort_key)
            headers = ["Округ", "Мероприятие"] + [f"{m['date']} N {m['number']}" for m in master_decisions]
            self.nakazy_tree.headers(headers)
            self.nakazy_tree.column_width(0, width=100); self.nakazy_tree.column_width(1, width=300)
            for i in range(2, len(headers)): self.nakazy_tree.column_width(i, width=110)
            timeline_steps = {(s["date"], s["number"]): s for s in timeline}
            final_rows = []; current_district = None
            for event in sorted_events:
                dist, name = event
                if dist != current_district:
                    current_district = dist
                    group_name = f"Округ {dist}" if dist and dist != "0" else "Без округа"
                    final_rows.append([group_name, "", ""] + [""] * len(master_decisions))
                row_values = [dist, name]; current_amount = None; is_removed = False
                for m_dec in master_decisions:
                    step = timeline_steps.get((m_dec["date"], m_dec["number"]))
                    if m_dec["is_base"]:
                        item_in_step = next((it for it in step.get("items", []) if it.get("district","").strip() == dist and it.get("works","").strip() == name and it.get("status") == "ok"), None) if step else None
                        if item_in_step: current_amount = float(item_in_step.get("amount") or 0); row_values.append(fmt(current_amount))
                        else: row_values.append("—")
                        continue
                    if not step:
                        if is_removed: row_values.append("убрано ранее")
                        elif current_amount is None: row_values.append("—")
                        else: row_values.append("не меняется")
                        continue
                    diff = step.get("diff", {})
                    removed = any(rem.get("district","").strip() == dist and rem.get("works","").strip() == name for rem in diff.get("removed", []))
                    if removed: row_values.append(f"убрано от {step['date']}"); is_removed = True; current_amount = None; continue
                    added = next((it for it in diff.get("added", []) if it.get("district","").strip() == dist and it.get("works","").strip() == name), None)
                    if added: current_amount = float(added.get("amount") or 0); row_values.append(fmt(current_amount)); is_removed = False; continue
                    changed = next((c for c in diff.get("changed", []) if c["after"].get("district","").strip() == dist and c["after"].get("works","").strip() == name), None)
                    if changed: current_amount = float(changed["after"].get("amount") or 0); row_values.append(fmt(current_amount)); continue
                    if is_removed: row_values.append("убрано ранее")
                    elif current_amount is None: row_values.append("—")
                    else: row_values.append("не меняется")
                import textwrap
                wrapped_name = "\n".join([name])
                display_values = [dist, wrapped_name] + row_values[2:]
                final_rows.append(display_values)
            self.nakazy_tree.set_sheet_data(final_rows)
            for i, row in enumerate(final_rows):
                if row[1] == "": self.nakazy_tree.highlight_cells(row=i, bg="#eef2f7", fg="#000")
        except Exception as e:
            self.logger.error(f"Ошибка в _populate_nakazy_tab: {e}\n{traceback.format_exc()}")

    def _populate_history_tab(self, timeline):
        rows = []
        for step in timeline:
            d, n = step.get("date", ""), step.get("number", "")
            if step["kind"] == "base":
                base_items = step.get("items", [])
                groups = {}
                for item in base_items:
                    if item.get("status") != "ok": continue
                    dist = item.get("district", "").strip()
                    if not dist: dist = "Без округа"
                    groups.setdefault(dist, []).append(item)
                for dist in sorted(groups.keys()):
                    rows.append([d, n, "БАЗА", f"Округ {dist}", "", ""])
                    for item in groups[dist]: rows.append([d, n, "", dist, item.get("works", ""), fmt(item.get("amount", 0))])
                continue
            diff = step.get("diff", {}); changes_by_dist = {}
            for item in diff.get("added", []):
                dist = item.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("ДОБАВЛЕНО", item, item.get("amount", 0)))
            for item in diff.get("removed", []):
                dist = item.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("УДАЛЕНО", item, item.get("amount", 0)))
            for c in diff.get("changed", []):
                b, a = c["before"], c["after"]; dist = a.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("ИЗМЕНЕНО", a, (b.get("amount", 0), a.get("amount", 0))))
            if not changes_by_dist: continue
            for dist in sorted(changes_by_dist.keys()):
                rows.append([d, n, "", f"Округ {dist}", "", ""])
                for action, item, val in changes_by_dist[dist]:
                    amount_str = f"{fmt(val[0])} → {fmt(val[1])}" if action == "ИЗМЕНЕНО" else fmt(val)
                    rows.append([d, n, action, dist, item.get("works", ""), amount_str])
        self.post_tree.set_sheet_data(rows)
        for i, row in enumerate(rows):
            if row[3].startswith("Округ") or row[3] == "Без округа":
                if not row[2] and not row[4] and not row[5]: self.post_tree.highlight_cells(row=i, bg="#eef2f7", fg="#000")

    def _compare_with_selected_duma(self):
        sel_idx = self.decision_cb.current()
        if sel_idx < 0 or not hasattr(self, 'all_duma_files') or sel_idx >= len(self.all_duma_files): return
        sel_file = self.all_duma_files[sel_idx]; changes_path = Path("changes.json")
        if not changes_path.exists(): return
        data = json.loads(changes_path.read_text(encoding="utf-8")); timeline = data.get("timeline", [])
        selected_step = next((s for s in timeline if s.get("date") == sel_file["date"] and s.get("number") == sel_file["number"]), None)
        if not selected_step:
            self.err_tree.set_sheet_data([["Нет данных", f"В выбранном решении Думы от {sel_file['date']} № {sel_file['number']} не содержится информация по разделу ТОС (Наказы)", "—", "—", "—", "—"]])
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой"); return
        target_items = selected_step.get("items", []); duma_map = {}
        group_mapping = {"10": "1", "12": "2", "20": "3", "27": "4", "31": "5", "33": "6", "МИО Галушко В.Ф.": "7"}
        for item in target_items:
            if item.get("status") != "ok": continue
            dist = item.get("district", "").strip(); g = group_mapping.get(dist)
            if not g: continue
            name = item.get("works", "").strip(); amount = float(item.get("amount") or 0)
            duma_map[(g, name)] = (amount, item.get("institution", ""))
        error_details = []; found_keys = set(); postanovlenie = self.data["editions"][self.selected_edition]["label"]
        app3_events = [e for e in get_effective_events(self.data, self.selected_edition) if e.get("source") == "app3"]
        if len(duma_map) < len(app3_events) * 0.5:
            self.err_tree.set_sheet_data([["Неполные данные", f"В выбранном решении Думы от {sel_file['date']} № {sel_file['number']} не содержится полная информация по разделу ТОС. Найдено {len(duma_map)} мероприятий из {len(app3_events)}. Сравнение невозможно.", "—", "—", "—", "—"]])
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой"); self.notebook.select(self.tab_errors); return
        def get_duma_source(g, name):
            for step in reversed(timeline):
                if step["kind"] == "amendment":
                    diff = step.get("diff", {})
                    for lst in (diff.get("added", []), diff.get("changed", [])):
                        for it in lst:
                            if group_mapping.get(it.get("district", "").strip()) == g and it.get("works", "").strip() == name: return f"от {step['date']} № {step['number']}"
            base = timeline[0]; return f"от {base['date']} № {base['number']} (база)"
        for ev in app3_events:
            g = ev.get("group"); m = re.search(r'«(.*)»', ev["name"]); name = m.group(1) if m else ev["name"]; key = (g, name)
            if key in duma_map:
                found_keys.add(key); expected = duma_map[key][0]; current = get_event_value_at(ev, 2026, self.data, self.selected_edition)
                if abs(current - expected) > 0.01:
                    error_details.append({"id": ev["id"], "name": ev["name"], "type": "Неверная сумма", "current": fmt(current), "expected": fmt(expected), "duma_source": get_duma_source(g, name), "postanovlenie": postanovlenie})
            else:
                error_details.append({"id": ev["id"], "name": ev["name"], "type": "Нет в Думе (лишнее)", "current": fmt(get_event_value_at(ev, 2026, self.data, self.selected_edition)), "expected": "—", "duma_source": get_duma_source(g, name), "postanovlenie": postanovlenie})
        added_details = []; is_latest = (selected_step == timeline[-1])
        if is_latest:
            for (g, name), (amount, inst) in duma_map.items():
                if (g, name) not in found_keys:
                    existing_nums = [int(re.search(r'п\.\s*\d+\.(\d+)', e["name"]).group(1)) for e in app3_events if e.get("group")==g and re.search(r'п\.\s*\d+\.(\d+)', e["name"])]
                    next_num = max(existing_nums) + 1 if existing_nums else 1; new_id = f"duma_{g}_{next_num}"
                    ed = self.data["editions"][self.selected_edition]
                    existing = any(e.get("name") == f"п. {g}.{next_num} «{name}»" for e in ed.get("added", []))
                    if not existing:
                        ed.setdefault("added", []).append({"id": new_id, "source": "app3", "parent": "e_1_1_3", "group": g, "name": f"п. {g}.{next_num} «{name}»", "old_value": amount, "years": {"2026": amount, "2027": 0.0, "2028": 0.0}, "executor": inst, "is_custom": True})
                        added_details.append({"name": f"п. {g}.{next_num} «{name}»", "amount": fmt(amount)})
        self.data["duma_errors"] = [e["id"] for e in error_details]
        self._save_data(explicit=True); self.refresh_table(); self.refresh_totals(); self._update_duma_errors_tab(error_details, added_details)

    def _update_duma_errors_tab(self, errors, added):
        print(f"DEBUG: _update_duma_errors_tab вызван, ошибок: {len(errors)}, добавлено: {len(added)}")
        
        # 1. Таблица
        data = []
        for e in errors: data.append([e["type"], e["name"], e["current"], e["expected"], e.get("duma_source", "—"), e.get("postanovlenie", "—")])
        for a in added: data.append(["Добавлено из Думы", a["name"], "—", a["amount"], "—", "—"])
        if not errors and not added: data.append(["Успех", "Расхождений с Думой не найдено.", "—", "—", "—", "—"])
        
        self.err_tree.set_sheet_data(data)
        print(f"DEBUG: Таблица обновлена, строк: {len(data)}")
        
        import textwrap
        heights = []
        for row in data:
            text = str(row[1]) if len(row) > 1 else ""; lines = [text]
            heights.append(max(25, len(lines) * 18 + 5))
        if heights: self.err_tree.set_row_heights(heights)

        # 2. Текстовый отчет
        try:
            print("DEBUG: Начинаем заполнять текстовый отчет...")
            self.error_details_text.configure(state="normal")
            self.error_details_text.delete("1.0", tk.END)
            
            if not errors and not added:
                self.error_details_text.insert(tk.END, "✅ РАСХОЖДЕНИЙ НЕ НАЙДЕНО\n\n")
                self.error_details_text.insert(tk.END, "Все мероприятия в Конструкторе полностью совпадают с выбранным решением Думы.\n\n")
                self.error_details_text.insert(tk.END, "Если вы хотите внести изменения, создайте новую редакцию постановления.")
            else:
                self.error_details_text.insert(tk.END, f"ВНИМАНИЕ! Найдено проблем: {len(errors) + len(added)}\n")
                self.error_details_text.insert(tk.END, "=" * 60 + "\n\n")
                
                for i, e in enumerate(errors, start=1):
                    self.error_details_text.insert(tk.END, f"❌ ПРОБЛЕМА №{i}: {e['type'].upper()}\n")
                    self.error_details_text.insert(tk.END, f"Мероприятие: {e['name']}\n")
                    self.error_details_text.insert(tk.END, f"Сейчас в Конструкторе: {e['current']}\n")
                    self.error_details_text.insert(tk.END, f"По данным Думы: {e['expected']}\n")
                    self.error_details_text.insert(tk.END, f"Источник в Думе: {e['duma_source']}\n")
                    self.error_details_text.insert(tk.END, f"Редакция Конструктора: {e['postanovlenie']}\n")
                    self.error_details_text.insert(tk.END, "-" * 60 + "\n\n")
                    
                for a in added:
                    self.error_details_text.insert(tk.END, f"✅ ДОБАВЛЕНО ИЗ ДУМЫ: {a['name']}\n")
                    self.error_details_text.insert(tk.END, f"Сумма: {a['amount']}\n")
                    self.error_details_text.insert(tk.END, "-" * 60 + "\n\n")
                    
            self.error_details_text.configure(state="disabled")
            print("DEBUG: Текстовый отчет заполнен.")
        except Exception as e:
            print(f"DEBUG: ОШИБКА при заполнении текстового отчета: {e}")
            import traceback; traceback.print_exc()

        # 3. Переключение вкладок
        if errors:
            self.notebook.tab(self.tab_errors, text=f"Расхождения ({len(errors)}) ⚠")
            self.notebook.tab(self.tab_error_details, text=f"Ошибки: подробно ({len(errors)}) ⚠")
        elif added:
            self.notebook.tab(self.tab_errors, text=f"Добавлено ({len(added)})")
            self.notebook.tab(self.tab_error_details, text=f"Добавлено ({len(added)})")
        else:
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой (OK)")
            self.notebook.tab(self.tab_error_details, text="Ошибки: подробно")

    def _on_duma_decision_change(self, event):
        sel = self.decision_cb.get()
        self.logger.info(f"Выбрано решение Думы для сравнения: «{sel}»")
        self._compare_with_selected_duma()

    def _update_errors_button(self):
        if hasattr(self, 'unresolved_districts') and self.unresolved_districts: self.btn_errors.configure(state="normal")
        else: self.btn_errors.configure(state="disabled")

    def _show_errors_dialog(self):
        if hasattr(self, 'unresolved_districts') and self.unresolved_districts: self._ask_for_missing_districts()
        else: messagebox.showinfo("Ошибки парсинга", "Все округа успешно определены.")

    def _ask_for_missing_districts(self):
        if not hasattr(self, 'unresolved_districts') or not self.unresolved_districts: return
        if hasattr(self, '_error_win') and self._error_win.winfo_exists(): self._error_win.lift(); return
        self._error_win = tk.Toplevel(self.root); self._error_win.title("Ошибка парсинга: не указан округ"); self._error_win.geometry("850x450"); self._error_win.transient(self.root)
        ttk.Label(self._error_win, text="В решениях Думы не удалось определить округ для следующих мероприятий.\nПожалуйста, укажите его (программа запомнит ваш выбор):", font=("TkDefaultFont", 10, "bold"), padding=10).pack()
        canvas = tk.Canvas(self._error_win); scrollbar = ttk.Scrollbar(self._error_win, orient="vertical", command=canvas.yview); scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))); canvas.create_window((0, 0), window=scrollable_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5); scrollbar.pack(side="right", fill="y")
        vars = {}; row = 0; fixes_file = Path("district_fixes.json"); fixes = {}
        if fixes_file.exists():
            try: fixes = json.loads(fixes_file.read_text(encoding="utf-8"))
            except Exception: pass
        for works, data in self.unresolved_districts.items():
            sources_str = ", ".join(data["sources"]); lbl_text = f"{works}\n(Встречается в: {sources_str})"
            ttk.Label(scrollable_frame, text=lbl_text, wraplength=500, justify="left").grid(row=row, column=0, sticky="w", pady=5, padx=5)
            var = tk.StringVar()
            if works in fixes: gid = fixes[works]; val = next((g[1] for g in GROUPS if g[0] == gid), ""); var.set(val)
            choices = [g[1] for g in GROUPS] + ["Без округа"]; cb = ttk.Combobox(scrollable_frame, textvariable=var, state="readonly", values=choices, width=40)
            cb.grid(row=row, column=1, sticky="w", padx=10, pady=5); vars[works] = var; row += 1
        def save():
            for works, var in vars.items():
                val = var.get()
                if not val: messagebox.showwarning("Ошибка", f"Пожалуйста, укажите округ для:\n{works}", parent=self._error_win); return
                if val == "Без округа": gid = "0"
                else: gid = next((g[0] for g in GROUPS if g[1] == val), "")
                if gid is not None: fixes[works] = gid
                if works in self.unresolved_districts: del self.unresolved_districts[works]
            fixes_file.write_text(json.dumps(fixes, ensure_ascii=False, indent=2), encoding="utf-8"); self._update_errors_button(); self._error_win.destroy(); self._sync_from_duma(silent=True)
        ttk.Button(self._error_win, text="💾 Сохранить и продолжить", command=save).pack(pady=10)

    def _populate_nakazy_tab(self, timeline):
        try:
            if not timeline: return
            master_decisions = []
            try:
                data = json.loads(Path("changes.json").read_text(encoding="utf-8"))
                base = timeline[0]; master_decisions.append({"date": base["date"], "number": base["number"], "is_base": True})
                for ch in data.get("changes", []): master_decisions.append({"date": ch["date"], "number": ch["number"], "is_base": False})
                for step in timeline[1:]:
                    if not any(m["date"] == step["date"] and m["number"] == step["number"] for m in master_decisions): master_decisions.append({"date": step["date"], "number": step["number"], "is_base": False})
                def parse_date(d_str):
                    try: return datetime.strptime(d_str, "%d.%m.%Y")
                    except: return datetime.min
                master_decisions.sort(key=lambda x: parse_date(x["date"]))
            except Exception as e: self.logger.error(f"Ошибка чтения changes.json: {e}"); return
            all_events = set()
            for step in timeline:
                for item in step.get("items", []):
                    if item.get("status") == "ok":
                        dist = item.get("district", "").strip()
                        if not dist: dist = "Без округа"
                        all_events.add((dist, item.get("works", "").strip()))
            def sort_key(x):
                dist = x[0]
                if dist.isdigit(): return (int(dist), x[1])
                return (999, x[1])
            sorted_events = sorted(all_events, key=sort_key)
            headers = ["Округ", "Мероприятие"] + [f"{m['date']} N {m['number']}" for m in master_decisions]
            self.nakazy_tree.headers(headers)
            self.nakazy_tree.column_width(0, width=100); self.nakazy_tree.column_width(1, width=300)
            for i in range(2, len(headers)): self.nakazy_tree.column_width(i, width=110)
            timeline_steps = {(s["date"], s["number"]): s for s in timeline}
            final_rows = []; current_district = None
            for event in sorted_events:
                dist, name = event
                if dist != current_district:
                    current_district = dist
                    group_name = f"Округ {dist}" if dist and dist != "0" else "Без округа"
                    final_rows.append([group_name, "", ""] + [""] * len(master_decisions))
                row_values = [dist, name]; current_amount = None; is_removed = False
                for m_dec in master_decisions:
                    step = timeline_steps.get((m_dec["date"], m_dec["number"]))
                    if m_dec["is_base"]:
                        item_in_step = next((it for it in step.get("items", []) if it.get("district","").strip() == dist and it.get("works","").strip() == name and it.get("status") == "ok"), None) if step else None
                        if item_in_step: current_amount = float(item_in_step.get("amount") or 0); row_values.append(fmt(current_amount))
                        else: row_values.append("—")
                        continue
                    if not step:
                        if is_removed: row_values.append("убрано ранее")
                        elif current_amount is None: row_values.append("—")
                        else: row_values.append("не меняется")
                        continue
                    diff = step.get("diff", {})
                    removed = any(rem.get("district","").strip() == dist and rem.get("works","").strip() == name for rem in diff.get("removed", []))
                    if removed: row_values.append(f"убрано от {step['date']}"); is_removed = True; current_amount = None; continue
                    added = next((it for it in diff.get("added", []) if it.get("district","").strip() == dist and it.get("works","").strip() == name), None)
                    if added: current_amount = float(added.get("amount") or 0); row_values.append(fmt(current_amount)); is_removed = False; continue
                    changed = next((c for c in diff.get("changed", []) if c["after"].get("district","").strip() == dist and c["after"].get("works","").strip() == name), None)
                    if changed: current_amount = float(changed["after"].get("amount") or 0); row_values.append(fmt(current_amount)); continue
                    if is_removed: row_values.append("убрано ранее")
                    elif current_amount is None: row_values.append("—")
                    else: row_values.append("не меняется")
                import textwrap
                wrapped_name = "\n".join([name])
                display_values = [dist, wrapped_name] + row_values[2:]
                final_rows.append(display_values)
            self.nakazy_tree.set_sheet_data(final_rows)
            for i, row in enumerate(final_rows):
                if row[1] == "": self.nakazy_tree.highlight_cells(row=i, bg="#eef2f7", fg="#000")
        except Exception as e:
            self.logger.error(f"Ошибка в _populate_nakazy_tab: {e}\n{traceback.format_exc()}")

    def _populate_history_tab(self, timeline):
        rows = []
        for step in timeline:
            d, n = step.get("date", ""), step.get("number", "")
            if step["kind"] == "base":
                base_items = step.get("items", [])
                groups = {}
                for item in base_items:
                    if item.get("status") != "ok": continue
                    dist = item.get("district", "").strip()
                    if not dist: dist = "Без округа"
                    groups.setdefault(dist, []).append(item)
                for dist in sorted(groups.keys()):
                    rows.append([d, n, "БАЗА", f"Округ {dist}", "", ""])
                    for item in groups[dist]: rows.append([d, n, "", dist, item.get("works", ""), fmt(item.get("amount", 0))])
                continue
            diff = step.get("diff", {}); changes_by_dist = {}
            for item in diff.get("added", []):
                dist = item.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("ДОБАВЛЕНО", item, item.get("amount", 0)))
            for item in diff.get("removed", []):
                dist = item.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("УДАЛЕНО", item, item.get("amount", 0)))
            for c in diff.get("changed", []):
                b, a = c["before"], c["after"]; dist = a.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("ИЗМЕНЕНО", a, (b.get("amount", 0), a.get("amount", 0))))
            if not changes_by_dist: continue
            for dist in sorted(changes_by_dist.keys()):
                rows.append([d, n, "", f"Округ {dist}", "", ""])
                for action, item, val in changes_by_dist[dist]:
                    amount_str = f"{fmt(val[0])} → {fmt(val[1])}" if action == "ИЗМЕНЕНО" else fmt(val)
                    rows.append([d, n, action, dist, item.get("works", ""), amount_str])
        self.post_tree.set_sheet_data(rows)
        for i, row in enumerate(rows):
            if row[3].startswith("Округ") or row[3] == "Без округа":
                if not row[2] and not row[4] and not row[5]: self.post_tree.highlight_cells(row=i, bg="#eef2f7", fg="#000")

    def _compare_with_selected_duma(self):
        sel_idx = self.decision_cb.current()
        if sel_idx < 0 or not hasattr(self, 'all_duma_files') or sel_idx >= len(self.all_duma_files): return
        sel_file = self.all_duma_files[sel_idx]; changes_path = Path("changes.json")
        if not changes_path.exists(): return
        data = json.loads(changes_path.read_text(encoding="utf-8")); timeline = data.get("timeline", [])
        selected_step = next((s for s in timeline if s.get("date") == sel_file["date"] and s.get("number") == sel_file["number"]), None)
        if not selected_step:
            self.err_tree.set_sheet_data([["Нет данных", f"В выбранном решении Думы от {sel_file['date']} № {sel_file['number']} не содержится информация по разделу ТОС (Наказы)", "—", "—", "—", "—"]])
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой"); return
        target_items = selected_step.get("items", []); duma_map = {}
        group_mapping = {"10": "1", "12": "2", "20": "3", "27": "4", "31": "5", "33": "6", "МИО Галушко В.Ф.": "7"}
        for item in target_items:
            if item.get("status") != "ok": continue
            dist = item.get("district", "").strip(); g = group_mapping.get(dist)
            if not g: continue
            name = item.get("works", "").strip(); amount = float(item.get("amount") or 0)
            duma_map[(g, name)] = (amount, item.get("institution", ""))
        error_details = []; found_keys = set(); postanovlenie = self.data["editions"][self.selected_edition]["label"]
        app3_events = [e for e in get_effective_events(self.data, self.selected_edition) if e.get("source") == "app3"]
        if len(duma_map) < len(app3_events) * 0.5:
            self.err_tree.set_sheet_data([["Неполные данные", f"В выбранном решении Думы от {sel_file['date']} № {sel_file['number']} не содержится полная информация по разделу ТОС. Найдено {len(duma_map)} мероприятий из {len(app3_events)}. Сравнение невозможно.", "—", "—", "—", "—"]])
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой"); self.notebook.select(self.tab_errors); return
        def get_duma_source(g, name):
            for step in reversed(timeline):
                if step["kind"] == "amendment":
                    diff = step.get("diff", {})
                    for lst in (diff.get("added", []), diff.get("changed", [])):
                        for it in lst:
                            if group_mapping.get(it.get("district", "").strip()) == g and it.get("works", "").strip() == name: return f"от {step['date']} № {step['number']}"
            base = timeline[0]; return f"от {base['date']} № {base['number']} (база)"
        for ev in app3_events:
            g = ev.get("group"); m = re.search(r'«(.*)»', ev["name"]); name = m.group(1) if m else ev["name"]; key = (g, name)
            if key in duma_map:
                found_keys.add(key); expected = duma_map[key][0]; current = get_event_value_at(ev, 2026, self.data, self.selected_edition)
                if abs(current - expected) > 0.01:
                    error_details.append({"id": ev["id"], "name": ev["name"], "type": "Неверная сумма", "current": fmt(current), "expected": fmt(expected), "duma_source": get_duma_source(g, name), "postanovlenie": postanovlenie})
            else:
                error_details.append({"id": ev["id"], "name": ev["name"], "type": "Нет в Думе (лишнее)", "current": fmt(get_event_value_at(ev, 2026, self.data, self.selected_edition)), "expected": "—", "duma_source": get_duma_source(g, name), "postanovlenie": postanovlenie})
        added_details = []; is_latest = (selected_step == timeline[-1])
        if is_latest:
            for (g, name), (amount, inst) in duma_map.items():
                if (g, name) not in found_keys:
                    existing_nums = [int(re.search(r'п\.\s*\d+\.(\d+)', e["name"]).group(1)) for e in app3_events if e.get("group")==g and re.search(r'п\.\s*\d+\.(\d+)', e["name"])]
                    next_num = max(existing_nums) + 1 if existing_nums else 1; new_id = f"duma_{g}_{next_num}"
                    ed = self.data["editions"][self.selected_edition]
                    existing = any(e.get("name") == f"п. {g}.{next_num} «{name}»" for e in ed.get("added", []))
                    if not existing:
                        ed.setdefault("added", []).append({"id": new_id, "source": "app3", "parent": "e_1_1_3", "group": g, "name": f"п. {g}.{next_num} «{name}»", "old_value": amount, "years": {"2026": amount, "2027": 0.0, "2028": 0.0}, "executor": inst, "is_custom": True})
                        added_details.append({"name": f"п. {g}.{next_num} «{name}»", "amount": fmt(amount)})
        self.data["duma_errors"] = [e["id"] for e in error_details]
        self._save_data(explicit=True); self.refresh_table(); self.refresh_totals(); self._update_duma_errors_tab(error_details, added_details)

    def _update_duma_errors_tab(self, errors, added):
        # 1. Заполняем таблицу расхождений
        data = []
        for e in errors: data.append([e["type"], e["name"], e["current"], e["expected"], e.get("duma_source", "—"), e.get("postanovlenie", "—")])
        for a in added: data.append(["Добавлено из Думы", a["name"], "—", a["amount"], "—", "—"])
        if not errors and not added: data.append(["Успех", "Расхождений с Думой не найдено. База мероприятий актуальна.", "—", "—", "—", "—"])
        
        self.err_tree.set_sheet_data(data)
        import textwrap
        heights = []
        for row in data:
            text = str(row[1]) if len(row) > 1 else ""; lines = [text]
            heights.append(max(25, len(lines) * 18 + 5))
        if heights: self.err_tree.set_row_heights(heights)

        # 2. Заполняем текстовый отчет "Ошибки: подробно"
        self.error_details_text.configure(state="normal")
        self.error_details_text.delete("1.0", tk.END)
        
        if not errors and not added:
            self.error_details_text.insert(tk.END, "✅ РАСХОЖДЕНИЙ НЕ НАЙДЕНО\n\n")
            self.error_details_text.insert(tk.END, "Все мероприятия в Конструкторе полностью совпадают с выбранным решением Думы.\n\n")
            self.error_details_text.insert(tk.END, "Если вы хотите внести изменения, создайте новую редакцию постановления.")
        else:
            self.error_details_text.insert(tk.END, f"ВНИМАНИЕ! Найдено проблем: {len(errors) + len(added)}\n")
            self.error_details_text.insert(tk.END, "=" * 60 + "\n\n")
            
            for i, e in enumerate(errors, start=1):
                self.error_details_text.insert(tk.END, f"❌ ПРОБЛЕМА №{i}: {e['type'].upper()}\n", "bold")
                self.error_details_text.insert(tk.END, f"Мероприятие: {e['name']}\n")
                self.error_details_text.insert(tk.END, f"Сейчас в Конструкторе: {e['current']}\n")
                self.error_details_text.insert(tk.END, f"По данным Думы: {e['expected']}\n")
                self.error_details_text.insert(tk.END, f"Источник в Думе: {e['duma_source']}\n")
                self.error_details_text.insert(tk.END, f"Редакция Конструктора: {e['postanovlenie']}\n")
                
                if e['type'] == "Неверная сумма":
                    self.error_details_text.insert(tk.END, "\nПОЧЕМУ: Сумма в Конструкторе не совпадает с официальной цифрой из решения Думы.\n")
                    self.error_details_text.insert(tk.END, "КАК ИСПРАВИТЬ: Перейдите на вкладку «Мероприятия», дважды кликните по колонке «Станет» для этого мероприятия и введите правильную сумму.\n")
                elif e['type'] == "Нет в Думе (лишнее)":
                    self.error_details_text.insert(tk.END, "\nПОЧЕМУ: Этого мероприятия нет в официальном решении Думы. Возможно, оно было отменено или его ошибочно добавили вручную.\n")
                    self.error_details_text.insert(tk.END, "КАК ИСПРАВИТЬ: Нажмите правой кнопкой мыши на это мероприятие в таблице и выберите «🗑 Удалить / Утратило силу» (оно обнулится в текущей редакции).\n")
                self.error_details_text.insert(tk.END, "-" * 60 + "\n\n")
                
            for a in added:
                self.error_details_text.insert(tk.END, f"✅ ДОБАВЛЕНО ИЗ ДУМЫ: {a['name']}\n", "bold")
                self.error_details_text.insert(tk.END, f"Сумма: {a['amount']}\n")
                self.error_details_text.insert(tk.END, "ПОЧЕМУ: Этого мероприятия не хватало в Конструкторе, но оно есть в решении Думы.\n")
                self.error_details_text.insert(tk.END, "КАК ИСПРАВИТЬ: Ничего делать не нужно, программа уже добавила его в текущую редакцию.\n")
                self.error_details_text.insert(tk.END, "-" * 60 + "\n\n")
                
        # Делаем заголовки жирными
        self.error_details_text.tag_configure("bold", font=("TkDefaultFont", 11, "bold"))
        self.error_details_text.configure(state="disabled")

        # Переключаем вкладку, если есть ошибки
        if errors:
            self.notebook.tab(self.tab_errors, text=f"Расхождения ({len(errors)}) ⚠")
            self.notebook.tab(self.tab_error_details, text=f"Ошибки: подробно ({len(errors)}) ⚠")
            self.notebook.select(self.tab_errors)
        elif added:
            self.notebook.tab(self.tab_errors, text=f"Добавлено ({len(added)})")
            self.notebook.tab(self.tab_error_details, text=f"Добавлено ({len(added)})")
            self.notebook.select(self.tab_errors)
        else:
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой (OK)")
            self.notebook.tab(self.tab_error_details, text="Ошибки: подробно")
            self.notebook.select(self.tab_main)

    def _on_duma_decision_change(self, event):
        sel = self.decision_cb.get()
        self.logger.info(f"Выбрано решение Думы для сравнения: «{sel}»")
        self._compare_with_selected_duma()

    def _update_errors_button(self):
        if hasattr(self, 'unresolved_districts') and self.unresolved_districts: self.btn_errors.configure(state="normal")
        else: self.btn_errors.configure(state="disabled")

    def _show_errors_dialog(self):
        if hasattr(self, 'unresolved_districts') and self.unresolved_districts: self._ask_for_missing_districts()
        else: messagebox.showinfo("Ошибки парсинга", "Все округа успешно определены.")

    def _ask_for_missing_districts(self):
        if not hasattr(self, 'unresolved_districts') or not self.unresolved_districts: return
        if hasattr(self, '_error_win') and self._error_win.winfo_exists(): self._error_win.lift(); return
        self._error_win = tk.Toplevel(self.root); self._error_win.title("Ошибка парсинга: не указан округ"); self._error_win.geometry("850x450"); self._error_win.transient(self.root)
        ttk.Label(self._error_win, text="В решениях Думы не удалось определить округ для следующих мероприятий.\nПожалуйста, укажите его (программа запомнит ваш выбор):", font=("TkDefaultFont", 10, "bold"), padding=10).pack()
        canvas = tk.Canvas(self._error_win); scrollbar = ttk.Scrollbar(self._error_win, orient="vertical", command=canvas.yview); scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))); canvas.create_window((0, 0), window=scrollable_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5); scrollbar.pack(side="right", fill="y")
        vars = {}; row = 0; fixes_file = Path("district_fixes.json"); fixes = {}
        if fixes_file.exists():
            try: fixes = json.loads(fixes_file.read_text(encoding="utf-8"))
            except Exception: pass
        for works, data in self.unresolved_districts.items():
            sources_str = ", ".join(data["sources"]); lbl_text = f"{works}\n(Встречается в: {sources_str})"
            ttk.Label(scrollable_frame, text=lbl_text, wraplength=500, justify="left").grid(row=row, column=0, sticky="w", pady=5, padx=5)
            var = tk.StringVar()
            if works in fixes: gid = fixes[works]; val = next((g[1] for g in GROUPS if g[0] == gid), ""); var.set(val)
            choices = [g[1] for g in GROUPS] + ["Без округа"]; cb = ttk.Combobox(scrollable_frame, textvariable=var, state="readonly", values=choices, width=40)
            cb.grid(row=row, column=1, sticky="w", padx=10, pady=5); vars[works] = var; row += 1
        def save():
            for works, var in vars.items():
                val = var.get()
                if not val: messagebox.showwarning("Ошибка", f"Пожалуйста, укажите округ для:\n{works}", parent=self._error_win); return
                if val == "Без округа": gid = "0"
                else: gid = next((g[0] for g in GROUPS if g[1] == val), "")
                if gid is not None: fixes[works] = gid
                if works in self.unresolved_districts: del self.unresolved_districts[works]
            fixes_file.write_text(json.dumps(fixes, ensure_ascii=False, indent=2), encoding="utf-8"); self._update_errors_button(); self._error_win.destroy(); self._sync_from_duma(silent=True)
        ttk.Button(self._error_win, text="💾 Сохранить и продолжить", command=save).pack(pady=10)

    def _populate_nakazy_tab(self, timeline):
        try:
            if not timeline: return
            master_decisions = []
            try:
                data = json.loads(Path("changes.json").read_text(encoding="utf-8"))
                base = timeline[0]; master_decisions.append({"date": base["date"], "number": base["number"], "is_base": True})
                for ch in data.get("changes", []): master_decisions.append({"date": ch["date"], "number": ch["number"], "is_base": False})
                for step in timeline[1:]:
                    if not any(m["date"] == step["date"] and m["number"] == step["number"] for m in master_decisions): master_decisions.append({"date": step["date"], "number": step["number"], "is_base": False})
                def parse_date(d_str):
                    try: return datetime.strptime(d_str, "%d.%m.%Y")
                    except: return datetime.min
                master_decisions.sort(key=lambda x: parse_date(x["date"]))
            except Exception as e: self.logger.error(f"Ошибка чтения changes.json: {e}"); return
            all_events = set()
            for step in timeline:
                for item in step.get("items", []):
                    if item.get("status") == "ok":
                        dist = item.get("district", "").strip()
                        if not dist: dist = "Без округа"
                        all_events.add((dist, item.get("works", "").strip()))
            def sort_key(x):
                dist = x[0]
                if dist.isdigit(): return (int(dist), x[1])
                return (999, x[1])
            sorted_events = sorted(all_events, key=sort_key)
            headers = ["Округ", "Мероприятие"] + [f"{m['date']} N {m['number']}" for m in master_decisions]
            self.nakazy_tree.headers(headers)
            self.nakazy_tree.column_width(0, width=100); self.nakazy_tree.column_width(1, width=300)
            for i in range(2, len(headers)): self.nakazy_tree.column_width(i, width=110)
            timeline_steps = {(s["date"], s["number"]): s for s in timeline}
            final_rows = []; current_district = None
            for event in sorted_events:
                dist, name = event
                if dist != current_district:
                    current_district = dist
                    group_name = f"Округ {dist}" if dist and dist != "0" else "Без округа"
                    final_rows.append([group_name, "", ""] + [""] * len(master_decisions))
                row_values = [dist, name]; current_amount = None; is_removed = False
                for m_dec in master_decisions:
                    step = timeline_steps.get((m_dec["date"], m_dec["number"]))
                    if m_dec["is_base"]:
                        item_in_step = next((it for it in step.get("items", []) if it.get("district","").strip() == dist and it.get("works","").strip() == name and it.get("status") == "ok"), None) if step else None
                        if item_in_step: current_amount = float(item_in_step.get("amount") or 0); row_values.append(fmt(current_amount))
                        else: row_values.append("—")
                        continue
                    if not step:
                        if is_removed: row_values.append("убрано ранее")
                        elif current_amount is None: row_values.append("—")
                        else: row_values.append("не меняется")
                        continue
                    diff = step.get("diff", {})
                    removed = any(rem.get("district","").strip() == dist and rem.get("works","").strip() == name for rem in diff.get("removed", []))
                    if removed: row_values.append(f"убрано от {step['date']}"); is_removed = True; current_amount = None; continue
                    added = next((it for it in diff.get("added", []) if it.get("district","").strip() == dist and it.get("works","").strip() == name), None)
                    if added: current_amount = float(added.get("amount") or 0); row_values.append(fmt(current_amount)); is_removed = False; continue
                    changed = next((c for c in diff.get("changed", []) if c["after"].get("district","").strip() == dist and c["after"].get("works","").strip() == name), None)
                    if changed: current_amount = float(changed["after"].get("amount") or 0); row_values.append(fmt(current_amount)); continue
                    if is_removed: row_values.append("убрано ранее")
                    elif current_amount is None: row_values.append("—")
                    else: row_values.append("не меняется")
                import textwrap
                wrapped_name = "\n".join([name])
                display_values = [dist, wrapped_name] + row_values[2:]
                final_rows.append(display_values)
            self.nakazy_tree.set_sheet_data(final_rows)
            for i, row in enumerate(final_rows):
                if row[1] == "": self.nakazy_tree.highlight_cells(row=i, bg="#eef2f7", fg="#000")
        except Exception as e:
            self.logger.error(f"Ошибка в _populate_nakazy_tab: {e}\n{traceback.format_exc()}")

    def _populate_history_tab(self, timeline):
        rows = []
        for step in timeline:
            d, n = step.get("date", ""), step.get("number", "")
            if step["kind"] == "base":
                base_items = step.get("items", [])
                groups = {}
                for item in base_items:
                    if item.get("status") != "ok": continue
                    dist = item.get("district", "").strip()
                    if not dist: dist = "Без округа"
                    groups.setdefault(dist, []).append(item)
                for dist in sorted(groups.keys()):
                    rows.append([d, n, "БАЗА", f"Округ {dist}", "", ""])
                    for item in groups[dist]: rows.append([d, n, "", dist, item.get("works", ""), fmt(item.get("amount", 0))])
                continue
            diff = step.get("diff", {}); changes_by_dist = {}
            for item in diff.get("added", []):
                dist = item.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("ДОБАВЛЕНО", item, item.get("amount", 0)))
            for item in diff.get("removed", []):
                dist = item.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("УДАЛЕНО", item, item.get("amount", 0)))
            for c in diff.get("changed", []):
                b, a = c["before"], c["after"]; dist = a.get("district", "").strip() or "Без округа"
                changes_by_dist.setdefault(dist, []).append(("ИЗМЕНЕНО", a, (b.get("amount", 0), a.get("amount", 0))))
            if not changes_by_dist: continue
            for dist in sorted(changes_by_dist.keys()):
                rows.append([d, n, "", f"Округ {dist}", "", ""])
                for action, item, val in changes_by_dist[dist]:
                    amount_str = f"{fmt(val[0])} → {fmt(val[1])}" if action == "ИЗМЕНЕНО" else fmt(val)
                    rows.append([d, n, action, dist, item.get("works", ""), amount_str])
        self.post_tree.set_sheet_data(rows)
        for i, row in enumerate(rows):
            if row[3].startswith("Округ") or row[3] == "Без округа":
                if not row[2] and not row[4] and not row[5]: self.post_tree.highlight_cells(row=i, bg="#eef2f7", fg="#000")

    def _compare_with_selected_duma(self):
        sel_idx = self.decision_cb.current()
        if sel_idx < 0 or not hasattr(self, 'all_duma_files') or sel_idx >= len(self.all_duma_files): return
        sel_file = self.all_duma_files[sel_idx]; changes_path = Path("changes.json")
        if not changes_path.exists(): return
        data = json.loads(changes_path.read_text(encoding="utf-8")); timeline = data.get("timeline", [])
        selected_step = next((s for s in timeline if s.get("date") == sel_file["date"] and s.get("number") == sel_file["number"]), None)
        if not selected_step:
            self.err_tree.set_sheet_data([["Нет данных", f"В выбранном решении Думы от {sel_file['date']} № {sel_file['number']} не содержится информация по разделу ТОС (Наказы)", "—", "—", "—", "—"]])
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой"); return
        target_items = selected_step.get("items", []); duma_map = {}
        group_mapping = {"10": "1", "12": "2", "20": "3", "27": "4", "31": "5", "33": "6", "МИО Галушко В.Ф.": "7"}
        for item in target_items:
            if item.get("status") != "ok": continue
            dist = item.get("district", "").strip(); g = group_mapping.get(dist)
            if not g: continue
            name = item.get("works", "").strip(); amount = float(item.get("amount") or 0)
            duma_map[(g, name)] = (amount, item.get("institution", ""))
        error_details = []; found_keys = set(); postanovlenie = self.data["editions"][self.selected_edition]["label"]
        app3_events = [e for e in get_effective_events(self.data, self.selected_edition) if e.get("source") == "app3"]
        if len(duma_map) < len(app3_events) * 0.5:
            self.err_tree.set_sheet_data([["Неполные данные", f"В выбранном решении Думы от {sel_file['date']} № {sel_file['number']} не содержится полная информация по разделу ТОС. Найдено {len(duma_map)} мероприятий из {len(app3_events)}. Сравнение невозможно.", "—", "—", "—", "—"]])
            self.notebook.tab(self.tab_errors, text="Расхождения с Думой"); self.notebook.select(self.tab_errors); return
        def get_duma_source(g, name):
            for step in reversed(timeline):
                if step["kind"] == "amendment":
                    diff = step.get("diff", {})
                    for lst in (diff.get("added", []), diff.get("changed", [])):
                        for it in lst:
                            if group_mapping.get(it.get("district", "").strip()) == g and it.get("works", "").strip() == name: return f"от {step['date']} № {step['number']}"
            base = timeline[0]; return f"от {base['date']} № {base['number']} (база)"
        for ev in app3_events:
            g = ev.get("group"); m = re.search(r'«(.*)»', ev["name"]); name = m.group(1) if m else ev["name"]; key = (g, name)
            if key in duma_map:
                found_keys.add(key); expected = duma_map[key][0]; current = get_event_value_at(ev, 2026, self.data, self.selected_edition)
                if abs(current - expected) > 0.01:
                    error_details.append({"id": ev["id"], "name": ev["name"], "type": "Неверная сумма", "current": fmt(current), "expected": fmt(expected), "duma_source": get_duma_source(g, name), "postanovlenie": postanovlenie})
            else:
                error_details.append({"id": ev["id"], "name": ev["name"], "type": "Нет в Думе (лишнее)", "current": fmt(get_event_value_at(ev, 2026, self.data, self.selected_edition)), "expected": "—", "duma_source": get_duma_source(g, name), "postanovlenie": postanovlenie})
        added_details = []; is_latest = (selected_step == timeline[-1])
        if is_latest:
            for (g, name), (amount, inst) in duma_map.items():
                if (g, name) not in found_keys:
                    existing_nums = [int(re.search(r'п\.\s*\d+\.(\d+)', e["name"]).group(1)) for e in app3_events if e.get("group")==g and re.search(r'п\.\s*\d+\.(\d+)', e["name"])]
                    next_num = max(existing_nums) + 1 if existing_nums else 1; new_id = f"duma_{g}_{next_num}"
                    ed = self.data["editions"][self.selected_edition]
                    existing = any(e.get("name") == f"п. {g}.{next_num} «{name}»" for e in ed.get("added", []))
                    if not existing:
                        ed.setdefault("added", []).append({"id": new_id, "source": "app3", "parent": "e_1_1_3", "group": g, "name": f"п. {g}.{next_num} «{name}»", "old_value": amount, "years": {"2026": amount, "2027": 0.0, "2028": 0.0}, "executor": inst, "is_custom": True})
                        added_details.append({"name": f"п. {g}.{next_num} «{name}»", "amount": fmt(amount)})
        self.data["duma_errors"] = [e["id"] for e in error_details]
        self._save_data(explicit=True); self.refresh_table(); self.refresh_totals(); self._update_duma_errors_tab(error_details, added_details)

    def _update_duma_errors_tab(self, errors, added):
        data = []
        for e in errors: data.append([e["type"], e["name"], e["current"], e["expected"], e.get("duma_source", "—"), e.get("postanovlenie", "—")])
        for a in added: data.append(["Добавлено из Думы", a["name"], "—", a["amount"], "—", "—"])
        if not errors and not added: data.append(["Успех", "Расхождений с Думой не найдено. База мероприятий актуальна.", "—", "—", "—", "—"])
        self.err_tree.set_sheet_data(data)
        import textwrap
        heights = []
        for row in data:
            text = str(row[1]) if len(row) > 1 else ""; lines = [text]
            heights.append(max(25, len(lines) * 18 + 5))
        if heights: self.err_tree.set_row_heights(heights)
        if errors: self.notebook.tab(self.tab_errors, text=f"Расхождения ({len(errors)}) ⚠"); self.notebook.select(self.tab_errors)
        elif added: self.notebook.tab(self.tab_errors, text=f"Добавлено ({len(added)})"); self.notebook.select(self.tab_errors)
        else: self.notebook.tab(self.tab_errors, text="Расхождения с Думой (OK)"); self.notebook.select(self.tab_main)

def main():
    root = tk.Tk()
    app = App(root)
    if getattr(app, "data", None) is None:
        try: root.destroy()
        except tk.TclError: pass
        return
    try: root.mainloop()
    except tk.TclError: pass


# ============================================================
# СЛУЖЕБНЫЕ КОМАНДЫ (были отдельными файлами backup.py,
# rename_backups.py и diagnose.py)
# ============================================================
BACKUP_PATTERNS = ["*.bak", "*.bak2", "*.bak3", "*.bak4", "*.bak5",
                   "*.before_*", "*.manual_backup", "*.final_backup",
                   "*.before_tksheet", "*.before_normalize",
                   "*.before_base_fix", "*.before_base_fix2",
                   "*.before_markers", "*.before_current_fix"]


def make_backup(src_path: Path):
    """Создаёт бэкап одного файла с уникальным именем."""
    if not src_path.exists():
        print(f"❌ Файл не найден: {src_path}")
        return None

    now = datetime.now()
    date_str = now.strftime("%d%m%Y-%H-%M-%S")

    # Счётчик, если такой бэкап уже есть (в эту же секунду)
    n = 1
    while True:
        backup_name = f"{src_path.name}_{date_str}-{n}.bak"
        backup_path = src_path.parent / backup_name
        if not backup_path.exists():
            break
        n += 1

    shutil.copy2(src_path, backup_path)
    print(f"✅ {src_path.name} → {backup_name}")
    return backup_path


def _backup_cli():
    """CLI: python3 constructor.py backup <файл...> | --all"""
    args = sys.argv[2:]

    if not args:
        print("Использование:\n"
              "    python3 constructor.py backup <файл>            # один файл\n"
              "    python3 constructor.py backup <файл1> <файл2>   # несколько\n"
              "    python3 constructor.py backup --all             # все .py и .json в текущей папке")
        return 1

    if args == ["--all"]:
        files = sorted(Path(".").glob("*.py")) + sorted(Path(".").glob("*.json"))
        # Исключаем сами бэкапы; единый код бэкапит сам себя
        files = [f for f in files if ".bak" not in f.name]
        if not files:
            print("❌ Нет файлов .py/.json в текущей папке")
            return 1
        print(f"📦 Делаю бэкапы для {len(files)} файлов...")
        for f in files:
            make_backup(f)
        return 0

    for arg in args:
        p = Path(arg)
        if not make_backup(p):
            return 1
    return 0


def _rename_backups_cli():
    """CLI: python3 constructor.py rename-backups
    Переименовывает все бэкапы в формат {имя}_{ддммгггг-чч-мм-сс}-{n}.bak (дата из mtime)."""
    folder = Path(".")
    all_backups = set()
    for pattern in BACKUP_PATTERNS:
        all_backups.update(folder.glob(pattern))

    # Исключаем уже переименованные (формат _ддммгггг-чч-мм-сс-n.bak)
    already_renamed = re.compile(r".+_\d{8}-\d{2}-\d{2}-\d{2}-\d+\.bak$")
    to_rename = [p for p in all_backups
                 if p.is_file() and not already_renamed.match(p.name)]

    if not to_rename:
        print("ℹ️ Нет бэкапов для переименования.")
        return 0

    print(f"📦 Найдено {len(to_rename)} бэкапов для переименования:\n")

    # Сортируем по mtime, чтобы счётчики шли по порядку
    to_rename.sort(key=lambda p: p.stat().st_mtime)

    for old_path in to_rename:
        mtime = datetime.fromtimestamp(old_path.stat().st_mtime)
        date_str = mtime.strftime("%d%m%Y-%H-%M-%S")

        # Извлекаем оригинальное имя (без суффиксов)
        name = old_path.name
        match = re.match(r"^([^.]+\.[^.]+)(?:\..*)?$", name)
        orig_name = match.group(1) if match else name

        # Счётчик
        n = 1
        while True:
            new_name = f"{orig_name}_{date_str}-{n}.bak"
            new_path = old_path.parent / new_name
            if not new_path.exists():
                break
            n += 1

        old_path.rename(new_path)
        print(f"  {name:60} → {new_name}")

    print(f"\n✅ Переименовано {len(to_rename)} файлов.")
    return 0


class _Tee:
    """Дублирует вывод в консоль и в файл (для диагностики)."""
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)
            s.flush()

    def flush(self):
        for s in self.streams:
            s.flush()


def _diagnose_cli():
    """CLI: python3 constructor.py diagnose
    Полная диагностика Конструктора без GUI; результат — в консоль и в diag/."""
    dt = datetime.now().strftime("%d%m%Y-%H-%M-%S")
    diag_dir = Path("diag")
    diag_dir.mkdir(parents=True, exist_ok=True)
    output_file = diag_dir / f"diagnose_{dt}.txt"
    fh = open(output_file, "w", encoding="utf-8")
    old_stdout = sys.stdout
    sys.stdout = _Tee(sys.__stdout__, fh)
    try:
        _run_diagnostics()
    finally:
        fh.close()
        sys.stdout = old_stdout
    print(f"\n📄 Диагностика сохранена: {output_file.absolute()}")
    print("   Просто прикрепите файл в чат.")
    # Открываем папку diag/ через файловый менеджер
    try:
        subprocess.Popen(["xdg-open", str(diag_dir.absolute())],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("📂 Папка diag/ открыта в файловом менеджере")
    except Exception as e:
        print(f"⚠️ Не удалось открыть папку: {e}")
    return 0


def _sep(title):
    print(f"\n{'='*70}\n{title}\n{'='*70}")


def _run_diagnostics():
    # ---------- 1. DATA.JSON ----------
    _sep("1. DATA.JSON")
    data_path = Path("data.json")
    if not data_path.exists():
        print(f"❌ Файл не найден: {data_path}")
        return
    data = json.loads(data_path.read_text(encoding="utf-8"))
    editions = data.get("editions", [])
    print(f"✅ Редакций: {len(editions)}")
    for i, ed in enumerate(editions):
        print(f"   [{i}] {ed.get('label','?')[:60]} ({ed.get('date','?')})")

    # ---------- 2. EVENTS (база конструктора) ----------
    _sep("2. EVENTS (база конструктора)")
    app3_events = [e for e in EVENTS if e.get("source") == "app3"]
    table3_events = [e for e in EVENTS if e.get("source") == "table3" and not e.get("is_aggregate")]
    print(f"✅ app3: {len(app3_events)} мероприятий")
    print(f"✅ table3: {len(table3_events)} мероприятий")
    print(f"✅ Всего в EVENTS: {len(EVENTS)}")

    by_group = defaultdict(list)
    for e in app3_events:
        by_group[e.get("group", "?")].append(e)
    print("\nПо округам:")
    for g in sorted(by_group.keys()):
        total_2026 = sum(e.get("years", {}).get("2026", 0) for e in by_group[g])
        print(f"   Округ {g}: {len(by_group[g])} мероприятий, сумма 2026 = {total_2026:.1f}")

    # ---------- 3. СУММЫ ПО РЕДАКЦИЯМ ----------
    _sep("3. СУММЫ ПО РЕДАКЦИЯМ (год 2026)")
    print(f"{'Редакция':<45} {'Сумма меропр.':>15} {'1.1.3 факт':>15}")
    print("-" * 80)
    for i, ed in enumerate(editions):
        total = get_event_sum_at(2026, data, i)
        agg = {"id": "e_1_1_3", "is_aggregate": True}
        agg_val = get_event_value_at(agg, 2026, data, i)
        print(f"{ed.get('label','?')[:44]:<45} {total:>15,.1f} {agg_val:>15,.1f}".replace(",", " "))

    # ---------- 4. АУДИТ 1.1.3 ----------
    _sep("4. АУДИТ 1.1.3 (официально vs по мероприятиям)")
    for i, ed in enumerate(editions):
        if i == 0:
            continue
        official, computed, diff = check_aggregate_consistency(data, i, 2026)
        if official is None:
            continue
        status = "✅ OK" if abs(diff) < 0.1 else f"⚠ РАСХОЖДЕНИЕ {diff:+.1f}"
        print(f"   [{i}] {ed.get('label','?')[:40]:<40} официал={official:>8,.1f} факт={computed:>8,.1f} {status}".replace(",", " "))

    # ---------- 5. CHANGES.JSON ----------
    _sep("5. CHANGES.JSON (история Думы)")
    changes_path = Path("changes.json")
    if not changes_path.exists():
        print(f"⚠️ Файл не найден: {changes_path} (не было синхронизации)")
        return
    changes = json.loads(changes_path.read_text(encoding="utf-8"))
    timeline = changes.get("timeline", [])
    print(f"✅ Шагов в истории: {len(timeline)}")
    print(f"✅ Итог Думы: {changes.get('final_total', '?')} тыс. руб.")
    print(f"✅ Финальных items: {len(changes.get('final_items', []))}")
    for i, step in enumerate(timeline):
        kind = step.get("kind", "?")
        date = step.get("date", "?")
        num = step.get("number", "?")
        items_count = len(step.get("items", []))
        delta = ""
        if kind == "amendment":
            d = step.get("delta_total", 0)
            delta = f" (Δ {d:+.1f})".replace(",", " ")
        print(f"   [{i}] {date} №{num:<5} {kind:<10} items={items_count}{delta}")

    # ---------- 6. СРАВНЕНИЕ С ДУМОЙ ----------
    _sep("6. СРАВНЕНИЕ С ДУМОЙ (последнее решение)")
    if not timeline:
        print("⚠️ История пуста")
    else:
        last_step = timeline[-1]
        target_items = last_step.get("items", [])

        group_mapping = {"10": "1", "12": "2", "20": "3", "27": "4",
                         "31": "5", "33": "6", "МИО Галушко В.Ф.": "7"}
        duma_map = {}
        for item in target_items:
            if item.get("status") != "ok":
                continue
            dist = item.get("district", "").strip()
            g = group_mapping.get(dist)
            if not g:
                continue
            name = normalize_name(item.get("works", ""))
            amount_v = float(item.get("amount") or 0)
            duma_map[(g, name)] = amount_v

        print(f"Мероприятий в Думе: {len(duma_map)}")

        current_idx = len(editions) - 1
        app3 = [e for e in get_effective_events(data, current_idx) if e.get("source") == "app3"]
        print(f"Мероприятий в Конструкторе (редакция {current_idx}): {len(app3)}")

        found_in_duma = set()
        errors = []
        for ev in app3:
            g = ev.get("group")
            eff_name = get_effective_name(ev, data, current_idx)
            m = re.search(r'«(.*)»', eff_name)
            name = normalize_name(m.group(1) if m else eff_name)
            key_ = (g, name)

            val = get_event_value_at(ev, 2026, data, current_idx)

            if key_ in duma_map:
                found_in_duma.add(key_)
                expected = duma_map[key_]
                if abs(val - expected) > 0.01:
                    errors.append(("НЕВЕРНАЯ СУММА", eff_name[:60], val, expected))
            else:
                errors.append(("ЛИШНЕЕ", eff_name[:60], val, None))

        for key_, expected in duma_map.items():
            if key_ not in found_in_duma:
                g, name = key_
                errors.append(("НЕ ХВАТАЕТ В КОНСТРУКТОРЕ", f"[{g}] {name[:55]}", None, expected))

        print(f"\nРасхождений: {len(errors)}")
        if errors:
            for i, (etype, nm, cur, exp) in enumerate(errors[:30], 1):
                cur_s = f"{cur:>8,.1f}".replace(",", " ") if cur is not None else "    —"
                exp_s = f"{exp:>8,.1f}".replace(",", " ") if exp is not None else "    —"
                print(f"   [{i:2}] {etype:<28} {nm:<60} сейчас={cur_s} в Думе={exp_s}")
        else:
            print("   ✅ Расхождений не найдено")

    # ---------- 7. ПАПКА НАКАЗЫ ----------
    _sep("7. ПАПКА НАКАЗЫ")
    folder = Path("Наказы")
    if not folder.exists():
        print(f"❌ Папка не найдена: {folder}")
    else:
        files = list(folder.glob("*.htm*"))
        print(f"✅ HTML-файлов: {len(files)}")

    # ---------- 8. ui_settings.json ----------
    _sep("8. ui_settings.json")
    ui_path = Path("ui_settings.json")
    if ui_path.exists():
        try:
            ui = json.loads(ui_path.read_text(encoding="utf-8"))
            print(f"✅ Файл существует, ключей: {len(ui)}")
            for k, v in ui.items():
                if isinstance(v, list):
                    print(f"   {k}: {len(v)} значений")
                else:
                    print(f"   {k}: {v}")
        except Exception as e:
            print(f"⚠️ Ошибка чтения: {e}")
    else:
        print("⚠️ Файл не найден")

    _sep("КОНЕЦ ДИАГНОСТИКИ")


# ============================================================
# ТОЧКА ВХОДА — единый запуск всех модулей из одного файла:
#   python3 constructor.py                 — графический интерфейс (GUI)
#   python3 constructor.py tracker [scan|serve|open] — трекер изменений ТОС
#   python3 constructor.py duma file.htm [-o tos.json] [--csv tos.csv] — парсер Думы
#   python3 constructor.py diagnose        — диагностика без GUI (отчёт в diag/)
#   python3 constructor.py backup <файл...> | --all   — создание бэкапов
#   python3 constructor.py rename-backups  — переименование старых бэкапов
# ============================================================
def _cli():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "tracker":
        return _tracker_cli()
    if cmd == "duma":
        return _duma_main()
    if cmd == "diagnose":
        return _diagnose_cli()
    if cmd == "backup":
        return _backup_cli()
    if cmd == "rename-backups":
        return _rename_backups_cli()
    # без команды или с неизвестной командой — запускаем GUI
    return main()


if __name__ == "__main__":
    main()