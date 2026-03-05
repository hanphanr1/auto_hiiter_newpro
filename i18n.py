# -*- coding: utf-8 -*-
"""Internationalization module — EN / VI language support."""

_user_lang: dict[int, str] = {}

PROOF_LINK = "https://t.me/tptth_proof"
BRAND = "TPTTH PRIVATE HITTER"
BY = "by @idkbroo_fr"
SEP = "━━━━━━━━━━━━━━━━━━━━━━━━━━"


def set_lang(uid: int, lang: str):
    _user_lang[uid] = lang


def get_lang(uid: int) -> str:
    return _user_lang.get(uid, "")


def t(uid: int, key: str, **kw) -> str:
    lang = get_lang(uid) or "en"
    texts = _TEXTS.get(lang, _TEXTS["en"])
    s = texts.get(key, _TEXTS["en"].get(key, key))
    return s.format(**kw) if kw else s


_HEADER = (
    f"╔{'═' * 28}╗\n"
    f"    ⚡ <b>{BRAND}</b> ⚡\n"
    f"╚{'═' * 28}╝"
)

_FOOTER = (
    f"\n📢 <b>Proof:</b> <a href=\"{PROOF_LINK}\">t.me/tptth_proof</a>\n"
    f"{SEP}\n"
    f"      ⚡ <b>{BY}</b> ⚡\n"
    f"{SEP}"
)

_TEXTS = {
    "en": {
        "lang_set": "✅ Language set to English!",

        "help": (
            f"{_HEADER}\n\n"
            "🔶 <b>CC FILTER</b>\n"
            "  ├ Send <b>.txt file</b> → Filter <code>cc|mm|yy|cvv</code>\n"
            "  ├ Send <b>text</b> with CC → Reply CC lines\n"
            "  └ Auto-detect all formats\n\n"
            "🔶 <b>AUTO HITTER</b>\n"
            "  ├ <code>/co &lt;url&gt;</code> — Parse checkout\n"
            "  ├ <code>/co &lt;url&gt; cc|mm|yy|cvv</code> — Hit 1 card\n"
            "  ├ <code>/co &lt;url&gt; bin &lt;BIN&gt; [n]</code> — Gen &amp; hit\n"
            "  └ Auto retry + Anti-fraud bypass\n\n"
            "🔶 <b>PROXY</b>\n"
            "  ├ <code>/addproxy host:port:user:pass</code>\n"
            "  ├ <code>/removeproxy all</code> — Remove all\n"
            "  ├ <code>/proxy</code> — List | <code>/proxy check</code>\n"
            "  └ Auto-rotate when hitting"
            f"{_FOOTER}"
        ),

        "co_usage": (
            f"{_HEADER}\n\n"
            "🔹 <code>/co &lt;url&gt;</code> — Parse checkout\n"
            "🔹 <code>/co &lt;url&gt; cc|mm|yy|cvv</code> — Hit 1 card\n"
            "🔹 <code>/co &lt;url&gt; bin &lt;BIN&gt; [n]</code> — Gen &amp; hit\n\n"
            "Proxy auto from <code>/addproxy</code>"
            f"{_FOOTER}"
        ),
        "co_parsing": "⏳ Parsing checkout…\n🔌 {proxy}",
        "co_error": f"{SEP}\n❌ <b>Error</b>\n{{error}}\n{SEP}",
        "co_hitting": (
            f"{SEP}\n"
            "🔄 Hitting <b>{price}</b> — {count} cards ({mode})\n"
            "🔌 {proxy}\n"
            "⏳ Checking card #1…\n"
            f"{SEP}"
        ),
        "co_checking": "⏳ Checking card #{n}…",
        "co_all_done": "✅ All cards processed",
        "co_charged_title": "🟢 <b>CHARGED SUCCESSFULLY</b>",
        "co_3ds_stop_title": "🔐 <b>STOP — Site requires 3DS</b>",
        "co_3ds_body": (
            "⚠️ This site requires <b>3D Secure (OTP)</b>.\n"
            "Bot cannot auto-enter bank OTP.\n\n"
            "🔹 Tried: {tried} cards — all 3DS\n"
            "🔹 Remaining: {remaining} cards — <b>skipped</b>\n\n"
            "💡 <i>Try another site without 3DS, use better BINs, or re-send the link.</i>"
        ),
        "co_session_dead_title": "STOP — Checkout Session Dead",
        "co_session_dead_body": (
            "⚠️ The checkout session has been <b>canceled/expired</b>.\n"
            "No more cards can be processed on this link.\n\n"
            "🔹 Tried: {tried} cards\n"
            "🔹 Remaining: {remaining} cards — <b>skipped</b>\n\n"
            "💡 <i>Please generate a new checkout link and try again.</i>"
        ),
        "filter_error": "❌ Cannot read file: {error}",
        "filter_no_cc": "❌ No CC found in file.",
        "filter_result": "✅ Filtered <b>{count}</b> CC from <code>{file}</code>",
        "filter_text_result": "✅ <b>{count}</b> CC found",
        "proxy_checking": "⏳ Checking {count} proxies…",
        "proxy_no_valid": "❌ No valid proxy provided.",
        "proxy_removed_all": "✅ Removed all <b>{count}</b> proxies.",
        "proxy_removed": "✅ Removed <code>{proxy}</code>",
        "proxy_not_found": "❌ Proxy not found.",
        "proxy_empty": "❌ No proxies yet. Add with /addproxy",
        "proxy_title": "Proxy",
        "proxy_add_title": "Add Proxy",
        "proxy_check_title": "Proxy Check",
        "proxy_rm_title": "Remove Proxy",
        "proxy_alive": "Alive",
        "proxy_dead": "Dead",
        "proxy_added": "Added",
        "proxy_your_proxies": "Your Proxies",
        "proxy_check_all": "check all",

        "co_checkout_parsed": "Checkout Parsed",
        "filter_title": "CC Filter",

        "merchant": "Merchant",
        "product": "Product",
        "country": "Country",
        "mode": "Mode",
        "cards_label": "Cards",
        "process_by": "Process by",
    },
    "vi": {
        "lang_set": "✅ Đã chọn Tiếng Việt!",

        "help": (
            f"{_HEADER}\n\n"
            "🔶 <b>LỌC CC</b>\n"
            "  ├ Gửi <b>file .txt</b> → Lọc <code>cc|mm|yy|cvv</code>\n"
            "  ├ Gửi <b>text</b> có CC → Reply dòng CC\n"
            "  └ Tự nhận diện mọi format\n\n"
            "🔶 <b>AUTO HITTER</b>\n"
            "  ├ <code>/co &lt;url&gt;</code> — Parse checkout\n"
            "  ├ <code>/co &lt;url&gt; cc|mm|yy|cvv</code> — Hit 1 thẻ\n"
            "  ├ <code>/co &lt;url&gt; bin &lt;BIN&gt; [n]</code> — Gen &amp; hit\n"
            "  └ Auto retry + Bypass anti-fraud\n\n"
            "🔶 <b>PROXY</b>\n"
            "  ├ <code>/addproxy host:port:user:pass</code>\n"
            "  ├ <code>/removeproxy all</code> — Xóa tất cả\n"
            "  ├ <code>/proxy</code> — Xem | <code>/proxy check</code>\n"
            "  └ Tự xoay khi hit"
            f"{_FOOTER}"
        ),

        "co_usage": (
            f"{_HEADER}\n\n"
            "🔹 <code>/co &lt;url&gt;</code> — Parse checkout\n"
            "🔹 <code>/co &lt;url&gt; cc|mm|yy|cvv</code> — Hit 1 thẻ\n"
            "🔹 <code>/co &lt;url&gt; bin &lt;BIN&gt; [n]</code> — Gen &amp; hit\n\n"
            "Proxy tự động từ <code>/addproxy</code>"
            f"{_FOOTER}"
        ),
        "co_parsing": "⏳ Đang parse checkout…\n🔌 {proxy}",
        "co_error": f"{SEP}\n❌ <b>Lỗi</b>\n{{error}}\n{SEP}",
        "co_hitting": (
            f"{SEP}\n"
            "🔄 Đang hit <b>{price}</b> — {count} thẻ ({mode})\n"
            "🔌 {proxy}\n"
            "⏳ Đang check thẻ #1…\n"
            f"{SEP}"
        ),
        "co_checking": "⏳ Đang check thẻ #{n}…",
        "co_all_done": "✅ Đã xử lý tất cả thẻ",
        "co_charged_title": "🟢 <b>CHARGE THÀNH CÔNG</b>",
        "co_3ds_stop_title": "🔐 <b>DỪNG — Site yêu cầu 3DS</b>",
        "co_3ds_body": (
            "⚠️ Site này bắt <b>3D Secure (OTP)</b>.\n"
            "Bot không thể tự nhập mã OTP ngân hàng.\n\n"
            "🔹 Đã thử: {tried} thẻ — tất cả 3DS\n"
            "🔹 Còn lại: {remaining} thẻ — <b>bỏ qua</b>\n\n"
            "💡 <i>Thử site khác không bật 3DS hoặc dùng BIN xịn hơn hoặc gửi lại link nhé.</i>"
        ),
        "co_session_dead_title": "DỪNG — Checkout Session Đã Chết",
        "co_session_dead_body": (
            "⚠️ Checkout session đã bị <b>hủy/hết hạn</b>.\n"
            "Không thể xử lý thêm thẻ nào trên link này.\n\n"
            "🔹 Đã thử: {tried} thẻ\n"
            "🔹 Còn lại: {remaining} thẻ — <b>bỏ qua</b>\n\n"
            "💡 <i>Vui lòng tạo link checkout mới và thử lại.</i>"
        ),
        "filter_error": "❌ Không đọc được file: {error}",
        "filter_no_cc": "❌ Không tìm thấy CC nào trong file.",
        "filter_result": "✅ Lọc ra <b>{count}</b> CC từ <code>{file}</code>",
        "filter_text_result": "✅ Tìm thấy <b>{count}</b> CC",
        "proxy_checking": "⏳ Đang check {count} proxy…",
        "proxy_no_valid": "❌ Không có proxy hợp lệ.",
        "proxy_removed_all": "✅ Đã xóa tất cả <b>{count}</b> proxy.",
        "proxy_removed": "✅ Đã xóa <code>{proxy}</code>",
        "proxy_not_found": "❌ Không tìm thấy proxy.",
        "proxy_empty": "❌ Chưa có proxy. Thêm bằng /addproxy",
        "proxy_title": "Proxy",
        "proxy_add_title": "Thêm Proxy",
        "proxy_check_title": "Kiểm Tra Proxy",
        "proxy_rm_title": "Xóa Proxy",
        "proxy_alive": "Sống",
        "proxy_dead": "Chết",
        "proxy_added": "Đã thêm",
        "proxy_your_proxies": "Proxy của bạn",
        "proxy_check_all": "kiểm tra tất cả",

        "co_checkout_parsed": "Đã Parse Checkout",
        "filter_title": "Lọc CC",

        "merchant": "Merchant",
        "product": "Sản phẩm",
        "country": "Quốc gia",
        "mode": "Loại",
        "cards_label": "Thẻ",
        "process_by": "Xử lý bởi",
    },
}
