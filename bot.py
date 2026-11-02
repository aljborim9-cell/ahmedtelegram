"""
Telegram Bot Control Panel for A2 TV App.
Provides interactive management for Channels, Categories, Stream Links (m3u8, ts, js, php, json), APK Updates, Maintenance Mode, and Admins.
"""

import telebot
from telebot import types
import json
import time
import re
from config import BOT_TOKEN, ADMIN_ID, API_HOST, API_PORT, PUBLIC_URL, APP_PACKAGE, logger
from database import db

# Safe initialization for Bot
BOT_INITIALIZED = False
if BOT_TOKEN and ":" in BOT_TOKEN and BOT_TOKEN != "YOUR_TELEGRAM_BOT_TOKEN_HERE":
    try:
        bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
        BOT_INITIALIZED = True
    except Exception as e:
        logger.error("Failed to initialize TeleBot: %s", e)
        bot = telebot.TeleBot("123456789:AAFakeTokenForValidationPlaceholderUntilReal", parse_mode="HTML")
else:
    bot = telebot.TeleBot("123456789:AAFakeTokenForValidationPlaceholderUntilReal", parse_mode="HTML")

# User States for multi-step wizards
user_states = {}

def get_user_id(message_or_query):
    if hasattr(message_or_query, "from_user") and message_or_query.from_user:
        return message_or_query.from_user.id
    return message_or_query.chat.id

def check_admin(user_id, permission=None):
    if not db.is_admin(user_id):
        logger.warning("Access denied: user %s is not an admin", user_id)
        return False
    if permission and not db.has_permission(user_id, permission):
        logger.warning("Permission denied: user %s lacks '%s' permission", user_id, permission)
        return False
    return True

# ----------------- Keyboard Generators -----------------

def main_menu_keyboard(user_id):
    kb = types.InlineKeyboardMarkup(row_width=2)
    b_search = types.InlineKeyboardButton("🔍 بحث عن قناة", callback_data="ch_search_prompt")
    b_add_ch = types.InlineKeyboardButton("➕ إضافة قنوات (API وقسم)", callback_data="ch_add_unified")
    
    b_browse_cat = types.InlineKeyboardButton("📂 تصفح حسب الأقسام", callback_data="ch_browse_by_cat")
    b_categories = types.InlineKeyboardButton("🗂️ إدارة الأقسام", callback_data="cat_list")
    
    b_channels = types.InlineKeyboardButton("📺 كل القنوات", callback_data="ch_list_0")
    b_links = types.InlineKeyboardButton("🔗 إضافة روابط سريعة", callback_data="ch_universal_link")

    b_apis = types.InlineKeyboardButton("🌐 سيرفرات API", callback_data="menu_apis")
    b_export = types.InlineKeyboardButton("💾 تصدير ونسخ احتياطي", callback_data="ch_export_menu")
    
    b_maint = types.InlineKeyboardButton("🛠️ وضع الصيانة", callback_data="menu_maint")
    b_updates = types.InlineKeyboardButton("🔄 تحديث التطبيق APK", callback_data="menu_updates")
    
    b_stats = types.InlineKeyboardButton("📊 إحصائيات النظام", callback_data="ch_stats_view")
    b_admins = types.InlineKeyboardButton("👥 إدارة المشرفين", callback_data="menu_admins")
    
    kb.row(b_search, b_add_ch)
    kb.row(b_browse_cat, b_categories)
    kb.row(b_channels, b_links)
    kb.row(b_apis, b_export)
    kb.row(b_maint, b_updates)
    kb.row(b_stats, b_admins)
    return kb

def channels_menu_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    b_search = types.InlineKeyboardButton("🔍 بحث عن قناة", callback_data="ch_search_prompt")
    b_browse_cat = types.InlineKeyboardButton("📂 تصفح حسب الأقسام", callback_data="ch_browse_by_cat")

    b_add_ch = types.InlineKeyboardButton("➕ إضافة قنوات (API وقسم)", callback_data="ch_add_unified")
    b_links = types.InlineKeyboardButton("🔗 إضافة روابط قنوات بكل الصيغ", callback_data="ch_universal_link")
    
    b_list_ch = types.InlineKeyboardButton("📺 عرض وتعديل كل القنوات", callback_data="ch_list_0")
    b_list_cat = types.InlineKeyboardButton("🗂️ عرض وتعديل الأقسام", callback_data="cat_list")
    
    b_add_cat = types.InlineKeyboardButton("📁 إضافة قسم جديد", callback_data="cat_add")
    b_php = types.InlineKeyboardButton("🌐 استيراد PHP API JSON", callback_data="ch_import_php")

    b_export = types.InlineKeyboardButton("💾 تصدير M3U / نسخ احتياطي", callback_data="ch_export_menu")
    b_stats = types.InlineKeyboardButton("📊 إحصائيات القنوات والأقسام", callback_data="ch_stats_view")

    b_del_all = types.InlineKeyboardButton("🗑️ تفريغ وحذف جميع القنوات", callback_data="ch_del_all_confirm")
    b_back = types.InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")
    
    kb.row(b_search, b_browse_cat)
    kb.row(b_add_ch, b_links)
    kb.row(b_list_ch, b_list_cat)
    kb.row(b_add_cat, b_php)
    kb.row(b_export, b_stats)
    kb.add(b_del_all)
    kb.add(b_back)
    return kb

def apis_menu_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    b_add = types.InlineKeyboardButton("➕ إضافة سيرفر API جديد", callback_data="api_add")
    b_list = types.InlineKeyboardButton("📋 قائمة وتعديل السيرفرات", callback_data="api_list")
    b_sync_all = types.InlineKeyboardButton("🔄 مزامنة واستيراد جميع السيرفرات", callback_data="api_sync_all")
    b_back = types.InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")
    kb.row(b_add, b_list)
    kb.add(b_sync_all)
    kb.add(b_back)
    return kb

def category_selection_keyboard(action_prefix="cat_pick_"):
    kb = types.InlineKeyboardMarkup(row_width=2)
    cats = db.get_categories()
    if cats:
        for c in cats:
            icon = c.get("icon", "📁")
            name = c.get("name", c["id"])
            kb.add(types.InlineKeyboardButton(f"{icon} {name}", callback_data=f"{action_prefix}{c['id']}"))
    kb.add(types.InlineKeyboardButton("➕ إنشاء قسم جديد واختياره", callback_data="cat_create_and_select"))
    kb.add(types.InlineKeyboardButton("❌ إلغاء العملية", callback_data="cancel_action"))
    return kb

def back_to_main_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu"))
    return kb

def cancel_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("❌ إلغاء العملية", callback_data="cancel_action"))
    return kb

def updates_menu_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    up = db.get_app_update()
    status_text = "🟢 التحديث مفعّل" if up.get("enabled") else "🔴 التحديث معطّل"
    force_text = "🔒 إجباري: نعم" if up.get("is_force") else "🔓 إجباري: لا"

    b_toggle = types.InlineKeyboardButton(status_text, callback_data="up_toggle")
    b_force = types.InlineKeyboardButton(force_text, callback_data="up_toggle_force")
    b_set = types.InlineKeyboardButton("📦 تعيين رابط وبيانات تحديث جديد", callback_data="up_new")
    b_back = types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")
    
    kb.add(b_toggle, b_force)
    kb.add(b_set)
    kb.add(b_back)
    return kb

def maintenance_menu_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    m = db.get_maintenance()
    status_btn = types.InlineKeyboardButton(
        "🟢 الصيانة قيد التشغيل (إيقاف)" if m.get("enabled") else "🔴 الصيانة متوقفة (تفعيل)",
        callback_data="maint_toggle"
    )
    b_msg = types.InlineKeyboardButton("✏️ تعديل رسالة الصيانة", callback_data="maint_msg")
    b_back = types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")
    kb.add(status_btn)
    kb.add(b_msg)
    kb.add(b_back)
    return kb

def admins_menu_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    b1 = types.InlineKeyboardButton("➕ إضافة أدمن جديد", callback_data="admin_add")
    b2 = types.InlineKeyboardButton("📋 قائمة الأدمن والصلاحيات", callback_data="admin_list")
    b_back = types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")
    kb.add(b1, b2)
    kb.add(b_back)
    return kb

# ----------------- Start & Help -----------------

@bot.message_handler(commands=["start", "admin", "panel"])
def handle_start(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "المستخدم"

    if ADMIN_ID and user_id == ADMIN_ID:
        if not db.is_admin(user_id):
            db.add_admin(user_id, f"{user_name} (الرئيسي)", ["all"])

    if not check_admin(user_id):
        text = (
            f"مرحباً بك <b>{user_name}</b> في بوت التحكم بتطبيق <b>A2 TV</b> 📺\n\n"
            f"ℹ️ آيدي حسابك: <code>{user_id}</code>\n\n"
            f"⚠️ عذراً، لا تمتلك صلاحيات الأدمن للوصول إلى لوحة التحكم.\n"
            f"إذا كنت المدير، يرجى تعيين هذا الآيدي في ملف <code>.env</code> تحت <code>ADMIN_ID</code>."
        )
        bot.reply_to(message, text)
        return

    user_states.pop(user_id, None)

    welcome_text = (
        f"👑 مرحباً بك يا <b>{user_name}</b> في <b>لوحة تحكم تطبيق A2 TV</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"يمكنك إضافة وإدارة القنوات بجميع الصيغ (m3u8, ts, js, php, json)، الأقسام، التحديثات، ووضع الصيانة:\n"
    )
    bot.reply_to(message, welcome_text, reply_markup=main_menu_keyboard(user_id))

@bot.message_handler(commands=["id"])
def handle_id(message):
    bot.reply_to(message, f"🆔 آيدي حسابك في تيليجرام هو:\n<code>{message.from_user.id}</code>")

# ----------------- Callback Query Router -----------------

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id

    if not check_admin(user_id):
        bot.answer_callback_query(call.id, "⚠️ ليس لديك صلاحية أدمن!", show_alert=True)
        return

    data = call.data

    # Return to main menu
    if data == "main_menu":
        user_states.pop(user_id, None)
        text = (
            "👑 <b>لوحة التحكم الرئيسية لتطبيق A2 TV</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "اختر الإجراء أو القسم المطلوب:"
        )
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=main_menu_keyboard(user_id))
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=main_menu_keyboard(user_id))
        bot.answer_callback_query(call.id)
        return

    # Cancel ongoing action
    if data == "cancel_action":
        user_states.pop(user_id, None)
        bot.answer_callback_query(call.id, "تم إلغاء العملية")
        try:
            bot.edit_message_text("❌ تم إلغاء العملية والعودة للقائمة الرئيسية.", call.message.chat.id, call.message.message_id, reply_markup=main_menu_keyboard(user_id))
        except Exception:
            bot.send_message(call.message.chat.id, "❌ تم إلغاء العملية والعودة للقائمة الرئيسية.", reply_markup=main_menu_keyboard(user_id))
        return

    # 1. Universal Stream Link Wizard (m3u8, ts, js, php, json)
    if data == "ch_universal_link":
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ لا تملك صلاحية إدارة القنوات!", show_alert=True)
            return
        user_states[user_id] = {"action": "wait_universal_link", "data": {}}
        text = (
            "🔗 <b>إضافة واستيراد روابط القنوات بكل الصيغ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "يدعم النظام تشغيل واستيراد جميع أنواع الروابط والصيغ:\n"
            "• <b>m3u8</b> (روابط بث مباشر HLS فائقة السرعة)\n"
            "• <b>ts</b> (سيرفرات وبث MPEG-TS المباشر)\n"
            "• <b>php</b> (روابط وسيرفرات الأسطورة مثل <code>main.php?id=...</code>)\n"
            "• <b>js</b> (روابط وبث المشغلات البرمجية)\n"
            "• <b>json</b> (واجهات API وقوائم القنوات بصيغة JSON)\n"
            "• <b>m3u</b> (ملفات وقوائم تشغيل القنوات)\n\n"
            "أرسل الآن الرابط أو الصق كود JSON / M3U مباشرة:"
        )
        bot.send_message(call.message.chat.id, text, reply_markup=cancel_keyboard())
        bot.answer_callback_query(call.id)
        return

    # Unified Add Channel Flow (Pick API -> Pick Category -> Enter Stream)
    if data == "ch_add_unified":
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك بإدارة القنوات!", show_alert=True)
            return
        apis = db.get_channel_apis()
        kb = types.InlineKeyboardMarkup(row_width=1)
        for a in apis:
            kb.add(types.InlineKeyboardButton(f"🌐 {a.get('name')} [{a.get('type', 'api').upper()}]", callback_data=f"ch_uni_api_{a['id']}"))
        kb.add(types.InlineKeyboardButton("📡 قنوات مباشرة بدون سيرفر API", callback_data="ch_uni_api_direct"))
        kb.add(types.InlineKeyboardButton("➕ إضافة سيرفر API جديد", callback_data="api_add"))
        kb.add(types.InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu"))

        text = (
            "➕ <b>إضافة قنوات إلى التطبيق</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "<b>الخطوة 1 من 3:</b> اختر <b>سيرفر الـ API</b> الذي ترغب بإضافة القنوات إليه:\n"
            "<i>(أو اختر «قنوات مباشرة بدون سيرفر API» لإضافة روابط حرة)</i>"
        )
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("ch_uni_api_"):
        api_raw = data[len("ch_uni_api_"):]
        if api_raw == "direct":
            api_id = None
            api_name = "مباشر بدون API"
            cats = db.get_categories()
        else:
            api_id = api_raw
            api_obj = db.get_channel_api(api_id)
            api_name = api_obj.get("name", "سيرفر API") if api_obj else "سيرفر API"
            cats = db.get_categories_for_api(api_id)
            if not cats:
                cats = db.get_categories()

        user_states[user_id] = {
            "action": "wait_uni_pick_cat",
            "data": {
                "api_id": api_id,
                "api_name": api_name
            }
        }

        kb = types.InlineKeyboardMarkup(row_width=2)
        for c in cats:
            icon = c.get("icon", "📁")
            c_name = c.get("name", c.get("id"))
            ch_cnt = len(db.get_channels(c["id"]))
            kb.add(types.InlineKeyboardButton(f"{icon} {c_name} ({ch_cnt})", callback_data=f"ch_uni_cat_{c['id']}"))
        
        target_api_key = api_id if api_id else "direct"
        kb.add(types.InlineKeyboardButton("➕ إنشاء قسم جديد واختياره", callback_data=f"ch_uni_newcat_{target_api_key}"))
        kb.add(types.InlineKeyboardButton("🔙 رجوع لاختيار الـ API", callback_data="ch_add_unified"))

        text = (
            f"➕ <b>إضافة قنوات جديدة</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🌐 الـ API المحدد: <b>{api_name}</b>\n\n"
            f"<b>الخطوة 2 من 3:</b> اختر <b>القسم</b> الذي تريد إضافة القناة إليه:"
        )
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("ch_uni_cat_"):
        cat_id = data[len("ch_uni_cat_"):]
        cat = db.get_category(cat_id)
        cat_name = cat.get("name", cat_id) if cat else cat_id

        state = user_states.get(user_id, {})
        d = state.get("data", {})
        api_id = d.get("api_id")
        api_name = d.get("api_name", "مباشر")

        user_states[user_id] = {
            "action": "wait_uni_channel_input",
            "data": {
                "api_id": api_id,
                "api_name": api_name,
                "cat_id": cat_id,
                "cat_name": cat_name
            }
        }

        text = (
            f"📺 <b>إضافة قناة جديدة</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🌐 الـ API: <b>{api_name}</b>\n"
            f"📁 القسم: <b>{cat_name}</b>\n\n"
            f"<b>الخطوة 3 من 3:</b> أرسل الآن بيانات القناة أو رابط البث:\n\n"
            f"🔹 <b>صيغة سريعة بسطر واحد:</b>\n"
            f"<code>اسم القناة | رابط البث | الجودة</code>\n"
            f"مثال:\n"
            f"<code>beIN Sports 1 | https://example.com/live.m3u8 | FHD</code>\n\n"
            f"🔹 <b>أو أرسل رابط البث فقط</b> (m3u8, ts, js, php, mpd)\n\n"
            f"🔹 <b>أو الصق كود JSON</b> لقناة أو قائمة قنوات\n\n"
            f"✨ <b>ميزة الجودات التلقائية:</b> إذا كانت القناة موجودة مسبقاً بنفس الاسم ولديك جودة جديدة (مثل 4K أو SD)، سيتم دمجها تلقائياً داخل القناة كجودة إضافية دون تكرار القناة في التطبيق!"
        )
        bot.send_message(call.message.chat.id, text, reply_markup=cancel_keyboard())
        bot.answer_callback_query(call.id)
        return

    if data.startswith("ch_uni_newcat_"):
        api_param = data[len("ch_uni_newcat_"):]
        api_id = None if api_param == "direct" else api_param
        api_name = "مباشر"
        if api_id:
            api_obj = db.get_channel_api(api_id)
            if api_obj: api_name = api_obj.get("name", "سيرفر API")

        user_states[user_id] = {
            "action": "wait_uni_newcat_name",
            "data": {
                "api_id": api_id,
                "api_name": api_name
            }
        }
        text = (
            f"📁 <b>إنشاء قسم جديد تابع لـ: {api_name}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"أرسل الآن <b>اسم القسم الجديد</b>:\n"
            f"(مثال: <code>⚽ قنوات رياضية VIP</code> أو <code>🎬 مسلسلات</code>):"
        )
        bot.send_message(call.message.chat.id, text, reply_markup=cancel_keyboard())
        bot.answer_callback_query(call.id)
        return

    # 2. Add Channel in Any Category (Pick Category first)
    if data == "ch_add_select_cat":
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        cats = db.get_categories()
        text = (
            "➕ <b>إضافة قناة في أي قسم</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "الخطوة 1 من 3: اختر <b>القسم</b> الذي تريد إضافة القناة إليه، أو اضغط إنشاء قسم جديد:"
        )
        bot.send_message(call.message.chat.id, text, reply_markup=category_selection_keyboard("cat_pick_"))
        bot.answer_callback_query(call.id)
        return

    # Category Selected for Adding Channel
    if data.startswith("cat_pick_"):
        cat_id = data[len("cat_pick_"):]
        cats = db.get_categories()
        cat = next((c for c in cats if c["id"] == cat_id), None)
        cat_name = cat["name"] if cat else cat_id

        user_states[user_id] = {
            "action": "wait_picked_cat_ch_name",
            "data": {"category": cat_id, "categoryName": cat_name}
        }
        text = (
            f"📁 تم اختيار القسم: <b>{cat_name}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"الخطوة 2 من 3: أرسل الآن <b>اسم القناة</b> (مثال: <code>beIN Sports 1 HD</code> أو <code>سبورت 2</code>):"
        )
        bot.send_message(call.message.chat.id, text, reply_markup=cancel_keyboard())
        bot.answer_callback_query(call.id)
        return

    # Create category on the fly and select it
    if data == "cat_create_and_select":
        user_states[user_id] = {"action": "wait_cat_name_for_new_channel", "data": {}}
        text = (
            "📁 <b>إنشاء قسم جديد واختياره</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "أرسل اسم القسم الجديد (مثال: <code>⚽ قنوات رياضية</code> أو <code>🎬 أفلام ومسلسلات</code>):"
        )
        bot.send_message(call.message.chat.id, text, reply_markup=cancel_keyboard())
        bot.answer_callback_query(call.id)
        return

    # Category Selected for Universal Link Wizard
    if data.startswith("univ_cat_"):
        cat_id = data[len("univ_cat_"):]
        state = user_states.get(user_id)
        if not state or not state.get("data"):
            bot.answer_callback_query(call.id, "انتهت صلاحية الجلسة، يرجى إعادة المحاولة.", show_alert=True)
            return

        cats = db.get_categories()
        cat = next((c for c in cats if c["id"] == cat_id), None)
        cat_name = cat["name"] if cat else cat_id

        d = state["data"]
        ch = db.add_single_channel(
            name=d.get("name", "قناة بث مباشر"),
            url=d.get("url", ""),
            category_id=cat_id,
            category_name=cat_name,
            logo=d.get("logo", "📺"),
            quality=d.get("quality", "FHD")
        )
        user_states.pop(user_id, None)
        success_text = (
            f"🎉 <b>تمت إضافة القناة بنجاح في التطبيق!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📺 القناة: <b>{ch['name']}</b>\n"
            f"📁 القسم: <b>{ch['categoryName']}</b>\n"
            f"🔗 الرابط: <code>{ch['url']}</code>\n"
            f"✨ الجودة: <b>{ch['quality']}</b>\n\n"
            f"تظهر القناة فوراً داخل تطبيق A2 TV في قسم «{ch['categoryName']}»."
        )
        bot.send_message(call.message.chat.id, success_text, reply_markup=channels_menu_keyboard())
        bot.answer_callback_query(call.id)
        return

    # 3. Add Category Wizard
    if data == "cat_add":
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        user_states[user_id] = {"action": "wait_cat_name_simple", "data": {}}
        text = (
            "📁 <b>إضافة قسم جديد للقنوات</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "أرسل الآن <b>اسم القسم</b> الجديد:\n"
            "(مثال: <code>⚽ قنوات رياضية</code> أو <code>🎬 أفلام أجنبية</code> أو <code>🔴 قنوات إخبارية</code> أو <code>🕋 قنوات إسلامية</code>):"
        )
        bot.send_message(call.message.chat.id, text, reply_markup=cancel_keyboard())
        bot.answer_callback_query(call.id)
        return

    # Channels Menu
    if data == "menu_channels":
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ لا تملك صلاحية إدارة القنوات!", show_alert=True)
            return
        ch_count = len(db.get_channels())
        cat_count = len(db.get_categories())
        text = (
            f"📺 <b>إدارة القنوات والأقسام</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 عدد القنوات الحالية في التطبيق: <b>{ch_count}</b> قناة\n"
            f"📁 عدد الأقسام الحالية: <b>{cat_count}</b> قسم\n\n"
            f"<i>تنبيه: تم مسح القنوات الجاهزة وتعمل القنوات حصرياً من البوت.</i>\n\n"
            f"اختر الإجراء المطلوب:"
        )
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=channels_menu_keyboard())
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=channels_menu_keyboard())
        bot.answer_callback_query(call.id)
        return

    # Clear All Channels Confirmation
    if data == "ch_del_all_confirm":
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        kb = types.InlineKeyboardMarkup(row_width=2)
        b_yes = types.InlineKeyboardButton("🗑️ نعم، احذف الكل", callback_data="ch_del_all_do")
        b_no = types.InlineKeyboardButton("❌ تراجع", callback_data="menu_channels")
        kb.add(b_yes, b_no)
        text = (
            "⚠️ <b>تأكيد تفريغ وحذف جميع القنوات</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "هل أنت متأكد من رغبتك في حذف جميع القنوات والأقسام من التطبيق بالكامل؟\n\n"
            "عند الحذف سيصبح التطبيق خالياً تماماً حتى تقوم بإضافة قنوات جديدة."
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    # Clear All Channels Execution
    if data == "ch_del_all_do":
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        count = db.delete_all_channels()
        bot.answer_callback_query(call.id, f"تم مسح {count} قناة بنجاح", show_alert=True)
        text = (
            f"🗑️ <b>تم مسح وتفريغ جميع القنوات الجاهزة والمسجلة بنجاح!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"تم حذف <b>{count}</b> قناة.\n"
            f"التطبيق الآن خالٍ تماماً وجاهز لإضافة قنواتك الخاصة عبر زر «إضافة روابط قنوات»."
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=channels_menu_keyboard())
        return

    # Channel List & Pagination
    if data.startswith("ch_list_"):
        page = int(data.split("_")[2])
        channels = db.get_channels()
        if len(channels) == 0:
            text = "📋 <b>لا توجد قنوات حالياً في التطبيق.</b>\nأضف قنوات عبر زر «إضافة روابط قنوات» أو «إضافة قناة في أي قسم»."
            try:
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=channels_menu_keyboard())
            except Exception:
                bot.send_message(call.message.chat.id, text, reply_markup=channels_menu_keyboard())
            bot.answer_callback_query(call.id)
            return

        per_page = 6
        total_pages = (len(channels) + per_page - 1) // per_page
        if total_pages == 0: total_pages = 1
        page = max(0, min(page, total_pages - 1))

        start = page * per_page
        end = start + per_page
        slice_ch = channels[start:end]

        kb = types.InlineKeyboardMarkup(row_width=1)
        for ch in slice_ch:
            name_label = ch.get('name', 'قناة')
            cat_label = ch.get('categoryName', 'عام')
            qual_label = ch.get('quality', 'FHD')
            kb.add(types.InlineKeyboardButton(f"📺 {name_label} | {cat_label} [{qual_label}]", callback_data=f"ch_view_{ch['id']}"))

        nav_row = []
        if page > 0:
            nav_row.append(types.InlineKeyboardButton("⬅️ السابق", callback_data=f"ch_list_{page-1}"))
        nav_row.append(types.InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_row.append(types.InlineKeyboardButton("التالي ➡️", callback_data=f"ch_list_{page+1}"))
        if nav_row:
            kb.row(*nav_row)

        kb.add(types.InlineKeyboardButton("🔙 رجوع لقسم القنوات", callback_data="menu_channels"))
        text = f"📋 <b>قائمة القنوات المسجلة ({len(channels)} قناة)</b>\nاضغط على أي قناة لعرض تفاصيلها أو تعديلها أو حذفها:"
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    # View Channel Details
    if data.startswith("ch_view_"):
        ch_id = data[len("ch_view_"):]
        ch = db.get_channel(ch_id)
        if not ch:
            bot.answer_callback_query(call.id, "⚠️ القناة غير موجودة أو تم حذفها", show_alert=True)
            call.data = "ch_list_0"
            handle_callback(call)
            return

        is_disabled = ch.get("disabled", False)
        status_text = "🔴 معطلة ومخفية بالتطبيق" if is_disabled else "🟢 نشطة ومعروضة بالتطبيق"
        logo_str = ch.get("logo") or "📺"

        text = (
            f"📺 <b>تفاصيل القناة: {ch.get('name')}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 المعرف: <code>{ch.get('id')}</code>\n"
            f"📁 القسم: <b>{ch.get('categoryName', 'عام')}</b>\n"
            f"🔘 الحالة: <b>{status_text}</b>\n"
            f"✨ الجودة الأساسية: <b>{ch.get('quality', 'FHD')}</b>\n"
            f"🖼️ الشعار: <b>{logo_str}</b>\n"
            f"🔗 رابط البث المباشر:\n<code>{ch.get('url')}</code>\n"
        )

        servers = ch.get("servers", [])
        if servers:
            text += f"\n🌐 <b>السيرفرات والجودات المتاحة ({len(servers)}):</b>\n"
            for i, srv in enumerate(servers, 1):
                s_name = srv.get("name", f"سيرفر {i}")
                s_q = srv.get("quality", "HD")
                s_url = srv.get("url", "")
                text += f"{i}. <b>{s_name} [{s_q}]</b>: <code>{s_url[:45]}...</code>\n"

        if ch.get("referer"):
            text += f"🌐 Referer: <code>{ch.get('referer')}</code>\n"
        if ch.get("useragent"):
            text += f"📱 User-Agent: <code>{ch.get('useragent')[:30]}...</code>\n"
        if ch.get("key"):
            text += f"🔑 DRM Key: <code>{ch.get('key')}</code>\n"

        kb = types.InlineKeyboardMarkup(row_width=2)
        b_ping = types.InlineKeyboardButton("⚡ فحص الرابط الآن", callback_data=f"ch_ping_{ch_id}")
        b_toggle = types.InlineKeyboardButton("🟢 تفعيل" if is_disabled else "🔴 تعطيل", callback_data=f"ch_toggledis_{ch_id}")
        
        b_edname = types.InlineKeyboardButton("✏️ تعديل الاسم", callback_data=f"ch_edname_{ch_id}")
        b_edurl = types.InlineKeyboardButton("🔗 تعديل الرابط", callback_data=f"ch_edurl_{ch_id}")
        
        b_edcat = types.InlineKeyboardButton("📁 تغيير القسم", callback_data=f"ch_edcat_{ch_id}")
        b_edqual = types.InlineKeyboardButton("✨ تغيير الجودة", callback_data=f"ch_edqual_{ch_id}")
        
        b_srvs = types.InlineKeyboardButton(f"🌐 إدارة الجودات ({len(servers)})", callback_data=f"ch_srvs_{ch_id}")
        b_logo = types.InlineKeyboardButton("🖼️ تعديل الشعار", callback_data=f"ch_edlogo_{ch_id}")

        b_headers = types.InlineKeyboardButton("⚙️ تعديل الرؤوس (Headers)", callback_data=f"ch_edheaders_{ch_id}")
        b_del = types.InlineKeyboardButton("🗑️ حذف القناة", callback_data=f"ch_del_{ch_id}")
        
        b_back = types.InlineKeyboardButton("🔙 رجوع لقائمة القنوات", callback_data="ch_list_0")

        kb.row(b_ping, b_toggle)
        kb.row(b_edname, b_edurl)
        kb.row(b_edcat, b_edqual)
        kb.row(b_srvs, b_logo)
        kb.row(b_headers, b_del)
        kb.add(b_back)

        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    # Stream Health Check (Ping)
    if data.startswith("ch_ping_"):
        ch_id = data[len("ch_ping_"):]
        ch = db.get_channel(ch_id)
        if not ch:
            bot.answer_callback_query(call.id, "⚠️ القناة غير موجودة", show_alert=True)
            return
        bot.answer_callback_query(call.id, "⏳ جاري فحص استجابة سيرفر البث...")
        url = ch.get("url", "")
        res = db.test_stream_url(url, referer=ch.get("referer", ""), useragent=ch.get("useragent", ""))
        alert_msg = res.get("message", "تم الفحص")
        bot.send_message(
            call.message.chat.id,
            f"📡 <b>نتيجة فحص سيرفر البث: {ch.get('name')}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 الرابط: <code>{url}</code>\n"
            f"📊 الحالة: <b>{alert_msg}</b>\n"
            f"⚡ نوع المحتوى: <code>{res.get('content_type', 'unknown')}</code>\n"
            f"⏱️ زمن الاستجابة: <b>{res.get('latency', 0)} ms</b>",
            reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 رجوع لتفاصيل القناة", callback_data=f"ch_view_{ch_id}"))
        )
        return

    # Toggle Channel Active / Disabled
    if data.startswith("ch_toggledis_"):
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        ch_id = data[len("ch_toggledis_"):]
        success, is_dis = db.toggle_channel_disabled(ch_id)
        if success:
            msg = "🔴 تم تعطيل القناة مؤقتاً في التطبيق" if is_dis else "🟢 تم تفعيل القناة لتظهر في التطبيق فوراً"
            bot.answer_callback_query(call.id, msg, show_alert=True)
        else:
            bot.answer_callback_query(call.id, f"❌ {is_dis}", show_alert=True)
        call.data = f"ch_view_{ch_id}"
        handle_callback(call)
        return

    # Channel Edit Logo
    if data.startswith("ch_edlogo_"):
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        ch_id = data[len("ch_edlogo_"):]
        ch = db.get_channel(ch_id)
        if not ch:
            bot.answer_callback_query(call.id, "⚠️ القناة غير موجودة", show_alert=True)
            return
        user_states[user_id] = {"action": "wait_ch_edlogo", "data": {"id": ch_id, "name": ch.get("name")}}
        text = (
            f"🖼️ <b>تعديل شعار/أيقونة القناة: {ch.get('name')}</b>\n"
            f"الشعار الحالي: <b>{ch.get('logo', '📺')}</b>\n\n"
            f"أرسل الآن <b>رابط صورة الشعار (URL)</b> أو أرسل رمز إيموجي (مثل ⚽ أو 📺):"
        )
        bot.send_message(call.message.chat.id, text, reply_markup=cancel_keyboard())
        bot.answer_callback_query(call.id)
        return

    # Channel Edit Headers
    if data.startswith("ch_edheaders_"):
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        ch_id = data[len("ch_edheaders_"):]
        ch = db.get_channel(ch_id)
        if not ch:
            bot.answer_callback_query(call.id, "⚠️ القناة غير موجودة", show_alert=True)
            return
        user_states[user_id] = {"action": "wait_ch_edheaders", "data": {"id": ch_id, "name": ch.get("name")}}
        text = (
            f"⚙️ <b>تعديل رؤوس البث (Headers & Referer) للقناة: {ch.get('name')}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"القيم الحالية:\n"
            f"• Referer: <code>{ch.get('referer') or 'بدون'}</code>\n"
            f"• User-Agent: <code>{ch.get('useragent') or 'تلقائي'}</code>\n\n"
            f"أرسل الآن الرؤوس بأحد الصيغ:\n"
            f"1. أرسل رابط Referer مباشرة: <code>https://example.com/</code>\n"
            f"2. أو بالتنسيق المتقدم:\n<code>referer: https://... | useragent: Mozilla/...</code>"
        )
        bot.send_message(call.message.chat.id, text, reply_markup=cancel_keyboard())
        bot.answer_callback_query(call.id)
        return

    # Channel Manage Multi-Quality Servers
    if data.startswith("ch_srvs_"):
        ch_id = data[len("ch_srvs_"):]
        ch = db.get_channel(ch_id)
        if not ch:
            bot.answer_callback_query(call.id, "⚠️ القناة غير موجودة", show_alert=True)
            return
        servers = ch.get("servers", [])
        text = (
            f"🌐 <b>إدارة السيرفرات والجودات للقناة: {ch.get('name')}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"إجمالي السيرفرات المضافة: <b>{len(servers)}</b>\n\n"
            f"تتيح هذه الميزة ظهور نافذة اختيار الجودة في التطبيق تلقائياً (Smart Quality Selector).\n"
            f"يمكنك حذف سيرفر أو إضافة جودة جديدة:"
        )
        kb = types.InlineKeyboardMarkup(row_width=1)
        for idx, srv in enumerate(servers):
            kb.add(types.InlineKeyboardButton(f"🗑️ حذف {srv.get('name', 'سيرفر')} [{srv.get('quality', 'HD')}]", callback_data=f"ch_delsrv_{ch_id}_{idx}"))
        kb.add(types.InlineKeyboardButton("➕ إضافة جودة / سيرفر جديد لهذه القناة", callback_data=f"ch_addsrv_{ch_id}"))
        kb.add(types.InlineKeyboardButton("🔙 رجوع لتفاصيل القناة", callback_data=f"ch_view_{ch_id}"))
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    # Delete Server from Channel
    if data.startswith("ch_delsrv_"):
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        parts = data[len("ch_delsrv_"):].rsplit("_", 1)
        if len(parts) == 2:
            ch_id, srv_idx_str = parts[0], parts[1]
            try:
                srv_idx = int(srv_idx_str)
                success, res = db.delete_channel_server(ch_id, srv_idx)
                if success:
                    bot.answer_callback_query(call.id, "✅ تم حذف السيرفر بنجاح", show_alert=True)
                else:
                    bot.answer_callback_query(call.id, f"❌ {res}", show_alert=True)
            except ValueError:
                pass
            call.data = f"ch_srvs_{ch_id}"
            handle_callback(call)
            return

    # Add Quality / Server to Channel - Step 1: Pick Quality
    if data.startswith("ch_addsrv_"):
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        ch_id = data[len("ch_addsrv_"):]
        ch = db.get_channel(ch_id)
        if not ch:
            bot.answer_callback_query(call.id, "⚠️ القناة غير موجودة", show_alert=True)
            return
        kb = types.InlineKeyboardMarkup(row_width=2)
        for q in ["4K", "FHD", "HD", "SD", "LOW"]:
            kb.add(types.InlineKeyboardButton(f"✨ جودة {q}", callback_data=f"ch_setaddsrv_q_{ch_id}_{q}"))
        kb.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data=f"ch_srvs_{ch_id}"))
        text = (
            f"➕ <b>إضافة سيرفر/جودة جديدة للقناة: {ch.get('name')}</b>\n"
            f"اختر الجودة المطلوبة لإضافة رابطها:"
        )
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    # Add Quality / Server to Channel - Step 2: Quality selected, Ask for URL
    if data.startswith("ch_setaddsrv_q_"):
        parts = data[len("ch_setaddsrv_q_"):].split("_", 1)
        if len(parts) == 2:
            ch_id, quality = parts[0], parts[1]
            user_states[user_id] = {
                "action": "wait_ch_addsrv_url",
                "data": {"id": ch_id, "quality": quality}
            }
            text = (
                f"🔗 <b>أرسل الآن رابط البث لجودة ({quality}):</b>\n\n"
                f"يدعم جميع صيغ البث المباشر (m3u8, ts, php, js, json):"
            )
            bot.send_message(call.message.chat.id, text, reply_markup=cancel_keyboard())
            bot.answer_callback_query(call.id)
            return

    # Quick Search Channel Prompt
    if data == "ch_search_prompt":
        user_states[user_id] = {"action": "wait_channel_search", "data": {}}
        text = (
            "🔍 <b>البحث الذكي عن القنوات</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "أرسل الآن <b>اسم القناة</b> (أو جزءاً منه باللغة العربية أو الإنجليزية) أو <b>رابط البث</b>:\n"
            "<i>(مثال: <code>beIN</code> أو <code>الكأس</code> أو <code>مباشر</code>)</i>"
        )
        bot.send_message(call.message.chat.id, text, reply_markup=cancel_keyboard())
        bot.answer_callback_query(call.id)
        return

    # Browse Channels by Category
    if data == "ch_browse_by_cat":
        cats = db.get_categories()
        if not cats:
            bot.answer_callback_query(call.id, "⚠️ لا توجد أقسام مسجلة حالياً", show_alert=True)
            return
        kb = types.InlineKeyboardMarkup(row_width=1)
        for c in cats:
            count = len(db.get_channels(c["id"]))
            kb.add(types.InlineKeyboardButton(f"{c.get('icon', '📁')} {c.get('name')} ({count} قناة)", callback_data=f"ch_catlist_{c['id']}_0"))
        kb.add(types.InlineKeyboardButton("🔙 رجوع لقسم القنوات", callback_data="menu_channels"))
        text = "📂 <b>تصفح القنوات حسب الأقسام:</b>\nاختر القسم لعرض جميع قنواته وإدارتها بالتفصيل:"
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    # Category Channel Listing with Pagination
    if data.startswith("ch_catlist_"):
        parts = data[len("ch_catlist_"):].rsplit("_", 1)
        cat_id = parts[0]
        try:
            page = int(parts[1])
        except (IndexError, ValueError):
            page = 0

        cat = db.get_category(cat_id)
        cat_name = cat.get("name", cat_id) if cat else cat_id
        cat_icon = cat.get("icon", "📁") if cat else "📁"

        channels = db.get_channels(cat_id)
        if len(channels) == 0:
            text = (
                f"📋 <b>لا توجد قنوات مسجلة في قسم «{cat_icon} {cat_name}» حالياً.</b>\n"
                f"يمكنك إضافة قناة جديدة في هذا القسم مباشرة عبر الزر أدناه:"
            )
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton(f"➕ إضافة قناة في قسم «{cat_name}»", callback_data=f"ch_uni_cat_{cat_id}"))
            kb.add(types.InlineKeyboardButton("🔙 رجوع للأقسام", callback_data="ch_browse_by_cat"))
            try:
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
            except Exception:
                bot.send_message(call.message.chat.id, text, reply_markup=kb)
            bot.answer_callback_query(call.id)
            return

        per_page = 6
        total_pages = (len(channels) + per_page - 1) // per_page
        if total_pages == 0: total_pages = 1
        page = max(0, min(page, total_pages - 1))

        start = page * per_page
        end = start + per_page
        slice_ch = channels[start:end]

        kb = types.InlineKeyboardMarkup(row_width=1)
        for ch in slice_ch:
            name_label = ch.get('name', 'قناة')
            qual_label = ch.get('quality', 'FHD')
            dis_dot = "🔴 " if ch.get("disabled", False) else "🟢 "
            kb.add(types.InlineKeyboardButton(f"{dis_dot}{name_label} [{qual_label}]", callback_data=f"ch_view_{ch['id']}"))

        nav_row = []
        if page > 0:
            nav_row.append(types.InlineKeyboardButton("⬅️ السابق", callback_data=f"ch_catlist_{cat_id}_{page-1}"))
        nav_row.append(types.InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_row.append(types.InlineKeyboardButton("التالي ➡️", callback_data=f"ch_catlist_{cat_id}_{page+1}"))
        if nav_row:
            kb.row(*nav_row)

        kb.add(types.InlineKeyboardButton(f"➕ إضافة قناة جديدة في «{cat_name}»", callback_data=f"ch_uni_cat_{cat_id}"))
        kb.add(types.InlineKeyboardButton("🔙 رجوع للأقسام", callback_data="ch_browse_by_cat"))

        text = f"📂 <b>قنوات قسم: {cat_icon} {cat_name} ({len(channels)} قناة)</b>\nاختر أي قناة لعرض تفاصيلها أو تعديلها أو فحصها:"
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    # Comprehensive Statistics View
    if data == "ch_stats_view":
        stats = db.get_channel_stats()
        text = (
            "📊 <b>إحصائيات شاملة للأقسام والقنوات - تطبيق A2 TV</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🗂️ إجمالي الأقسام: <b>{stats['total_categories']}</b>\n"
            f"📺 إجمالي القنوات: <b>{stats['total_channels']}</b>\n"
            f"🟢 القنوات النشطة: <b>{stats['active_channels']}</b>\n"
            f"🔴 القنوات المعطلة: <b>{stats['disabled_channels']}</b>\n"
            f"✨ قنوات متعددة الجودات: <b>{stats['multi_quality_channels']}</b>\n"
            f"🌐 سيرفرات الـ API: <b>{stats['total_apis']}</b>\n\n"
            "📁 <b>توزيع القنوات حسب الأقسام:</b>\n"
        )
        for cat_n, count in stats.get("by_category", {}).items():
            text += f"• {cat_n}: <b>{count}</b> قناة\n"

        text += "\n✨ <b>توزيع الجودات:</b>\n"
        for q_name, q_count in stats.get("by_quality", {}).items():
            text += f"• جودة {q_name}: <b>{q_count}</b>\n"

        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("💾 تصدير ونسخ احتياطي", callback_data="ch_export_menu"))
        kb.add(types.InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu"))
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    # Export & Backup Menu
    if data == "ch_export_menu":
        text = (
            "💾 <b>تصدير القنوات والنسخ الاحتياطي (Export & Backup)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "يمكنك استخراج نسخة كاملة من قنواتك وأقسامك بعدة خيارات:\n\n"
            "1. <b>ملف M3U (IPTV Playlist):</b> جاهز للتشغيل والمشاركة على أي جهاز أو مشغل IPTV خارجي.\n"
            "2. <b>نسخة JSON كاملة:</b> نسخة احتياطية آمنة لقاعدة البيانات بالكامل يمكن استعادتها في أي وقت.\n"
            "3. <b>رابط السيرفر المباشر:</b> رابط حي لتشغيل القنوات عبر الإنترنت."
        )
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(types.InlineKeyboardButton("📥 تحميل ملف قائمة التشغيل (M3U)", callback_data="ch_export_m3u_file"))
        kb.add(types.InlineKeyboardButton("💾 تحميل ملف النسخة الاحتياطية (JSON)", callback_data="ch_export_json_file"))
        kb.add(types.InlineKeyboardButton("🌐 عرض رابط M3U المباشر", callback_data="ch_export_m3u_link"))
        kb.add(types.InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu"))
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    # Export M3U File
    if data == "ch_export_m3u_file":
        bot.answer_callback_query(call.id, "⏳ جاري توليد ملف M3U...")
        m3u_content = db.export_channels_m3u()
        temp_path = os.path.join(os.path.dirname(__file__), "data", "a2tv_playlist.m3u")
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(m3u_content)
        with open(temp_path, "rb") as f:
            bot.send_document(
                call.message.chat.id,
                f,
                caption=f"📥 <b>قائمة قنوات A2 TV بصيغة M3U</b>\nعدد القنوات: <b>{len(db.get_channels())}</b> قناة\nجاهزة للتشغيل على VLC أو أي برنامج IPTV.",
                reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 رجوع", callback_data="ch_export_menu"))
            )
        return

    # Export JSON Backup File
    if data == "ch_export_json_file":
        bot.answer_callback_query(call.id, "⏳ جاري توليد ملف النسخة الاحتياطية...")
        json_content = db.export_database_json()
        temp_path = os.path.join(os.path.dirname(__file__), "data", "a2tv_backup.json")
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(json_content)
        with open(temp_path, "rb") as f:
            bot.send_document(
                call.message.chat.id,
                f,
                caption=f"💾 <b>نسخة احتياطية كاملة لقاعدة بيانات A2 TV (JSON)</b>\nتحتوي على كافة الأقسام والقنوات وسيرفرات الـ API والمشرفين.",
                reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 رجوع", callback_data="ch_export_menu"))
            )
        return

    # Show M3U Direct URL
    if data == "ch_export_m3u_link":
        url = f"{PUBLIC_URL}/api/export/m3u"
        text = (
            f"🌐 <b>رابط تشغيل قائمة القنوات المباشر (Live M3U Link):</b>\n\n"
            f"<code>{url}</code>\n\n"
            f"يمكن وضع هذا الرابط في أي تطبيق IPTV لتحديث القنوات تلقائياً فوراً من السيرفر!"
        )
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 رجوع", callback_data="ch_export_menu"))
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    # Edit Channel Name
    if data.startswith("ch_edname_"):
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        ch_id = data[len("ch_edname_"):]
        ch = db.get_channel(ch_id)
        if not ch:
            bot.answer_callback_query(call.id, "⚠️ القناة غير موجودة", show_alert=True)
            return
        user_states[user_id] = {"action": "wait_ch_edname", "data": {"id": ch_id, "name": ch.get("name")}}
        text = (
            f"✏️ <b>تعديل اسم القناة</b>\n"
            f"الاسم الحالي: <b>{ch.get('name')}</b>\n\n"
            f"أرسل الآن الاسم الجديد للقناة:"
        )
        bot.send_message(call.message.chat.id, text, reply_markup=cancel_keyboard())
        bot.answer_callback_query(call.id)
        return

    # Edit Channel URL
    if data.startswith("ch_edurl_"):
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        ch_id = data[len("ch_edurl_"):]
        ch = db.get_channel(ch_id)
        if not ch:
            bot.answer_callback_query(call.id, "⚠️ القناة غير موجودة", show_alert=True)
            return
        user_states[user_id] = {"action": "wait_ch_edurl", "data": {"id": ch_id, "name": ch.get("name")}}
        text = (
            f"🔗 <b>تعديل رابط البث للقناة: {ch.get('name')}</b>\n"
            f"الرابط الحالي:\n<code>{ch.get('url')}</code>\n\n"
            f"أرسل الآن رابط البث الجديد (m3u8, ts, js, php, json):"
        )
        bot.send_message(call.message.chat.id, text, reply_markup=cancel_keyboard())
        bot.answer_callback_query(call.id)
        return

    # Edit Channel Category (Select New Category)
    if data.startswith("ch_edcat_"):
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        ch_id = data[len("ch_edcat_"):]
        ch = db.get_channel(ch_id)
        if not ch:
            bot.answer_callback_query(call.id, "⚠️ القناة غير موجودة", show_alert=True)
            return
        cats = db.get_categories()
        kb = types.InlineKeyboardMarkup(row_width=2)
        for c in cats:
            kb.add(types.InlineKeyboardButton(f"{c.get('icon', '📁')} {c.get('name')}", callback_data=f"ch_setcat_{ch_id}_{c['id']}"))
        kb.add(types.InlineKeyboardButton("🔙 إلغاء والرجوع للقناة", callback_data=f"ch_view_{ch_id}"))
        text = (
            f"📁 <b>نقل القناة «{ch.get('name')}» إلى قسم آخر</b>\n"
            f"القسم الحالي: <b>{ch.get('categoryName', 'عام')}</b>\n\n"
            f"اختر القسم الجديد من القائمة التالية:"
        )
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    # Apply Channel Category Change
    if data.startswith("ch_setcat_"):
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        parts = data[len("ch_setcat_"):].split("_", 1)
        if len(parts) == 2:
            ch_id, new_cat_id = parts[0], parts[1]
            cat = db.get_category(new_cat_id)
            cat_name = cat["name"] if cat else new_cat_id
            success, res = db.update_channel(ch_id, {"category": new_cat_id, "categoryName": cat_name})
            if success:
                bot.answer_callback_query(call.id, f"✅ تم نقل القناة إلى قسم «{cat_name}»", show_alert=True)
            else:
                bot.answer_callback_query(call.id, f"❌ فشل النقل: {res}", show_alert=True)
            call.data = f"ch_view_{ch_id}"
            handle_callback(call)
            return

    # Edit Channel Quality (Pick Quality)
    if data.startswith("ch_edqual_"):
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        ch_id = data[len("ch_edqual_"):]
        ch = db.get_channel(ch_id)
        if not ch:
            bot.answer_callback_query(call.id, "⚠️ القناة غير موجودة", show_alert=True)
            return
        kb = types.InlineKeyboardMarkup(row_width=2)
        for q in ["4K", "FHD", "HD", "SD", "LOW"]:
            kb.add(types.InlineKeyboardButton(f"✨ جودة {q}", callback_data=f"ch_setqual_{ch_id}_{q}"))
        kb.add(types.InlineKeyboardButton("🔙 إلغاء والرجوع للقناة", callback_data=f"ch_view_{ch_id}"))
        text = f"✨ <b>تغيير جودة القناة: {ch.get('name')}</b>\nالجودة الحالية: <b>{ch.get('quality', 'FHD')}</b>\nاختر الجودة الجديدة:"
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    # Apply Channel Quality Change
    if data.startswith("ch_setqual_"):
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        parts = data[len("ch_setqual_"):].split("_", 1)
        if len(parts) == 2:
            ch_id, new_qual = parts[0], parts[1]
            success, res = db.update_channel(ch_id, {"quality": new_qual})
            if success:
                bot.answer_callback_query(call.id, f"✅ تم تغيير الجودة إلى {new_qual}", show_alert=True)
            else:
                bot.answer_callback_query(call.id, f"❌ فشل تغيير الجودة: {res}", show_alert=True)
            call.data = f"ch_view_{ch_id}"
            handle_callback(call)
            return

    # Delete Channel Action with Verification
    if data.startswith("ch_del_"):
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        ch_id = data[len("ch_del_"):]
        success, res = db.delete_channel(ch_id)
        if success:
            bot.answer_callback_query(call.id, f"✅ تم حذف القناة بنجاح: {res}", show_alert=True)
        else:
            bot.answer_callback_query(call.id, f"❌ فشل حذف القناة: {res}", show_alert=True)
        call.data = "ch_list_0"
        handle_callback(call)
        return

    # Category List
    if data == "cat_list":
        cats = db.get_categories()
        if len(cats) == 0:
            text = "🗂️ <b>لا توجد أقسام مسجلة حالياً.</b>\nيمكنك إنشاء قسم جديد عبر زر «إضافة قسم جديد»."
            try:
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=channels_menu_keyboard())
            except Exception:
                bot.send_message(call.message.chat.id, text, reply_markup=channels_menu_keyboard())
            bot.answer_callback_query(call.id)
            return
        kb = types.InlineKeyboardMarkup(row_width=1)
        for c in cats:
            ch_in_cat = len(db.get_channels(c["id"]))
            kb.add(types.InlineKeyboardButton(f"{c.get('icon', '📁')} {c.get('name')} ({ch_in_cat} قناة)", callback_data=f"cat_view_{c['id']}"))
        kb.add(types.InlineKeyboardButton("➕ إضافة قسم جديد", callback_data="cat_add"))
        kb.add(types.InlineKeyboardButton("🔙 رجوع لقسم القنوات", callback_data="menu_channels"))
        text = f"🗂️ <b>قائمة الأقسام الحالية ({len(cats)} قسم)</b>\nاضغط على أي قسم لعرض تفاصيله أو تعديله أو حذفه:"
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    # View Category Details
    if data.startswith("cat_view_"):
        cat_id = data[len("cat_view_"):]
        cat = db.get_category(cat_id)
        if not cat:
            bot.answer_callback_query(call.id, "⚠️ القسم غير موجود أو تم حذفه", show_alert=True)
            call.data = "cat_list"
            handle_callback(call)
            return

        api_id = cat.get("api_id")
        api_name = "مباشر (بدون API)"
        if api_id:
            api_obj = db.get_channel_api(api_id)
            if api_obj:
                api_name = f"{api_obj.get('name')} [{api_obj.get('type', 'api').upper()}]"

        ch_in_cat = db.get_channels(cat_id)
        is_hidden = cat.get("hidden", False)
        status_text = "👁️‍🗨️ مخفي من التطبيق" if is_hidden else "🟢 ظاهر في التطبيق"

        text = (
            f"📁 <b>تفاصيل القسم: {cat.get('icon', '📁')} {cat.get('name')}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 المعرف البرمجي: <code>{cat.get('id')}</code>\n"
            f"🔘 الحالة: <b>{status_text}</b>\n"
            f"🌐 السيرفر المرتبط: <b>{api_name}</b>\n"
            f"🎨 الأيقونة: <b>{cat.get('icon', '📁')}</b>\n"
            f"📺 عدد القنوات بداخله: <b>{len(ch_in_cat)}</b> قناة\n"
        )
        kb = types.InlineKeyboardMarkup(row_width=2)
        b_view_ch = types.InlineKeyboardButton(f"📺 قنوات هذا القسم ({len(ch_in_cat)})", callback_data=f"ch_catlist_{cat_id}_0")
        b_add_ch = types.InlineKeyboardButton("➕ إضافة قناة هنا", callback_data=f"ch_uni_cat_{cat_id}")
        
        b_edname = types.InlineKeyboardButton("✏️ تعديل الاسم", callback_data=f"cat_edname_{cat_id}")
        b_edicon = types.InlineKeyboardButton("🎨 تغيير الأيقونة", callback_data=f"cat_edicon_{cat_id}")
        
        b_up = types.InlineKeyboardButton("⬆️ للأعلى", callback_data=f"cat_moveup_{cat_id}")
        b_down = types.InlineKeyboardButton("⬇️ للأسفل", callback_data=f"cat_movedown_{cat_id}")

        b_hide = types.InlineKeyboardButton("🟢 إظهار بالتطبيق" if is_hidden else "👁️ إخفاء من التطبيق", callback_data=f"cat_togglehide_{cat_id}")
        b_bind = types.InlineKeyboardButton("🌐 ربط بـ API", callback_data=f"cat_bind_{cat_id}")
        
        b_clear = types.InlineKeyboardButton("🧹 تفريغ قنوات القسم", callback_data=f"cat_clear_prompt_{cat_id}")
        b_del = types.InlineKeyboardButton("🗑️ خيارات حذف القسم", callback_data=f"cat_del_prompt_{cat_id}")
        
        b_back = types.InlineKeyboardButton("🔙 رجوع لقائمة الأقسام", callback_data="cat_list")

        kb.row(b_view_ch, b_add_ch)
        kb.row(b_edname, b_edicon)
        kb.row(b_up, b_down)
        kb.row(b_hide, b_bind)
        kb.row(b_clear, b_del)
        kb.add(b_back)

        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    # Move Category Up / Down in Order
    if data.startswith("cat_moveup_") or data.startswith("cat_movedown_"):
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        direction = "up" if data.startswith("cat_moveup_") else "down"
        cat_id = data[len("cat_moveup_"):] if direction == "up" else data[len("cat_movedown_"):]
        ok, res = db.reorder_category(cat_id, direction)
        bot.answer_callback_query(call.id, res, show_alert=not ok)
        call.data = f"cat_view_{cat_id}"
        handle_callback(call)
        return

    # Toggle Category Visibility (Hidden / Visible)
    if data.startswith("cat_togglehide_"):
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        cat_id = data[len("cat_togglehide_"):]
        ok, new_state = db.toggle_category_hidden(cat_id)
        if ok:
            msg = "👁️ تم إخفاء القسم من التطبيق" if new_state else "🟢 تم إظهار القسم في التطبيق بنجاح"
            bot.answer_callback_query(call.id, msg, show_alert=True)
        else:
            bot.answer_callback_query(call.id, f"❌ {new_state}", show_alert=True)
        call.data = f"cat_view_{cat_id}"
        handle_callback(call)
        return

    # Clear All Channels in Category (Prompt)
    if data.startswith("cat_clear_prompt_"):
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        cat_id = data[len("cat_clear_prompt_"):]
        cat = db.get_category(cat_id)
        count = len(db.get_channels(cat_id))
        text = (
            f"⚠️ <b>تحذير تفريغ القنوات:</b>\n"
            f"هل أنت متأكد من رغبتك في حذف جميع قنوات قسم <b>{cat.get('icon', '📁')} {cat.get('name')}</b>؟\n\n"
            f"📊 عدد القنوات التي سيتم حذفها: <b>{count}</b> قناة.\n"
            f"لن يتم حذف القسم نفسه، فقط القنوات الموجودة بداخله."
        )
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(types.InlineKeyboardButton(f"🚨 نعم، احذف جميع الـ {count} قناة الآن", callback_data=f"cat_clear_confirm_{cat_id}"))
        kb.add(types.InlineKeyboardButton("❌ إلغاء وتراجع", callback_data=f"cat_view_{cat_id}"))
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    # Clear All Channels in Category (Confirm)
    if data.startswith("cat_clear_confirm_"):
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        cat_id = data[len("cat_clear_confirm_"):]
        removed = db.clear_category_channels(cat_id)
        bot.answer_callback_query(call.id, f"✅ تم تفريغ القسم وحذف {removed} قناة بنجاح", show_alert=True)
        call.data = f"cat_view_{cat_id}"
        handle_callback(call)
        return

    # Bind Category to API
    if data.startswith("cat_bind_"):
        cat_id = data[len("cat_bind_"):]
        cat = db.get_category(cat_id)
        if not cat:
            bot.answer_callback_query(call.id, "⚠️ القسم غير موجود", show_alert=True)
            return
        apis = db.get_channel_apis()
        kb = types.InlineKeyboardMarkup(row_width=1)
        for a in apis:
            kb.add(types.InlineKeyboardButton(f"🌐 ربط بـ {a.get('name')}", callback_data=f"cat_setapi_{cat_id}_{a['id']}"))
        kb.add(types.InlineKeyboardButton("📡 فصل الربط (قنوات مباشرة)", callback_data=f"cat_setapi_{cat_id}_none"))
        kb.add(types.InlineKeyboardButton("🔙 رجوع لتفاصيل القسم", callback_data=f"cat_view_{cat_id}"))

        text = (
            f"🌐 <b>ربط القسم بسيرفر API:</b>\n"
            f"القسم: <b>{cat.get('icon', '📁')} {cat.get('name')}</b>\n\n"
            f"اختر سيرفر الـ API لربط هذا القسم به:"
        )
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    # Set Category API Target
    if data.startswith("cat_setapi_"):
        parts = data[len("cat_setapi_"):].split("_", 1)
        if len(parts) == 2:
            cat_id, target_api = parts
            db.update_category(cat_id, api_id=target_api)
            bot.answer_callback_query(call.id, "✅ تم تحديث ارتباط الـ API للقسم بنجاح")
            call.data = f"cat_view_{cat_id}"
            handle_callback(call)
            return

    # Edit Category Name
    if data.startswith("cat_edname_"):
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        cat_id = data[len("cat_edname_"):]
        cat = db.get_category(cat_id)
        if not cat:
            bot.answer_callback_query(call.id, "⚠️ القسم غير موجود", show_alert=True)
            return
        user_states[user_id] = {"action": "wait_cat_edname", "data": {"id": cat_id, "name": cat.get("name")}}
        text = (
            f"✏️ <b>تعديل اسم القسم</b>\n"
            f"الاسم الحالي: <b>{cat.get('name')}</b>\n\n"
            f"أرسل الآن الاسم الجديد للقسم:\n"
            f"<i>سيتم تلقائياً تحديث اسم القسم في جميع القنوات التابعة له.</i>"
        )
        bot.send_message(call.message.chat.id, text, reply_markup=cancel_keyboard())
        bot.answer_callback_query(call.id)
        return

    # Edit Category Icon
    if data.startswith("cat_edicon_"):
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        cat_id = data[len("cat_edicon_"):]
        cat = db.get_category(cat_id)
        if not cat:
            bot.answer_callback_query(call.id, "⚠️ القسم غير موجود", show_alert=True)
            return
        user_states[user_id] = {"action": "wait_cat_edicon", "data": {"id": cat_id, "name": cat.get("name")}}
        text = (
            f"🎨 <b>تغيير أيقونة القسم: {cat.get('name')}</b>\n"
            f"الأيقونة الحالية: <b>{cat.get('icon', '📁')}</b>\n\n"
            f"أرسل الآن رمز الإيموجي أو الأيقونة الجديدة (مثال: ⚽ أو 🎬 أو 🔴 أو 🕋):"
        )
        bot.send_message(call.message.chat.id, text, reply_markup=cancel_keyboard())
        bot.answer_callback_query(call.id)
        return

    # Category Delete Choices Prompt
    if data.startswith("cat_del_prompt_") or data.startswith("cat_del_"):
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        prefix = "cat_del_prompt_" if data.startswith("cat_del_prompt_") else "cat_del_"
        cat_id = data[len(prefix):]
        cat = db.get_category(cat_id)
        if not cat:
            bot.answer_callback_query(call.id, "⚠️ القسم غير موجود", show_alert=True)
            return

        ch_in_cat = len(db.get_channels(cat_id))
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(types.InlineKeyboardButton(f"🗑️ حذف القسم مع جميع قنواته ({ch_in_cat} قناة)", callback_data=f"cat_delall_{cat_id}"))
        kb.add(types.InlineKeyboardButton(f"📁 حذف القسم فقط ونقل القنوات لقسم عام", callback_data=f"cat_delkeep_{cat_id}"))
        kb.add(types.InlineKeyboardButton("🔙 تراجع وإلغاء", callback_data=f"cat_view_{cat_id}"))

        prompt_text = (
            f"⚠️ <b>تأكيد حذف القسم: {cat.get('name')}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"يحتوي هذا القسم على <b>{ch_in_cat}</b> قناة.\n"
            f"اختر نوع الحذف المطلوب:"
        )
        try:
            bot.edit_message_text(prompt_text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        except Exception:
            bot.send_message(call.message.chat.id, prompt_text, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    # Delete Category with its Channels
    if data.startswith("cat_delall_"):
        cat_id = data[len("cat_delall_"):]
        success, res = db.delete_category(cat_id, delete_channels=True)
        if success:
            bot.answer_callback_query(call.id, "✅ تم حذف القسم وقنواته بنجاح", show_alert=True)
        else:
            bot.answer_callback_query(call.id, f"❌ فشل: {res}", show_alert=True)
        call.data = "cat_list"
        handle_callback(call)
        return

    # Delete Category while keeping channels
    if data.startswith("cat_delkeep_"):
        cat_id = data[len("cat_delkeep_"):]
        success, res = db.delete_category(cat_id, delete_channels=False)
        if success:
            bot.answer_callback_query(call.id, "✅ تم حذف القسم ونقل القنوات لقسم عام بنجاح", show_alert=True)
        else:
            bot.answer_callback_query(call.id, f"❌ فشل: {res}", show_alert=True)
        call.data = "cat_list"
        handle_callback(call)
        return

    # API Servers Menu
    if data == "menu_apis":
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك بإدارة سيرفرات API!", show_alert=True)
            return
        apis = db.get_channel_apis()
        text = (
            f"🌐 <b>إدارة سيرفرات وإعدادات الـ API</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"عدد سيرفرات API المسجلة: <b>{len(apis)}</b> سيرفر\n\n"
            f"يمكنك إضافة روابط واجهات برمجة التطبيقات (PHP API JSON أو سيرفرات M3U)، "
            f"وتعديلها أو حذفها ومزامنتها بنقرة واحدة لتحديث القنوات داخل التطبيق فوراً."
        )
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=apis_menu_keyboard())
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=apis_menu_keyboard())
        bot.answer_callback_query(call.id)
        return

    # Add API Server Wizard - Step 1
    if data == "api_add":
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        user_states[user_id] = {"action": "wait_api_name", "data": {}}
        text = (
            f"➕ <b>إضافة سيرفر API جديد</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"الخطوة 1 من 3: أرسل <b>اسم السيرفر أو الـ API</b>\n"
            f"(مثال: <code>سيرفر الأسطورة المباشر</code> أو <code>API سيرفر بي إن</code>):"
        )
        bot.send_message(call.message.chat.id, text, reply_markup=cancel_keyboard())
        bot.answer_callback_query(call.id)
        return

    # Select API Type (Step 3 of API Add)
    if data.startswith("api_settype_"):
        api_type = data[len("api_settype_"):]
        state = user_states.get(user_id)
        if not state or state.get("action") != "wait_api_type":
            bot.answer_callback_query(call.id, "انتهت صلاحية الجلسة، يرجى إعادة المحاولة.", show_alert=True)
            return
        d = state["data"]
        name = d.get("name", "سيرفر API")
        url = d.get("url", "")
        
        res_tuple = db.add_channel_api(name, url, api_type)
        if len(res_tuple) == 3:
            success, new_api, sync_res = res_tuple
        else:
            success, new_api = res_tuple
            sync_res = {}

        user_states.pop(user_id, None)
        if success:
            cats = sync_res.get("categories", [])
            ch_count = sync_res.get("channels_count", 0)

            cats_text = ""
            if cats:
                cats_text = "\n🗂️ <b>أقسام القنوات التابعة لهذا السيرفر:</b>\n"
                for idx, c in enumerate(cats, 1):
                    c_name = c.get("name", c.get("id"))
                    c_icon = c.get("icon", "📁")
                    c_cnt = c.get("channels_count", 0)
                    cats_text += f"{idx}. {c_icon} <b>{c_name}</b> ({c_cnt} قناة)\n"
            else:
                cats_text = "\n<i>لم يتم العثور على أقسام تلقائياً. يمكنك إضافة أقسام لهذا السيرفر يدوياً.</i>"

            kb = types.InlineKeyboardMarkup(row_width=1)
            kb.add(types.InlineKeyboardButton("➕ إضافة قنوات إلى هذا الـ API", callback_data=f"ch_uni_api_{new_api['id']}"))
            kb.add(types.InlineKeyboardButton("🔄 إعادة مزامنة السيرفر", callback_data=f"api_sync_{new_api['id']}"))
            kb.add(types.InlineKeyboardButton("📋 قائمة سيرفرات الـ API", callback_data="api_list"))
            kb.add(types.InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu"))
            text = (
                f"✅ <b>تمت إضافة ومزامنة سيرفر الـ API بنجاح!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🏷️ الاسم: <b>{new_api['name']}</b>\n"
                f"🔗 الرابط: <code>{new_api['url']}</code>\n"
                f"📁 النوع: <b>{new_api['type'].upper()}</b>\n"
                f"📺 القنوات المضافة: <b>{ch_count}</b> قناة\n"
                f"{cats_text}\n"
                f"أصبحت القنوات متوفرة مباشرة داخل تطبيق A2 TV بدون الحاجة لإعادة تثبيت التطبيق!"
            )
            bot.send_message(call.message.chat.id, text, reply_markup=kb)
            bot.answer_callback_query(call.id, "✅ تم الحفظ والمزامنة")
        else:
            bot.send_message(call.message.chat.id, f"❌ {new_api}", reply_markup=apis_menu_keyboard())
            bot.answer_callback_query(call.id, "❌ فشل الحفظ")
        return

    # List API Servers
    if data == "api_list":
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        apis = db.get_channel_apis()
        if not apis:
            text = "📋 <b>لا توجد سيرفرات API مسجلة حالياً.</b>\nأضف سيرفر جديد عبر زر «إضافة سيرفر API جديد»."
            try:
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=apis_menu_keyboard())
            except Exception:
                bot.send_message(call.message.chat.id, text, reply_markup=apis_menu_keyboard())
            bot.answer_callback_query(call.id)
            return

        kb = types.InlineKeyboardMarkup(row_width=1)
        for a in apis:
            kb.add(types.InlineKeyboardButton(f"🌐 {a.get('name')} [{a.get('type', 'api')}]", callback_data=f"api_view_{a['id']}"))
        kb.add(types.InlineKeyboardButton("➕ إضافة سيرفر جديد", callback_data="api_add"))
        kb.add(types.InlineKeyboardButton("🔙 رجوع لإعدادات API", callback_data="menu_apis"))
        text = f"📋 <b>قائمة سيرفرات الـ API المسجلة ({len(apis)} سيرفر)</b>\nاضغط على أي سيرفر لتعديله أو مزامنته أو حذفه:"
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    # View Single API Server
    if data.startswith("api_view_"):
        api_id = data[len("api_view_"):]
        api_obj = db.get_channel_api(api_id)
        if not api_obj:
            bot.answer_callback_query(call.id, "⚠️ السيرفر غير موجود أو تم حذفه", show_alert=True)
            call.data = "api_list"
            handle_callback(call)
            return

        text = (
            f"🌐 <b>تفاصيل سيرفر الـ API</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏷️ الاسم: <b>{api_obj.get('name')}</b>\n"
            f"🆔 المعرف: <code>{api_obj.get('id')}</code>\n"
            f"📁 النوع: <b>{api_obj.get('type', 'php_json').upper()}</b>\n"
            f"🟢 الحالة: <b>{api_obj.get('status', 'نشط')}</b>\n"
            f"🔗 الرابط:\n<code>{api_obj.get('url')}</code>\n"
        )
        kb = types.InlineKeyboardMarkup(row_width=2)
        b_sync = types.InlineKeyboardButton("🔄 مزامنة واستيراد القنوات", callback_data=f"api_sync_{api_id}")
        b_edname = types.InlineKeyboardButton("✏️ تعديل الاسم", callback_data=f"api_edname_{api_id}")
        b_edurl = types.InlineKeyboardButton("🔗 تعديل الرابط", callback_data=f"api_edurl_{api_id}")
        b_del = types.InlineKeyboardButton("🗑️ حذف السيرفر", callback_data=f"api_del_{api_id}")
        b_back = types.InlineKeyboardButton("🔙 رجوع للقائمة", callback_data="api_list")

        kb.add(b_sync)
        kb.row(b_edname, b_edurl)
        kb.add(b_del)
        kb.add(b_back)

        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    # Edit API Name
    if data.startswith("api_edname_"):
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        api_id = data[len("api_edname_"):]
        api_obj = db.get_channel_api(api_id)
        if not api_obj:
            bot.answer_callback_query(call.id, "⚠️ السيرفر غير موجود", show_alert=True)
            return
        user_states[user_id] = {"action": "wait_api_edname", "data": {"id": api_id, "name": api_obj.get("name")}}
        text = (
            f"✏️ <b>تعديل اسم سيرفر الـ API</b>\n"
            f"الاسم الحالي: <b>{api_obj.get('name')}</b>\n\n"
            f"أرسل الآن الاسم الجديد للسيرفر:"
        )
        bot.send_message(call.message.chat.id, text, reply_markup=cancel_keyboard())
        bot.answer_callback_query(call.id)
        return

    # Edit API URL
    if data.startswith("api_edurl_"):
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        api_id = data[len("api_edurl_"):]
        api_obj = db.get_channel_api(api_id)
        if not api_obj:
            bot.answer_callback_query(call.id, "⚠️ السيرفر غير موجود", show_alert=True)
            return
        user_states[user_id] = {"action": "wait_api_edurl", "data": {"id": api_id, "name": api_obj.get("name")}}
        text = (
            f"🔗 <b>تعديل رابط سيرفر الـ API: {api_obj.get('name')}</b>\n"
            f"الرابط الحالي:\n<code>{api_obj.get('url')}</code>\n\n"
            f"أرسل الآن الرابط الجديد للـ API:"
        )
        bot.send_message(call.message.chat.id, text, reply_markup=cancel_keyboard())
        bot.answer_callback_query(call.id)
        return

    # Delete API Server with Verification
    if data.startswith("api_del_"):
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        api_id = data[len("api_del_"):]
        success, res = db.delete_channel_api(api_id)
        if success:
            bot.answer_callback_query(call.id, f"✅ تم حذف سيرفر الـ API: {res}", show_alert=True)
        else:
            bot.answer_callback_query(call.id, f"❌ فشل الحذف: {res}", show_alert=True)
        call.data = "api_list"
        handle_callback(call)
        return

    # Sync Single API
    if data.startswith("api_sync_"):
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        api_id = data[len("api_sync_"):]
        api_obj = db.get_channel_api(api_id)
        if not api_obj:
            bot.answer_callback_query(call.id, "⚠️ السيرفر غير موجود", show_alert=True)
            return
        bot.answer_callback_query(call.id, "⏳ جاري الاتصال ومزامنة القنوات...")
        api_url = api_obj.get("url", "")
        api_type = api_obj.get("type", "php_json")
        if api_type == "m3u":
            imported = db.sync_m3u_from_url(api_url)
            success = imported >= 0
            err_msg = "" if success else "تعذر قراءة ملف M3U"
        else:
            res = db.sync_php_json(api_url)
            success = res.get("success", False)
            imported = res.get("channels_count", 0)
            err_msg = res.get("error", "فشل المزامنة")

        if success:
            total = len(db.get_channels())
            bot.send_message(
                call.message.chat.id,
                f"✅ <b>تمت مزامنة واستيراد القنوات بنجاح من {api_obj.get('name')}!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📺 القنوات المضافة: <b>{imported}</b> قناة\n"
                f"📊 إجمالي القنوات في التطبيق: <b>{total}</b> قناة\n\n"
                f"تظهر التغييرات فوراً في التطبيق بدون الحاجة لإعادة تثبيت APK.",
                reply_markup=apis_menu_keyboard()
            )
        else:
            bot.send_message(
                call.message.chat.id,
                f"❌ <b>فشلت المزامنة من سيرفر {api_obj.get('name')}:</b>\n<code>{err_msg}</code>",
                reply_markup=apis_menu_keyboard()
            )
        return

    # Sync All APIs
    if data == "api_sync_all":
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        apis = db.get_channel_apis()
        if not apis:
            bot.answer_callback_query(call.id, "لا توجد سيرفرات API مسجلة لمزامنتها!", show_alert=True)
            return
        bot.answer_callback_query(call.id, "⏳ جاري مزامنة جميع السيرفرات...")
        total_new = 0
        report = []
        for a in apis:
            a_url = a.get("url", "")
            a_type = a.get("type", "php_json")
            if a_type == "m3u":
                cnt = db.sync_m3u_from_url(a_url)
                if cnt >= 0:
                    total_new += cnt
                    report.append(f"• <b>{a.get('name')}</b>: تم استيراد {cnt} قناة")
                else:
                    report.append(f"• <b>{a.get('name')}</b>: ❌ فشل الاتصال")
            else:
                res = db.sync_php_json(a_url)
                if res.get("success"):
                    cnt = res.get("channels_count", 0)
                    total_new += cnt
                    report.append(f"• <b>{a.get('name')}</b>: تم استيراد {cnt} قناة")
                else:
                    report.append(f"• <b>{a.get('name')}</b>: ❌ خطأ ({res.get('error')})")

        total_channels = len(db.get_channels())
        summary_text = (
            f"🔄 <b>تقرير مزامنة جميع سيرفرات الـ API:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            + "\n".join(report) + "\n\n"
            f"📊 إجمالي القنوات المحدثة: <b>{total_new}</b>\n"
            f"📺 إجمالي قنوات التطبيق: <b>{total_channels}</b> قناة"
        )
        bot.send_message(call.message.chat.id, summary_text, reply_markup=apis_menu_keyboard())
        return


    # PHP API JSON Import Wizard
    if data == "ch_import_php":
        user_states[user_id] = {"action": "wait_php_json"}
        text = (
            "🌐 <b>استيراد القنوات من PHP API JSON</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "أرسل رابط API أو الصق كود JSON مباشرة هنا:"
        )
        bot.send_message(call.message.chat.id, text, reply_markup=cancel_keyboard())
        bot.answer_callback_query(call.id)
        return

    # M3U Import Wizard
    if data == "ch_import_m3u":
        user_states[user_id] = {"action": "wait_m3u_url"}
        text = (
            "📻 <b>استيراد القنوات من رابط M3U</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "أرسل رابط ملف أو سيرفر M3U للبث المباشر:"
        )
        bot.send_message(call.message.chat.id, text, reply_markup=cancel_keyboard())
        bot.answer_callback_query(call.id)
        return

    # Updates Menu
    if data == "menu_updates":
        if not check_admin(user_id, "updates"):
            bot.answer_callback_query(call.id, "⚠️ لا تملك صلاحية إدارة التحديثات!", show_alert=True)
            return
        up = db.get_app_update()
        st = "🟢 مفعل (يظهر للمستخدمين)" if up.get("enabled") else "🔴 معطل (لا يظهر)"
        fo = "نعم (إجباري)" if up.get("is_force") else "لا (اختياري)"
        text = (
            f"🔄 <b>إدارة تحديث التطبيق (APK Update)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"الحالة: <b>{st}</b>\n"
            f"رقم الإصدار الجديد (Code): <code>{up.get('version_code', 0)}</code>\n"
            f"اسم الإصدار الجديد: <b>{up.get('version_name', '1.0')}</b>\n"
            f"التحديث الإجباري: <b>{fo}</b>\n"
            f"رابط التحميل: <code>{up.get('download_url') or 'غير محدد بعد'}</code>\n"
            f"المميزات: <i>{up.get('release_notes') or 'لا يوجد'}</i>\n"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=updates_menu_keyboard())
        bot.answer_callback_query(call.id)
        return

    # Maintenance Menu
    if data == "menu_maint":
        if not check_admin(user_id, "maintenance"):
            bot.answer_callback_query(call.id, "⚠️ لا تملك صلاحية وضع الصيانة!", show_alert=True)
            return
        m = db.get_maintenance()
        st = "🔴 وضع الصيانة مفعل (التطبيق متوقف للمستخدمين)" if m.get("enabled") else "🟢 وضع الصيانة متوقف (التطبيق يعمل بشكل طبيعي)"
        text = (
            f"🛠️ <b>إدارة وضع الصيانة (Maintenance Mode)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"الحالة الحالية: <b>{st}</b>\n\n"
            f"الرسالة المعروضة للمستخدمين:\n"
            f"💬 <i>\"{m.get('message')}\"</i>\n"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=maintenance_menu_keyboard())
        bot.answer_callback_query(call.id)
        return

    # Maintenance Toggle
    if data == "maint_toggle":
        if not check_admin(user_id, "maintenance"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        current = db.get_maintenance()
        new_state = not current.get("enabled", False)
        msg = current.get("message")
        if not msg or not msg.strip() or "يعمل بشكل طبيعي" in msg:
            msg = "التطبيق تحت الصيانة حالياً، نعمل على تحسين تجربتك. يرجى المحاولة لاحقاً"
        success, m_data = db.set_maintenance(new_state, message=msg, admin_id=user_id)
        if success:
            alert_msg = "🔴 تم تفعيل وضع الصيانة وقفل الوصول للتطبيق والـ API!" if new_state else "🟢 تم إيقاف وضع الصيانة وعاد التطبيق والـ API للعمل بشكل طبيعي!"
            bot.answer_callback_query(call.id, alert_msg, show_alert=True)
        else:
            bot.answer_callback_query(call.id, f"❌ فشل تحديث وضع الصيانة: {m_data}", show_alert=True)
        call.data = "menu_maint"
        handle_callback(call)
        return

    # Maintenance Message Edit
    if data == "maint_msg":
        if not check_admin(user_id, "maintenance"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        user_states[user_id] = {"action": "wait_maint_msg"}
        text = (
            "✏️ <b>تعديل رسالة الصيانة للمستخدمين</b>\n"
            "أرسل الآن نص الرسالة التي تريد أن تظهر داخل التطبيق عند تفعيل الصيانة:"
        )
        bot.send_message(call.message.chat.id, text, reply_markup=cancel_keyboard())
        bot.answer_callback_query(call.id)
        return

    # Update Toggle
    if data == "up_toggle":
        if not check_admin(user_id, "updates"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        up = db.get_app_update()
        new_state = not up.get("enabled", False)
        db.toggle_app_update(new_state)
        alert_msg = "🟢 تم تفعيل إشعار التحديث في التطبيق!" if new_state else "🔴 تم إيقاف إشعار التحديث!"
        bot.answer_callback_query(call.id, alert_msg, show_alert=True)
        call.data = "menu_updates"
        handle_callback(call)
        return

    # Update Toggle Force
    if data == "up_toggle_force":
        if not check_admin(user_id, "updates"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        up = db.get_app_update()
        up["is_force"] = not up.get("is_force", False)
        db.set_app_update(
            up.get("version_code", 2),
            up.get("version_name", "1.1"),
            up.get("download_url", ""),
            up.get("release_notes", ""),
            up["is_force"],
            up.get("enabled", True)
        )
        bot.answer_callback_query(call.id, f"تم تغيير نوع التحديث إلى: {'إجباري' if up['is_force'] else 'اختياري'}")
        call.data = "menu_updates"
        handle_callback(call)
        return

    # Update New Wizard
    if data == "up_new":
        if not check_admin(user_id, "updates"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        user_states[user_id] = {"action": "wait_up_version_code"}
        text = (
            "📦 <b>إعداد تحديث جديد للتطبيق</b>\n\n"
            "الخطوة 1 من 4: أرسل <b>رقم الإصدار الجديد (Version Code)</b> كعدد صحيح (مثال: <code>3</code>):"
        )
        bot.send_message(call.message.chat.id, text, reply_markup=cancel_keyboard())
        bot.answer_callback_query(call.id)
        return

    # Admins Menu
    if data == "menu_admins":
        if ADMIN_ID and user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "⚠️ إدارة المشرفين متاحة للمدير العام فقط!", show_alert=True)
            return
        admins = db.get_admins()
        text = (
            f"👥 <b>إدارة المشرفين والصلاحيات</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"عدد الأدمن المسجلين: <b>{len(admins)}</b>\n"
            f"يمكنك إضافة مشرفين جدد وتحديد صلاحيات محددة لكل منهم."
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=admins_menu_keyboard())
        bot.answer_callback_query(call.id)
        return

    # Server Stats
    if data == "menu_stats":
        channels = db.get_channels()
        cats = db.get_categories()
        admins = db.get_admins()
        m = db.get_maintenance()
        up = db.get_app_update()
        text = (
            f"📊 <b>إحصائيات وحالة النظام المتصل بالتطبيق</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🌐 خادم الـ API: <code>{PUBLIC_URL}</code>\n"
            f"📦 الحزمة: <code>{APP_PACKAGE}</code>\n"
            f"📺 إجمالي القنوات: <b>{len(channels)}</b> قناة\n"
            f"📁 إجمالي الأقسام: <b>{len(cats)}</b> قسم\n"
            f"👥 عدد المشرفين: <b>{len(admins)}</b>\n"
            f"🛠️ الصيانة: <b>{'مفعلة 🔴' if m.get('enabled') else 'متوقفة 🟢'}</b>\n"
            f"🔄 التحديث: <b>{'نشط 🟢' if up.get('enabled') else 'معطل 🔴'}</b> (v{up.get('version_name')})\n"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=back_to_main_keyboard())
        bot.answer_callback_query(call.id)
        return

    # Admin List
    if data == "admin_list":
        admins = db.get_admins()
        kb = types.InlineKeyboardMarkup(row_width=1)
        for aid, ainfo in admins.items():
            if str(aid) != str(ADMIN_ID):
                kb.add(types.InlineKeyboardButton(f"❌ حذف: {ainfo.get('name')} ({aid})", callback_data=f"admin_del_{aid}"))
        kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="menu_admins"))
        msg_text = "👥 <b>قائمة المشرفين المسجلين:</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
        for aid, ainfo in admins.items():
            role_name = "المدير العام 👑" if ainfo.get("role") == "super_admin" else "مشرف 🛡️"
            perms = ", ".join(ainfo.get("permissions", ["all"]))
            msg_text += f"• <b>{ainfo.get('name')}</b> (<code>{aid}</code>)\n   الرتبة: {role_name}\n   الصلاحيات: <code>{perms}</code>\n\n"
        bot.edit_message_text(msg_text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    # Admin Delete Action
    if data.startswith("admin_del_"):
        if ADMIN_ID and user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "غير مصرح لك بحذف المشرفين!", show_alert=True)
            return
        del_id = data[len("admin_del_"):]
        if db.delete_admin(del_id):
            bot.answer_callback_query(call.id, "تم حذف المشرف بنجاح", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "تعذر الحذف", show_alert=True)
        call.data = "admin_list"
        handle_callback(call)
        return

    # Admin Add Wizard
    if data == "admin_add":
        if ADMIN_ID and user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "إضافة مشرفين متاحة للمدير العام فقط!", show_alert=True)
            return
        user_states[user_id] = {"action": "wait_admin_id", "data": {}}
        text = (
            "➕ <b>إضافة أدمن جديد</b>\n\n"
            "الخطوة 1 من 3: أرسل <b>الآيدي الرقمي</b> للمستخدم في تيليجرام (يمكنه الحصول عليه عبر @userinfobot):"
        )
        bot.send_message(call.message.chat.id, text, reply_markup=cancel_keyboard())
        bot.answer_callback_query(call.id)
        return

# ----------------- Document Handler (Direct APK Uploads) -----------------

@bot.message_handler(content_types=['document'])
def handle_document(message):
    user_id = message.from_user.id
    doc = message.document
    file_name = (doc.file_name or "").lower()

    # 1. M3U / M3U8 Playlist Upload
    if file_name.endswith(".m3u") or file_name.endswith(".m3u8"):
        if not check_admin(user_id, "channels"):
            bot.reply_to(message, "⚠️ غير مصرح لك بإدارة القنوات واستيراد الملفات!")
            return
        bot.reply_to(message, f"⏳ جاري تحميل وتحليل ملف قائمة القنوات (<b>{doc.file_name}</b>)...")
        try:
            file_info = bot.get_file(doc.file_id)
            downloaded = bot.download_file(file_info.file_path)
            try:
                content = downloaded.decode("utf-8")
            except UnicodeDecodeError:
                content = downloaded.decode("latin1", errors="ignore")

            parsed_channels = db._parse_m3u_text(content)
            if not parsed_channels:
                bot.reply_to(message, "⚠️ تعذر العثور على قنوات صالحة داخل ملف الـ M3U المرفوع.")
                return

            added_count = 0
            created_cats = set()
            for ch_item in parsed_channels:
                cat_id = ch_item.get("category", "general")
                cat_name = ch_item.get("categoryName", "عام")
                db.add_category(cat_id, cat_name, icon="📺")
                created_cats.add(cat_name)

                db.add_single_channel(
                    name=ch_item.get("name", "قناة"),
                    url=ch_item.get("url", ""),
                    category_id=cat_id,
                    category_name=cat_name,
                    logo=ch_item.get("logo", "📺"),
                    quality=ch_item.get("quality", "HD"),
                    referer=ch_item.get("referer", ""),
                    useragent=ch_item.get("useragent", "")
                )
                added_count += 1

            summary = (
                f"🎉 <b>تم استيراد ومعالجة ملف الـ M3U بنجاح!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📁 اسم الملف: <b>{doc.file_name}</b>\n"
                f"📺 عدد القنوات المستوردة: <b>{added_count}</b> قناة\n"
                f"🗂️ الأقسام المكتشفة: <b>{len(created_cats)}</b> قسم\n"
                f"✨ تم دمج الجودات المتعددة تلقائياً (Smart Quality Merging).\n\n"
                f"القنوات متاحة الآن فوراً لجميع مستخدمي تطبيق A2 TV!"
            )
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(types.InlineKeyboardButton("📺 عرض القنوات", callback_data="ch_list_0"))
            kb.add(types.InlineKeyboardButton("🗂️ عرض الأقسام", callback_data="cat_list"))
            kb.add(types.InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu"))
            bot.reply_to(message, summary, reply_markup=kb)
        except Exception as e:
            logger.error("Failed to import uploaded M3U: %s", e)
            bot.reply_to(message, f"❌ حدث خطأ أثناء استيراد ملف الـ M3U: {e}")
        return

    # 2. JSON Database Backup Upload
    if file_name.endswith(".json"):
        if not check_admin(user_id, "channels"):
            bot.reply_to(message, "⚠️ غير مصرح لك باستيراد النسخ الاحتياطية!")
            return
        bot.reply_to(message, f"⏳ جاري قراءة واستعادة النسخة الاحتياطية (<b>{doc.file_name}</b>)...")
        try:
            file_info = bot.get_file(doc.file_id)
            downloaded = bot.download_file(file_info.file_path)
            content = downloaded.decode("utf-8")
            ok, res_msg = db.import_database_json(content, merge=True)
            if ok:
                bot.reply_to(
                    message,
                    f"✅ <b>تم استعادة ودمج النسخة الاحتياطية بنجاح!</b>\n\n{res_msg}",
                    reply_markup=main_menu_keyboard(user_id)
                )
            else:
                bot.reply_to(message, f"❌ فشلت استعادة النسخة الاحتياطية: {res_msg}")
        except Exception as e:
            logger.error("Failed to import JSON backup: %s", e)
            bot.reply_to(message, f"❌ خطأ أثناء معالجة ملف JSON: {e}")
        return

    # 3. APK Update Upload
    if file_name.endswith(".apk"):
        if not check_admin(user_id, "updates"):
            bot.reply_to(message, "⚠️ غير مصرح لك بإدارة التحديثات!")
            return

        bot.reply_to(message, f"⏳ جاري استلام وتخزين ملف التطبيق (<b>{doc.file_name}</b>) على السيرفر...")
        try:
            import os
            file_info = bot.get_file(doc.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            save_dir = os.path.join(os.path.dirname(__file__), "data", "updates")
            os.makedirs(save_dir, exist_ok=True)
            apk_path = os.path.join(save_dir, "app.apk")
            
            with open(apk_path, "wb") as f:
                f.write(downloaded_file)
                
            public_url = f"{PUBLIC_URL}/static/app.apk"
            current_up = db.get_app_update()
            new_vcode = current_up.get("version_code", 2) + 1
            
            user_states[user_id] = {
                "action": "wait_apk_update_notes",
                "data": {
                    "version_code": new_vcode,
                    "version_name": f"v{new_vcode}.0",
                    "download_url": public_url
                }
            }
            
            prompt = (
                f"📦 <b>تم تخزين ملف الـ APK بنجاح على سيرفر التحديثات!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📁 اسم الملف: <b>{doc.file_name}</b>\n"
                f"🔢 رقم الإصدار المقترح: <code>{new_vcode}</code>\n"
                f"🔗 الرابط العام المباشر:\n<code>{public_url}</code>\n\n"
                f"أرسل الآن <b>ملاحظات ومميزات هذا التحديث</b> لنشره فوراً للمستخدمين:\n"
                f"(مثال: <code>إصلاح المشغل وإضافة أقسام وجودات جديدة</code>)"
            )
            bot.reply_to(message, prompt, reply_markup=cancel_keyboard())
        except Exception as e:
            logger.error("Failed to save uploaded APK: %s", e)
            bot.reply_to(message, f"❌ حدث خطأ أثناء حفظ ملف الـ APK: {e}")
        return

    # Unsupported file type
    bot.reply_to(
        message,
        "⚠️ <b>نوع الملف غير مدعوم!</b>\n"
        "يمكنك إرسال:\n"
        "• ملفات القنوات (<code>.m3u</code> أو <code>.m3u8</code>)\n"
        "• ملفات النسخ الاحتياطي (<code>.json</code>)\n"
        "• تحديثات التطبيق (<code>.apk</code>)"
    )

# ----------------- Text Messages & Multi-Step Wizards -----------------

@bot.message_handler(func=lambda msg: True)
def handle_text(message):
    user_id = message.from_user.id
    if not check_admin(user_id):
        return

    state = user_states.get(user_id)
    if not state:
        return

    action = state.get("action")
    text = (message.text or "").strip()

    # Unified Flow: Create Category on the fly
    if action == "wait_uni_newcat_name":
        cat_name = text
        icon = "📁"
        lower_n = cat_name.lower()
        if "رياض" in cat_name or "sport" in lower_n or "كورة" in cat_name: icon = "⚽"
        elif "أفلام" in cat_name or "فيلم" in cat_name or "سينما" in cat_name or "movie" in lower_n: icon = "🎬"
        elif "مسلسل" in cat_name or "دراما" in cat_name: icon = "🎭"
        elif "أخبار" in cat_name or "news" in lower_n: icon = "🔴"
        elif "دين" in cat_name or "قرآن" in cat_name or "إسلام" in cat_name: icon = "🕋"
        elif "أطفال" in cat_name or "كرتون" in cat_name or "kids" in lower_n: icon = "🦁"
        elif "وثائق" in cat_name: icon = "🌍"
        elif "موسيقى" in cat_name: icon = "🎵"

        cat_id = cat_name.lower().replace(" ", "_")
        cat_id = re.sub(r'[^a-zA-Z0-9_\u0600-\u06FF]', '', cat_id) or f"cat_{int(time.time())}"

        api_id = state.get("data", {}).get("api_id")
        api_name = state.get("data", {}).get("api_name", "مباشر")

        res_cat = db.add_category(cat_id, cat_name, icon, api_id=api_id)
        if isinstance(res_cat, tuple):
            ok, new_cat = res_cat
        else:
            new_cat = res_cat
        
        state["action"] = "wait_uni_channel_input"
        state["data"] = {
            "api_id": api_id,
            "api_name": api_name,
            "cat_id": new_cat["id"],
            "cat_name": new_cat["name"]
        }

        prompt = (
            f"✅ <b>تم إنشاء القسم بنجاح: {new_cat['icon']} {new_cat['name']}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🌐 الـ API: <b>{api_name}</b>\n\n"
            f"أرسل الآن بيانات القناة لإضافتها داخل هذا القسم:\n\n"
            f"🔹 <b>صيغة سريعة بسطر واحد:</b>\n"
            f"<code>اسم القناة | رابط البث | الجودة</code>\n"
            f"مثال:\n"
            f"<code>beIN Sports 1 | https://example.com/live.m3u8 | FHD</code>\n\n"
            f"🔹 أو أرسل رابط البث مباشرة (m3u8, ts, js, php, mpd)"
        )
        bot.reply_to(message, prompt, reply_markup=cancel_keyboard())
        return

    # Unified Flow: Channel Input
    if action == "wait_uni_channel_input":
        d = state["data"]
        cat_id = d.get("cat_id")
        cat_name = d.get("cat_name")
        api_id = d.get("api_id")
        api_name = d.get("api_name", "مباشر")

        # Check if raw JSON
        if text.startswith("[") or text.startswith("{"):
            try:
                parsed = json.loads(text)
                bot.reply_to(message, "⏳ جاري استيراد القنوات من كود JSON ودمج الجودات...")
                res = db._process_parsed_json(parsed, api_id=api_id)
                user_states.pop(user_id, None)
                msg = (
                    f"🎉 <b>تم استيراد قنوات الـ JSON بنجاح!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📺 إجمالي القنوات المضافة: <b>{res.get('channels_count', 0)}</b> قناة\n"
                    f"📁 الأقسام المكتشفة: <b>{res.get('categories_count', 0)}</b> قسم\n"
                    f"✨ تم دمج جودات القنوات المتكررة تلقائياً داخل كل قناة!"
                )
                bot.reply_to(message, msg, reply_markup=channels_menu_keyboard())
                return
            except Exception as e:
                bot.reply_to(message, f"⚠️ خطأ في قراءة كود الـ JSON: {e}\nتأكد من صحة الصيغة.")
                return

        # Check if piped format: Name | URL | Quality
        if "|" in text:
            parts = [p.strip() for p in text.split("|")]
            ch_name = parts[0]
            ch_url = parts[1]
            ch_qual = parts[2] if len(parts) > 2 else "FHD"

            ch = db.add_single_channel(
                name=ch_name,
                url=ch_url,
                category_id=cat_id,
                category_name=cat_name,
                quality=ch_qual,
                api_id=api_id
            )
            user_states.pop(user_id, None)

            srvs = ch.get("servers", [])
            quals = [s.get("quality", s.get("name")) for s in srvs if s.get("quality")]
            quals_text = ", ".join(quals) if quals else ch.get("quality", "FHD")

            kb = types.InlineKeyboardMarkup(row_width=1)
            kb.add(types.InlineKeyboardButton(f"➕ إضافة قناة أخرى في قسم «{cat_name}»", callback_data=f"ch_uni_cat_{cat_id}"))
            kb.add(types.InlineKeyboardButton("🗂️ اختيار قسم أو API آخر", callback_data="ch_add_unified"))
            kb.add(types.InlineKeyboardButton("📺 عرض وتعديل القنوات", callback_data="ch_list_0"))
            kb.add(types.InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu"))

            success_text = (
                f"🎉 <b>تمت إضافة القناة وتحديث الجودات بنجاح!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📺 القناة: <b>{ch['name']}</b>\n"
                f"📁 القسم: <b>{cat_name}</b>\n"
                f"🌐 السيرفر: <b>{api_name}</b>\n"
                f"✨ الجودات المتوفرة للقناة: <b>{quals_text} ({len(srvs)} سيرفر/جودة)</b>\n"
                f"🔗 الرابط: <code>{ch['url']}</code>\n\n"
                f"ستظهر القناة فوراً في تطبيق A2 TV بدون الحاجة لإعادة تشغيل أو إعادة تثبيت التطبيق!"
            )
            bot.reply_to(message, success_text, reply_markup=kb)
            return

        # Check if URL directly
        if text.startswith("http://") or text.startswith("https://") or text.startswith("rtmp://"):
            if "name" in d:
                ch_name = d["name"]
                ch = db.add_single_channel(
                    name=ch_name,
                    url=text,
                    category_id=cat_id,
                    category_name=cat_name,
                    quality="FHD",
                    api_id=api_id
                )
                user_states.pop(user_id, None)
                kb = types.InlineKeyboardMarkup(row_width=1)
                kb.add(types.InlineKeyboardButton(f"➕ إضافة قناة أخرى في قسم «{cat_name}»", callback_data=f"ch_uni_cat_{cat_id}"))
                kb.add(types.InlineKeyboardButton("🗂️ اختيار قسم أو API آخر", callback_data="ch_add_unified"))
                kb.add(types.InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu"))
                bot.reply_to(
                    message,
                    f"🎉 <b>تمت إضافة القناة بنجاح!</b>\n"
                    f"📺 القناة: <b>{ch['name']}</b>\n"
                    f"📁 القسم: <b>{cat_name}</b>\n"
                    f"🔗 الرابط: <code>{ch['url']}</code>",
                    reply_markup=kb
                )
                return
            else:
                state["data"]["url"] = text
                state["action"] = "wait_uni_channel_name_for_url"
                bot.reply_to(
                    message,
                    f"🔗 الرابط: <code>{text}</code>\n\n"
                    f"أرسل الآن <b>اسم القناة</b> (مثال: <code>beIN Sports 1</code>):",
                    reply_markup=cancel_keyboard()
                )
                return

        # Treat as channel name, then ask for URL
        state["data"]["name"] = text
        bot.reply_to(
            message,
            f"📺 اسم القناة: <b>{text}</b>\n\n"
            f"أرسل الآن <b>رابط البث</b> للقناة (m3u8, ts, js, php, mpd):",
            reply_markup=cancel_keyboard()
        )
        return

    # Name received for standalone URL
    if action == "wait_uni_channel_name_for_url":
        d = state["data"]
        cat_id = d.get("cat_id")
        cat_name = d.get("cat_name")
        api_id = d.get("api_id")
        api_name = d.get("api_name", "مباشر")
        url = d.get("url")

        ch = db.add_single_channel(
            name=text,
            url=url,
            category_id=cat_id,
            category_name=cat_name,
            quality="FHD",
            api_id=api_id
        )
        user_states.pop(user_id, None)

        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(types.InlineKeyboardButton(f"➕ إضافة قناة أخرى في قسم «{cat_name}»", callback_data=f"ch_uni_cat_{cat_id}"))
        kb.add(types.InlineKeyboardButton("🗂️ اختيار قسم أو API آخر", callback_data="ch_add_unified"))
        kb.add(types.InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu"))

        bot.reply_to(
            message,
            f"🎉 <b>تمت إضافة القناة بنجاح!</b>\n"
            f"📺 القناة: <b>{ch['name']}</b>\n"
            f"📁 القسم: <b>{cat_name}</b>\n"
            f"🌐 السيرفر: <b>{api_name}</b>\n"
            f"🔗 الرابط: <code>{ch['url']}</code>",
            reply_markup=kb
        )
        return

    # Uploaded APK Notes Step
    if action == "wait_apk_update_notes":
        d = state["data"]
        notes = text
        success, up_obj = db.set_app_update(
            version_code=d["version_code"],
            version_name=d["version_name"],
            download_url=d["download_url"],
            release_notes=notes,
            is_force=False,
            enabled=True
        )
        user_states.pop(user_id, None)
        msg = (
            f"🎉 <b>تم تفعيل ونشر التحديث الجديد للمستخدمين بنجاح!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔢 رقم الإصدار: <code>{d['version_code']}</code>\n"
            f"🏷️ اسم الإصدار: <b>{d['version_name']}</b>\n"
            f"📝 ملاحظات التحديث: <i>{notes}</i>\n"
            f"🔗 رابط التحميل المباشر: <code>{d['download_url']}</code>\n\n"
            f"سيظهر إشعار التحديث الجديد تلقائياً لجميع مستخدمي التطبيق فوراً بدون أي تأخير!"
        )
        bot.reply_to(message, msg, reply_markup=updates_menu_keyboard())
        return

    # 1. Universal Stream Link Processing
    if action == "wait_universal_link":
        bot.reply_to(message, "⏳ جاري فحص الرابط والصيغة (m3u8, ts, js, php, json)...")
        res = db.process_universal_link(text)

        if not res.get("success"):
            bot.reply_to(message, f"❌ {res.get('error', 'تعذر قراءة الرابط')}", reply_markup=cancel_keyboard())
            return

        res_type = res.get("type")

        # Multi-channel playlist or API
        if res_type in ["playlist_imported", "api_json_imported"]:
            user_states.pop(user_id, None)
            imported = res.get("channels_count", 0)
            total = res.get("total_channels", len(db.get_channels()))
            fmt = res.get("format", "stream").upper()
            msg = (
                f"🎉 <b>تم استيراد القنوات بنجاح بصيغة {fmt}!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📺 القنوات المضافة: <b>{imported}</b> قناة\n"
                f"📊 إجمالي القنوات في التطبيق: <b>{total}</b> قناة\n\n"
                f"أصبحت القنوات متاحة الآن مباشرة داخل التطبيق."
            )
            bot.reply_to(message, msg, reply_markup=channels_menu_keyboard())
            return

        # Direct single channel added
        if res_type == "single_channel_added":
            user_states.pop(user_id, None)
            bot.reply_to(message, f"✅ {res.get('message', 'تمت إضافة القناة بنجاح!')}", reply_markup=channels_menu_keyboard())
            return

        # Single stream needs name and category
        if res_type == "need_details":
            detected_fmt = res.get("format", "m3u8").upper()
            suggested = res.get("suggested_name", "قناة بث مباشر")
            state["action"] = "wait_univ_ch_name"
            state["data"] = {
                "url": res["url"],
                "format": detected_fmt,
                "suggested": suggested
            }
            prompt = (
                f"✅ <b>تم اكتشاف رابط بث مباشر بنجاح ({detected_fmt})!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔗 الرابط: <code>{res['url']}</code>\n\n"
                f"الخطوة 2 من 3: أرسل الآن <b>اسم القناة</b>\n"
                f"(مثال: <code>{suggested}</code>):"
            )
            bot.reply_to(message, prompt, reply_markup=cancel_keyboard())
            return

    # Universal Link Step 2: Channel Name
    if action == "wait_univ_ch_name":
        state["data"]["name"] = text
        state["action"] = "wait_univ_cat"
        cats = db.get_categories()
        prompt = (
            f"📺 اسم القناة: <b>{text}</b>\n\n"
            f"الخطوة 3 من 3: اختر <b>القسم</b> الذي تريد وضع القناة فيه:"
        )
        bot.reply_to(message, prompt, reply_markup=category_selection_keyboard("univ_cat_"))
        return

    # 2. Add Channel in Any Category Step 2: Name
    if action == "wait_picked_cat_ch_name":
        state["data"]["name"] = text
        state["action"] = "wait_picked_cat_ch_url"
        prompt = (
            f"📺 اسم القناة: <b>{text}</b>\n"
            f"📁 القسم: <b>{state['data']['categoryName']}</b>\n\n"
            f"الخطوة 3 من 3: أرسل الآن <b>رابط البث</b> للقناة:\n"
            f"<i>يدعم جميع الصيغ: m3u8, ts, js, php, json</i>\n"
            f"(مثال: <code>https://uruk.optikl.ink/ostora/main.php?id=4074&cat=331</code>):"
        )
        bot.reply_to(message, prompt, reply_markup=cancel_keyboard())
        return

    # Add Channel in Any Category Step 3: URL
    if action == "wait_picked_cat_ch_url":
        d = state["data"]
        ch = db.add_single_channel(
            name=d["name"],
            url=text,
            category_id=d["category"],
            category_name=d["categoryName"],
            quality="FHD"
        )
        user_states.pop(user_id, None)
        success_text = (
            f"🎉 <b>تمت إضافة القناة بنجاح في التطبيق!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📺 القناة: <b>{ch['name']}</b>\n"
            f"📁 القسم: <b>{ch['categoryName']}</b>\n"
            f"🔗 الرابط: <code>{ch['url']}</code>\n"
            f"✨ الجودة: <b>{ch['quality']}</b>\n\n"
            f"ستظهر القناة فوراً في تطبيق A2 TV بدون الحاجة لإعادة تشغيل!"
        )
        bot.reply_to(message, success_text, reply_markup=channels_menu_keyboard())
        return

    # 3. Add Category Wizard (Simple 1-step)
    if action in ["wait_cat_name_simple", "wait_cat_name_for_new_channel"]:
        cat_name = text
        # Auto-detect icon
        icon = "📁"
        lower_n = cat_name.lower()
        if "رياض" in cat_name or "sport" in lower_n or "كورة" in cat_name: icon = "⚽"
        elif "أفلام" in cat_name or "فيلم" in cat_name or "سينما" in cat_name or "movie" in lower_n: icon = "🎬"
        elif "مسلسل" in cat_name or "دراما" in cat_name: icon = "🎭"
        elif "أخبار" in cat_name or "news" in lower_n: icon = "🔴"
        elif "دين" in cat_name or "قرآن" in cat_name or "إسلام" in cat_name: icon = "🕋"
        elif "أطفال" in cat_name or "كرتون" in cat_name or "kids" in lower_n: icon = "🦁"
        elif "وثائق" in cat_name: icon = "🌍"
        elif "موسيقى" in cat_name: icon = "🎵"

        cat_id = cat_name.lower().replace(" ", "_")
        cat_id = re.sub(r'[^a-zA-Z0-9_\u0600-\u06FF]', '', cat_id) or f"cat_{int(time.time())}"

        res_cat = db.add_category(cat_id, cat_name, icon)
        if isinstance(res_cat, tuple):
            ok, new_cat = res_cat
        else:
            new_cat = res_cat
        
        # If user was adding channel on the fly
        if action == "wait_cat_name_for_new_channel":
            state["action"] = "wait_picked_cat_ch_name"
            state["data"] = {"category": new_cat["id"], "categoryName": new_cat["name"]}
            bot.reply_to(
                message,
                f"✅ تم إنشاء القسم: <b>{new_cat['icon']} {new_cat['name']}</b>\n\n"
                f"أرسل الآن <b>اسم القناة</b> لإضافتها في هذا القسم:",
                reply_markup=cancel_keyboard()
            )
            return

        user_states.pop(user_id, None)
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(types.InlineKeyboardButton(f"➕ إضافة قناة في قسم «{new_cat['name']}» الآن", callback_data=f"cat_pick_{new_cat['id']}"))
        kb.add(types.InlineKeyboardButton("📺 العودة لقسم القنوات", callback_data="menu_channels"))
        
        bot.reply_to(
            message,
            f"✅ <b>تمت إضافة القسم الجديد بنجاح!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📁 القسم: <b>{new_cat['icon']} {new_cat['name']}</b>\n"
            f"🆔 المعرف: <code>{new_cat['id']}</code>\n\n"
            f"أصبح القسم متاحاً الآن في التطبيق ويمكنك إضافة قنوات إليه فوراً.",
            reply_markup=kb
        )
        return

    # 4. Legacy PHP API JSON Importer
    if action == "wait_php_json":
        bot.reply_to(message, "⏳ جاري استيراد القنوات من PHP API JSON...")
        res = db.sync_php_json(text)
        user_states.pop(user_id, None)
        if res.get("success"):
            bot.reply_to(
                message,
                f"🎉 <b>تم استيراد القنوات بنجاح!</b>\n"
                f"📺 القنوات: <b>{res.get('channels_count', 0)}</b> | الأقسام: <b>{res.get('categories_count', 0)}</b>",
                reply_markup=channels_menu_keyboard()
            )
        else:
            bot.reply_to(message, f"❌ خطأ: {res.get('error', 'تعذر الاستيراد')}", reply_markup=channels_menu_keyboard())
        return

    # 5. Legacy M3U Importer
    if action == "wait_m3u_url":
        bot.reply_to(message, f"⏳ جاري فحص واستيراد القنوات من M3U...")
        count = db.sync_m3u_from_url(text)
        user_states.pop(user_id, None)
        if count >= 0:
            bot.reply_to(message, f"✅ تم استيراد <b>{count}</b> قناة بنجاح من رابط M3U!", reply_markup=channels_menu_keyboard())
        else:
            bot.reply_to(message, "❌ تعذر الاتصال بالرابط أو قراءة صيغة M3U.", reply_markup=channels_menu_keyboard())
        return

    # Channel Edit: Name
    if action == "wait_ch_edname":
        ch_id = state["data"]["id"]
        success, res = db.update_channel(ch_id, {"name": text})
        user_states.pop(user_id, None)
        if success:
            bot.reply_to(
                message,
                f"✅ <b>تم تعديل اسم القناة بنجاح في قاعدة البيانات والتطبيق!</b>\n"
                f"الاسم الجديد: <b>{text}</b>",
                reply_markup=channels_menu_keyboard()
            )
        else:
            bot.reply_to(message, f"❌ فشل تعديل اسم القناة: {res}", reply_markup=channels_menu_keyboard())
        return

    # Channel Edit: URL
    if action == "wait_ch_edurl":
        ch_id = state["data"]["id"]
        ch_name = state["data"].get("name", "القناة")
        stream_type = "hls"
        lower_u = text.lower()
        if ".mpd" in lower_u: stream_type = "dash"
        elif ".mp4" in lower_u: stream_type = "mp4"
        elif ".ts" in lower_u: stream_type = "ts"

        update_payload = {
            "url": text,
            "streamUrl": text,
            "servers": [{"name": "سيرفر البث المباشر", "url": text, "type": stream_type}]
        }
        success, res = db.update_channel(ch_id, update_payload)
        user_states.pop(user_id, None)
        if success:
            bot.reply_to(
                message,
                f"✅ <b>تم تعديل رابط القناة بنجاح!</b>\n"
                f"📺 القناة: <b>{ch_name}</b>\n"
                f"🔗 الرابط الجديد:\n<code>{text}</code>\n\n"
                f"يعمل الرابط الجديد فوراً داخل التطبيق بدون إعادة تثبيت.",
                reply_markup=channels_menu_keyboard()
            )
        else:
            bot.reply_to(message, f"❌ فشل تعديل رابط القناة: {res}", reply_markup=channels_menu_keyboard())
        return

    # Channel Edit: Logo
    if action == "wait_ch_edlogo":
        ch_id = state["data"]["id"]
        ch_name = state["data"].get("name", "القناة")
        success, res = db.update_channel_logo(ch_id, text)
        user_states.pop(user_id, None)
        if success:
            bot.reply_to(
                message,
                f"✅ <b>تم تحديث شعار القناة بنجاح!</b>\n"
                f"📺 القناة: <b>{ch_name}</b>\n"
                f"🖼️ الشعار الجديد: <b>{text}</b>",
                reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 عرض القناة", callback_data=f"ch_view_{ch_id}"))
            )
        else:
            bot.reply_to(message, f"❌ فشل تحديث الشعار: {res}")
        return

    # Channel Edit: Headers
    if action == "wait_ch_edheaders":
        ch_id = state["data"]["id"]
        ch_name = state["data"].get("name", "القناة")
        referer = ""
        useragent = ""
        if "referer:" in text.lower() or "useragent:" in text.lower() or "ua:" in text.lower():
            for part in text.split("|"):
                part = part.strip()
                if ":" in part:
                    k, v = part.split(":", 1)
                    k = k.strip().lower()
                    v = v.strip()
                    if k in ("referer", "ref"): referer = v
                    elif k in ("useragent", "ua", "user-agent"): useragent = v
        else:
            if text.startswith("http"):
                referer = text
            else:
                useragent = text

        success, res = db.update_channel_headers(ch_id, referer=referer, useragent=useragent)
        user_states.pop(user_id, None)
        if success:
            bot.reply_to(
                message,
                f"✅ <b>تم تحديث رؤوس البث (Headers) للقناة بنجاح!</b>\n"
                f"📺 القناة: <b>{ch_name}</b>\n"
                f"🌐 Referer: <code>{referer or 'بدون'}</code>\n"
                f"📱 User-Agent: <code>{useragent or 'تلقائي'}</code>",
                reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 عرض القناة", callback_data=f"ch_view_{ch_id}"))
            )
        else:
            bot.reply_to(message, f"❌ فشل حفظ الرؤوس: {res}")
        return

    # Channel Add Server / Quality URL
    if action == "wait_ch_addsrv_url":
        ch_id = state["data"]["id"]
        quality = state["data"]["quality"]
        ch = db.get_channel(ch_id)
        ch_name = ch.get("name", "القناة") if ch else "القناة"
        success, res = db.add_channel_server(ch_id, quality, text)
        user_states.pop(user_id, None)
        if success:
            bot.reply_to(
                message,
                f"✅ <b>تمت إضافة جودة ({quality}) بنجاح للقناة!</b>\n"
                f"📺 القناة: <b>{ch_name}</b>\n"
                f"✨ الجودة: <b>{quality}</b>\n"
                f"🔗 الرابط: <code>{text}</code>\n\n"
                f"ستظهر هذه الجودة الآن في قائمة اختيار الجودات داخل التطبيق.",
                reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 إدارة السيرفرات", callback_data=f"ch_srvs_{ch_id}"))
            )
        else:
            bot.reply_to(message, f"❌ فشلت الإضافة: {res}")
        return

    # Smart Channel Search
    if action == "wait_channel_search":
        query = text.strip()
        results = db.search_channels(query)
        user_states.pop(user_id, None)
        if not results:
            kb = types.InlineKeyboardMarkup(row_width=1)
            kb.add(types.InlineKeyboardButton("🔍 بحث مجدداً", callback_data="ch_search_prompt"))
            kb.add(types.InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu"))
            bot.reply_to(
                message,
                f"❌ <b>لم يتم العثور على أي قناة تطابق:</b> «<code>{query}</code>»\n\n"
                f"تأكد من كتابة الاسم بشكل صحيح أو جرب البحث بكلمة أقصر.",
                reply_markup=kb
            )
            return

        kb = types.InlineKeyboardMarkup(row_width=1)
        for ch in results[:10]:
            name_label = ch.get('name', 'قناة')
            cat_label = ch.get('categoryName', 'عام')
            qual_label = ch.get('quality', 'FHD')
            dis_dot = "🔴 " if ch.get("disabled", False) else "🟢 "
            kb.add(types.InlineKeyboardButton(f"{dis_dot}{name_label} | {cat_label} [{qual_label}]", callback_data=f"ch_view_{ch['id']}"))

        if len(results) > 10:
            kb.add(types.InlineKeyboardButton(f"➕ عرض بقية النتائج ({len(results)} قناة)", callback_data="ch_list_0"))

        kb.add(types.InlineKeyboardButton("🔍 بحث آخر", callback_data="ch_search_prompt"))
        kb.add(types.InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu"))

        bot.reply_to(
            message,
            f"🔍 <b>نتائج البحث عن «{query}» ({len(results)} قناة):</b>\n"
            f"اضغط على أي قناة لعرض تفاصيلها أو تعديلها أو فحص رابطها:",
            reply_markup=kb
        )
        return

    # Category Edit: Name
    if action == "wait_cat_edname":
        cat_id = state["data"]["id"]
        success, res = db.update_category(cat_id, new_name=text)
        user_states.pop(user_id, None)
        if success:
            bot.reply_to(
                message,
                f"✅ <b>تم تعديل اسم القسم بنجاح!</b>\n"
                f"📁 الاسم الجديد: <b>{text}</b>\n"
                f"تم تحديث جميع القنوات التابعة لهذا القسم تلقائياً في قاعدة البيانات.",
                reply_markup=channels_menu_keyboard()
            )
        else:
            bot.reply_to(message, f"❌ فشل تعديل اسم القسم: {res}", reply_markup=channels_menu_keyboard())
        return

    # Category Edit: Icon
    if action == "wait_cat_edicon":
        cat_id = state["data"]["id"]
        cat_name = state["data"].get("name", "القسم")
        success, res = db.update_category(cat_id, new_icon=text)
        user_states.pop(user_id, None)
        if success:
            bot.reply_to(
                message,
                f"✅ <b>تم تحديث أيقونة القسم بنجاح!</b>\n"
                f"📁 القسم: <b>{text} {cat_name}</b>",
                reply_markup=channels_menu_keyboard()
            )
        else:
            bot.reply_to(message, f"❌ فشل تحديث أيقونة القسم: {res}", reply_markup=channels_menu_keyboard())
        return

    # API Add Step 1: Name -> Ask URL
    if action == "wait_api_name":
        state["data"]["name"] = text
        state["action"] = "wait_api_url"
        bot.reply_to(
            message,
            f"🏷️ اسم السيرفر: <b>{text}</b>\n\n"
            f"الخطوة 2 من 3: أرسل الآن <b>رابط الـ API</b>\n"
            f"(مثال: <code>https://example.com/api/channels.php</code> أو رابط M3U):",
            reply_markup=cancel_keyboard()
        )
        return

    # API Add Step 2: URL -> Ask Type
    if action == "wait_api_url":
        state["data"]["url"] = text
        state["action"] = "wait_api_type"
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("PHP API JSON 🌐", callback_data="api_settype_php_json"),
            types.InlineKeyboardButton("M3U Playlist 📻", callback_data="api_settype_m3u")
        )
        kb.add(types.InlineKeyboardButton("❌ إلغاء", callback_data="cancel_action"))
        bot.reply_to(
            message,
            f"🔗 الرابط: <code>{text}</code>\n\n"
            f"الخطوة 3 من 3: اختر <b>نوع السيرفر أو الـ API</b>:",
            reply_markup=kb
        )
        return

    # API Edit: Name
    if action == "wait_api_edname":
        api_id = state["data"]["id"]
        success, res = db.update_channel_api(api_id, name=text)
        user_states.pop(user_id, None)
        if success:
            bot.reply_to(
                message,
                f"✅ <b>تم تعديل اسم سيرفر الـ API بنجاح!</b>\n"
                f"الاسم الجديد: <b>{text}</b>",
                reply_markup=apis_menu_keyboard()
            )
        else:
            bot.reply_to(message, f"❌ فشل التعديل: {res}", reply_markup=apis_menu_keyboard())
        return

    # API Edit: URL
    if action == "wait_api_edurl":
        api_id = state["data"]["id"]
        api_name = state["data"].get("name", "السيرفر")
        success, res = db.update_channel_api(api_id, url=text)
        user_states.pop(user_id, None)
        if success:
            bot.reply_to(
                message,
                f"✅ <b>تم تعديل رابط سيرفر الـ API بنجاح!</b>\n"
                f"🌐 السيرفر: <b>{api_name}</b>\n"
                f"🔗 الرابط الجديد:\n<code>{text}</code>",
                reply_markup=apis_menu_keyboard()
            )
        else:
            bot.reply_to(message, f"❌ فشل التعديل: {res}", reply_markup=apis_menu_keyboard())
        return

    # 6. Maintenance Message with Disk Verification
    if action == "wait_maint_msg":
        success, m_data = db.set_maintenance(True, text, admin_id=user_id)
        user_states.pop(user_id, None)
        if success:
            bot.reply_to(
                message,
                f"✅ <b>تم التحقق وحفظ رسالة الصيانة في قاعدة البيانات وتفعيل الوضع بنجاح!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💬 الرسالة المعروضة للمستخدمين:\n"
                f"<i>\"{text}\"</i>\n\n"
                f"تظهر الرسالة فوراً داخل تطبيق A2 TV ويتم قفل البث للمستخدمين.",
                reply_markup=back_to_main_keyboard()
            )
        else:
            bot.reply_to(
                message,
                f"❌ <b>فشل حفظ رسالة الصيانة:</b> {m_data}",
                reply_markup=back_to_main_keyboard()
            )
        return

    # 7. App Update Wizard
    if action == "wait_up_version_code":
        try:
            v_code = int(text)
            state["data"] = {"version_code": v_code}
            state["action"] = "wait_up_version_name"
            bot.reply_to(message, "الخطوة 2 من 4: أرسل <b>اسم الإصدار (Version Name)</b> (مثال: <code>2.0.0</code>):", reply_markup=cancel_keyboard())
        except ValueError:
            bot.reply_to(message, "⚠️ يرجى إدخال رقم صحيح للإصدار (مثال: <code>3</code>):")
        return

    if action == "wait_up_version_name":
        state["data"]["version_name"] = text
        state["action"] = "wait_up_url"
        bot.reply_to(message, "الخطوة 3 من 4: أرسل <b>رابط تحميل ملف APK المباشر</b>:\n(مثال: <code>https://my-server.com/app-v2.apk</code>):", reply_markup=cancel_keyboard())
        return

    if action == "wait_up_url":
        state["data"]["download_url"] = text
        state["action"] = "wait_up_notes"
        bot.reply_to(message, "الخطوة 4 من 4: أرسل <b>ملاحظات ومميزات التحديث</b> للمستخدمين:", reply_markup=cancel_keyboard())
        return

    if action == "wait_up_notes":
        state["data"]["release_notes"] = text
        d = state["data"]
        db.set_app_update(
            version_code=d["version_code"],
            version_name=d["version_name"],
            download_url=d["download_url"],
            release_notes=d["release_notes"],
            is_force=False,
            enabled=True
        )
        user_states.pop(user_id, None)
        success_text = (
            f"🎉 <b>تم نشر التحديث الجديد بنجاح!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔢 رقم الإصدار: <code>{d['version_code']}</code>\n"
            f"🏷️ الاسم: <b>{d['version_name']}</b>\n"
            f"🔗 الرابط: <code>{d['download_url']}</code>\n"
            f"📝 المميزات: <i>{d['release_notes']}</i>\n\n"
            f"سيظهر إشعار التحديث تلقائياً داخل التطبيق لجميع المستخدمين."
        )
        bot.reply_to(message, success_text, reply_markup=back_to_main_keyboard())
        return

    # 8. Add Admin Wizard
    if action == "wait_admin_id":
        try:
            aid = int(text)
            state["data"] = {"id": aid}
            state["action"] = "wait_admin_name"
            bot.reply_to(message, "الخطوة 2 من 3: أرسل <b>اسم المشرف</b>:", reply_markup=cancel_keyboard())
        except ValueError:
            bot.reply_to(message, "⚠️ يرجى إرسال آيدي رقمي صحيح (مثال: <code>123456789</code>):")
        return

    if action == "wait_admin_name":
        state["data"]["name"] = text
        kb = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        kb.add("👑 كل الصلاحيات")
        kb.add("📺 إدارة القنوات فقط")
        kb.add("🛠️ وضع الصيانة فقط")
        kb.add("🔄 التحديثات فقط")
        state["action"] = "wait_admin_perms"
        bot.reply_to(message, "الخطوة 3 من 3: اختر <b>صلاحيات المشرف</b>:", reply_markup=kb)
        return

    if action == "wait_admin_perms":
        perm_map = {
            "👑 كل الصلاحيات": ["all"],
            "📺 إدارة القنوات فقط": ["channels"],
            "🛠️ وضع الصيانة فقط": ["maintenance"],
            "🔄 التحديثات فقط": ["updates"]
        }
        perms = perm_map.get(text, ["all"])
        d = state["data"]
        db.add_admin(d["id"], d["name"], perms)
        user_states.pop(user_id, None)
        bot.reply_to(message, f"✅ تم تعيين <b>{d['name']}</b> مشرفاً بنجاح!\n🆔 الآيدي: <code>{d['id']}</code>\nالصلاحيات: <code>{', '.join(perms)}</code>", reply_markup=types.ReplyKeyboardRemove())
        bot.send_message(message.chat.id, "العودة للقائمة الرئيسية:", reply_markup=back_to_main_keyboard())
        return

def run_bot():
    if not BOT_INITIALIZED or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("⚠️ [Telegram Bot]: لم يتم تعيين BOT_TOKEN في ملف telegram_bot/.env حتى الآن.")
        print("ℹ️ السيرفر والـ API يعملان وجاهزان لربط التطبيق. لتفعيل البوت، أدخل التوكن والآيدي في .env")
        return
    print("🤖 Telegram Bot is starting polling...")
    while True:
        try:
            bot.infinity_polling(timeout=25, long_polling_timeout=25)
        except Exception as e:
            logger.error("Telegram bot polling encountered an error: %s. Reconnecting in 5s...", e)
            time.sleep(5)

if __name__ == "__main__":
    run_bot()
