import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_USERS = {
    int(uid.strip())
    for uid in os.getenv("ALLOWED_USERS", "").split(",")
    if uid.strip().isdigit()
}
_data_dir = Path(os.getenv("DATA_DIR", Path(__file__).parent))
_data_dir.mkdir(parents=True, exist_ok=True)
DATA_FILE = _data_dir / "progress.json"

# ─── Контент ────────────────────────────────────────────────────────────────

SECTIONS = {
    "spina": {
        "title": "🌿 Упражнения для спины",
        "videos": [
            ("FEELGOOD_GREEN_WEEK3_WORK6 — 21:15", "https://kinescope.io/202347824"),
            ("SPINA_WEEK2_DAY7 — 15:09",           "https://kinescope.io/200852251"),
            ("KROVAT2023_DASHA_BW3 — 6:51",        "https://kinescope.io/204992408"),
            ("#SEKTABOOTCAMP3 ОСАНКА (WEEK 3) — 8:14", "https://embed.new.video/uKWbpDkhZ4YVmENKRivNkA"),
        ],
    },
    "mtd": {
        "title": "✨ МТД комплексы",
        "videos": [
            ("evo_dno_1 — 8:04",     "https://kinescope.io/199726204"),
            ("evo_dno_3 — 6:57",     "https://kinescope.io/199726226"),
            ("evo_dno_4_new — 8:34", "https://kinescope.io/199726228"),
            ("evo_dno_5 — 6:22",     "https://kinescope.io/199726267"),
            ("evo_dno_6 — 5:03",     "https://kinescope.io/199726439"),
            ("evo_dno_7 — 10:11",    "https://kinescope.io/199726441"),
            ("evo_dno_8 — 7:02",     "https://kinescope.io/199726443"),
            ("evo_dno_9 — 6:38",     "https://kinescope.io/199726444"),
        ],
    },
}

# ─── Хранилище прогресса ─────────────────────────────────────────────────────

def load_data() -> dict:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {}

def save_data(data: dict):
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def get_user_data(data: dict, user_id: int) -> dict:
    key = str(user_id)
    if key not in data:
        data[key] = {}
    return data[key]

def get_video_state(user_data: dict, section: str, idx: int) -> tuple[bool, bool]:
    """Returns (done, starred)."""
    key = f"{section}_{idx}"
    entry = user_data.get(key, {})
    return entry.get("done", False), entry.get("starred", False)

def toggle(user_data: dict, section: str, idx: int, field: str):
    key = f"{section}_{idx}"
    if key not in user_data:
        user_data[key] = {}
    user_data[key][field] = not user_data[key].get(field, False)

# ─── Клавиатуры ─────────────────────────────────────────────────────────────

def main_menu_keyboard(user_data: dict) -> InlineKeyboardMarkup:
    rows = []
    for sec_id, sec in SECTIONS.items():
        videos = sec["videos"]
        done_count = sum(
            1 for i in range(len(videos))
            if get_video_state(user_data, sec_id, i)[0]
        )
        label = f"{sec['title']} ({done_count}/{len(videos)})"
        rows.append([InlineKeyboardButton(label, callback_data=f"section_{sec_id}")])

    starred_count = sum(
        1 for sec_id, sec in SECTIONS.items()
        for i in range(len(sec["videos"]))
        if get_video_state(user_data, sec_id, i)[1]
    )
    fav_label = f"⭐ Избранное ({starred_count})" if starred_count else "⭐ Избранное"
    rows.append([InlineKeyboardButton(fav_label, callback_data="section_favorites")])
    return InlineKeyboardMarkup(rows)

def favorites_keyboard(user_data: dict) -> InlineKeyboardMarkup:
    rows = []
    for sec_id, sec in SECTIONS.items():
        for i, (name, url) in enumerate(sec["videos"]):
            done, starred = get_video_state(user_data, sec_id, i)
            if starred:
                rows.append([
                    InlineKeyboardButton(f"▶️ {name}", url=url),
                    InlineKeyboardButton("✅" if done else "⬜", callback_data=f"toggle_done_{sec_id}_{i}"),
                    InlineKeyboardButton("⭐", callback_data=f"toggle_star_{sec_id}_{i}"),
                ])
    if not rows:
        rows.append([InlineKeyboardButton("Пока ничего нет 🙈", callback_data="noop")])
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)

def section_keyboard(section: str, user_data: dict) -> InlineKeyboardMarkup:
    videos = SECTIONS[section]["videos"]
    rows = []
    for i, (name, url) in enumerate(videos):
        done, starred = get_video_state(user_data, section, i)
        rows.append([
            InlineKeyboardButton(f"▶️ {name}", url=url),
            InlineKeyboardButton("✅" if done else "⬜", callback_data=f"toggle_done_{section}_{i}"),
            InlineKeyboardButton("⭐" if starred else "☆", callback_data=f"toggle_star_{section}_{i}"),
        ])
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)

# ─── Хендлеры ───────────────────────────────────────────────────────────────

def is_allowed(update: Update) -> bool:
    return update.effective_user.id in ALLOWED_USERS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        await update.message.reply_text("⛔ Доступ закрыт.")
        return
    data = load_data()
    user_data = get_user_data(data, update.effective_user.id)
    await update.message.reply_text(
        "Привет! Выбери раздел:",
        reply_markup=main_menu_keyboard(user_data),
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_allowed(update):
        await query.answer("⛔ Доступ закрыт.", show_alert=True)
        return
    await query.answer()

    cb = query.data
    user_id = query.from_user.id
    data = load_data()
    user_data = get_user_data(data, user_id)

    if cb == "noop":
        pass

    elif cb == "section_favorites":
        await query.edit_message_text(
            "⭐ Избранное:",
            reply_markup=favorites_keyboard(user_data),
        )

    elif cb.startswith("section_"):
        section = cb.removeprefix("section_")
        await query.edit_message_text(
            SECTIONS[section]["title"] + ":",
            reply_markup=section_keyboard(section, user_data),
        )

    elif cb.startswith("toggle_done_") or cb.startswith("toggle_star_"):
        if cb.startswith("toggle_done_"):
            rest = cb.removeprefix("toggle_done_")
            field = "done"
        else:
            rest = cb.removeprefix("toggle_star_")
            field = "starred"

        section, idx_str = rest.rsplit("_", 1)
        toggle(user_data, section, int(idx_str), field)
        save_data(data)

        current_text = query.message.text or ""
        if "Избранное" in current_text:
            await query.edit_message_reply_markup(reply_markup=favorites_keyboard(user_data))
        else:
            await query.edit_message_reply_markup(reply_markup=section_keyboard(section, user_data))

    elif cb == "back_main":
        await query.edit_message_text(
            "Выбери раздел:",
            reply_markup=main_menu_keyboard(user_data),
        )

# ─── Запуск ─────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    logger.info("Бот запущен")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    main()
