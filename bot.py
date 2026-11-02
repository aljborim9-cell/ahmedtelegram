"""
Telegram Bot Control Panel for A2 TV App.
Provides interactive management for Channels, Categories, Stream Links (m3u8, ts, js, php, json), APK Updates, Maintenance Mode, and Admins.
"""

import telebot
from telebot import types
import json
import time
import re
from config import BOT_TOKEN, ADMIN_ID, API_HOST, API_PORT, APP_PACKAGE
from database import db

# Safe initialization for Bot
BOT_INITIALIZED = False
if BOT_TOKEN and ":" in BOT_TOKEN and BOT_TOKEN != "YOUR_TELEGRAM_BOT_TOKEN_HERE":
    try:
        bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
        BOT_INITIALIZED = True
    except Exception:
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
        return False
    if permission:
        return db.has_permission(user_id, permission)
    return True

# ----------------- Keyboard Generators -----------------

def main_menu_keyboard(user_id):
    kb = types.InlineKeyboardMarkup(row_width=2)
    b_links = types.InlineKeyboardButton("🔗 إضافة روابط قنوات (m3u8, ts, js, php, json)", callback_data="ch_universal_link")
    b_add_ch = types.InlineKeyboardButton("➕ إضافة قناة في أي قسم", callback_data="ch_add_select_cat")
    b_add_cat = types.InlineKeyboardButton("📁 إضافة قسم جديد", callback_data="cat_add")
    
    b_channels = types.InlineKeyboardButton("📺 إدارة القنوات والأقسام", callback_data="menu_channels")
    b_stats = types.InlineKeyboardButton("📊 حالة السيرفر والإحصائيات", callback_data="menu_stats")
    
    b_updates = types.InlineKeyboardButton("🔄 تحديث التطبيق APK", callback_data="menu_updates")
    b_maint = types.InlineKeyboardButton("🛠️ وضع الصيانة", callback_data="menu_maint")
    b_admins = types.InlineKeyboardButton("👥 إدارة المشرفين", callback_data="menu_admins")
    
    kb.add(b_links)
    kb.row(b_add_ch, b_add_cat)
    kb.row(b_channels, b_stats)
    kb.row(b_updates, b_maint)
    kb.add(b_admins)
    return kb

def channels_menu_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    b_links = types.InlineKeyboardButton("🔗 إضافة روابط قنوات (m3u8, ts, js, php, json)", callback_data="ch_universal_link")
    b_add_to_cat = types.InlineKeyboardButton("➕ إضافة قناة في أي قسم", callback_data="ch_add_select_cat")
    b_add_cat = types.InlineKeyboardButton("📁 إضافة قسم جديد", callback_data="cat_add")
    
    b_php = types.InlineKeyboardButton("🌐 استيراد PHP API JSON", callback_data="ch_import_php")
    b_m3u = types.InlineKeyboardButton("📻 استيراد رابط M3U", callback_data="ch_import_m3u")
    
    b_list_ch = types.InlineKeyboardButton("📋 عرض وحذف القنوات", callback_data="ch_list_0")
    b_list_cat = types.InlineKeyboardButton("🗂️ عرض وحذف الأقسام", callback_data="cat_list")
    
    b_del_all = types.InlineKeyboardButton("🗑️ تفريغ وحذف جميع القنوات", callback_data="ch_del_all_confirm")
    b_back = types.InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")
    
    kb.add(b_links)
    kb.row(b_add_to_cat, b_add_cat)
    kb.row(b_php, b_m3u)
    kb.row(b_list_ch, b_list_cat)
    kb.add(b_del_all)
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
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=channels_menu_keyboard())
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
            kb.add(types.InlineKeyboardButton(f"🗑️ حذف: {ch.get('name', 'قناة')} ({ch.get('categoryName', 'عام')})", callback_data=f"ch_del_{ch['id']}"))

        nav_row = []
        if page > 0:
            nav_row.append(types.InlineKeyboardButton("⬅️ السابق", callback_data=f"ch_list_{page-1}"))
        nav_row.append(types.InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_row.append(types.InlineKeyboardButton("التالي ➡️", callback_data=f"ch_list_{page+1}"))
        if nav_row:
            kb.row(*nav_row)

        kb.add(types.InlineKeyboardButton("🔙 رجوع لقسم القنوات", callback_data="menu_channels"))
        text = f"📋 <b>قائمة القنوات المسجلة ({len(channels)} قناة)</b>\nاضغط على أي قناة لحذفها:"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    # Delete Channel Action
    if data.startswith("ch_del_"):
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        ch_id = data[len("ch_del_"):]
        ch = db.get_channel(ch_id)
        ch_name = ch.get("name") if ch else ch_id
        db.delete_channel(ch_id)
        bot.answer_callback_query(call.id, f"تم حذف: {ch_name}", show_alert=True)
        call.data = "ch_list_0"
        handle_callback(call)
        return

    # Category List
    if data == "cat_list":
        cats = db.get_categories()
        if len(cats) == 0:
            text = "🗂️ <b>لا توجد أقسام مسجلة حالياً.</b>"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=channels_menu_keyboard())
            bot.answer_callback_query(call.id)
            return
        kb = types.InlineKeyboardMarkup(row_width=1)
        for c in cats:
            ch_in_cat = len(db.get_channels(c["id"]))
            kb.add(types.InlineKeyboardButton(f"🗑️ حذف: {c.get('icon', '📁')} {c.get('name')} ({ch_in_cat} قناة)", callback_data=f"cat_del_{c['id']}"))
        kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="menu_channels"))
        text = f"🗂️ <b>قائمة الأقسام الحالية ({len(cats)} قسم)</b>\nاضغط على أي قسم لحذفه:"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    # Delete Category Action
    if data.startswith("cat_del_"):
        if not check_admin(user_id, "channels"):
            bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
            return
        cat_id = data[len("cat_del_"):]
        db.delete_category(cat_id)
        bot.answer_callback_query(call.id, "تم حذف القسم بنجاح", show_alert=True)
        call.data = "cat_list"
        handle_callback(call)
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
        db.set_maintenance(new_state)
        alert_msg = "🔴 تم تفعيل وضع الصيانة!" if new_state else "🟢 تم إيقاف وضع الصيانة وعاد التطبيق للعمل!"
        bot.answer_callback_query(call.id, alert_msg, show_alert=True)
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
            f"🌐 خادم الـ API: <code>http://{API_HOST}:{API_PORT}</code>\n"
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

        new_cat = db.add_category(cat_id, cat_name, icon)
        
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

    # 6. Maintenance Message
    if action == "wait_maint_msg":
        db.set_maintenance(True, text)
        user_states.pop(user_id, None)
        bot.reply_to(message, f"✅ تم تحديث رسالة الصيانة وتفعيل الوضع:\n<i>\"{text}\"</i>", reply_markup=back_to_main_keyboard())
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
    bot.infinity_polling(timeout=20, long_polling_timeout=20)

if __name__ == "__main__":
    run_bot()
