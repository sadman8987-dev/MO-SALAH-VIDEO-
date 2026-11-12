T = {
    "ar": {
        "start": (
            "👋 أهلاً <b>{name}</b>!\n\n"
            "ابعتلي <b>رابط</b> أي فيديو أو صورة أو ملف وأنا أنزّله، أو اكتب <b>اسم</b> أغنية/فيديو وأنا أدوّر عليه في يوتيوب 🔎\n\n"
            "✅ يوتيوب • تيك توك • انستجرام • فيسبوك • تويتر/X • ريديت • بنترست • "
            "ساوند كلاود • تويتش • فيميو • وأكتر من 1000 موقع.\n\n"
            "✨ جودات متعددة • MP3/M4A/FLAC/WAV • فويس • دايرة فيديو • GIF • ترجمات • قص مقاطع • "
            "قوائم تشغيل • اشتراك في قنوات • تحويل ملفاتك لـ MP3\n\n"
            "⚙️ /settings  📜 /history  🔔 /subscriptions  🎁 /invite  👤 /me  ❓ /help"
        ),
        "help": (
            "📖 <b>طريقة الاستخدام</b>\n\n"
            "🔗 ابعت رابط (أو لحد {links} روابط) ← اختار الجودة أو الصوت.\n"
            "🔎 اكتب اسم أغنية/فيديو ← اختار من نتايج البحث.\n"
            "🎵 صيغ الصوت: MP3 (128/192/320) • M4A • OPUS • FLAC • WAV • 🎤 فويس.\n"
            "⭕ «دايرة فيديو» (60ث) و 🎞 «GIF» (30ث) من أي فيديو.\n"
            "📚 رابط قائمة تشغيل ← حمّل الكل فيديو أو MP3 (/stop للإيقاف).\n"
            "📝 «الترجمة» ← ملف SRT بأي لغة متاحة.\n"
            "✂️ «قص مقطع» ← حدد البداية والنهاية.\n"
            "🖼 روابط الصور/الألبومات (انستجرام، بنترست...) وروابط الملفات المباشرة (PDF, ZIP, APK...) مدعومة.\n"
            "🎧 ابعت لي أي فيديو/صوت/فويس ← أحوّله MP3.\n\n"
            "🔔 <code>/subscribe رابط_قناة</code> ← إشعار بكل فيديو جديد • /subscriptions لإدارتها.\n"
            "🎁 /invite ادعُ أصحابك واكسب أيام مميزة • 💎 /buy اشتراك مميز.\n"
            "📜 /history آخر تحميلاتك • 👤 /me حسابك • ⚙️ /settings الإعدادات.\n"
            "👥 في الجروبات: <code>/dl الرابط</code> أو <code>/search الاسم</code>\n"
            "🌐 Inline: اكتب @اسم_البوت ثم اسم الأغنية في أي محادثة.\n\n"
            "• <b>تلقائي</b> = أعلى جودة تناسب حد الرفع.\n"
            "• الملفات الأكبر من الحد بتتقسّم أو بتتضغط (حسب الإعدادات).\n\n"
            "⚠️ الحد الأقصى للجزء: <b>{limit}</b>"
        ),
        "analyzing": "🔎 جاري تحليل الرابط...",
        "card": "🎞 <b>{title}</b>\n{meta}\n\nاختار الصيغة المطلوبة 👇",
        "queue": "⏳ في الطابور... هيبدأ التحميل حالاً.",
        "starting": "⏳ جاري التجهيز...",
        "downloading": "⬇️ <b>جاري التحميل</b>\n{bar} {pct}%\n🚀 {speed}  •  ⏱ {eta}",
        "processing": "⚙️ جاري المعالجة والدمج...",
        "compressing": "🗜 الملف كبير، جاري ضغطه ليناسب الحد... (ممكن ياخد شوية وقت)",
        "splitting": "✂️ الملف كبير، جاري تقسيمه لأجزاء...",
        "part": "الجزء",
        "join_parts": "ℹ️ لتجميع الأجزاء: حمّلها كلها في نفس الفولدر ثم استخدم 7-Zip أو الأمر <code>cat اسم_الملف.* &gt; اسم_الملف</code>",
        "uploading": "📤 جاري الرفع إلى تليجرام...",
        "gallery_try": "🖼 جاري تحميل الصور/الوسائط...",
        "err_generic": "❌ حصلت مشكلة:\n<code>{reason}</code>\n\nجرّب رابط تاني أو حاول بعد شوية.",
        "err_toobig": "⚠️ الملف أكبر من الحد المسموح ({limit}) حتى بعد التقسيم.\nاختار جودة أقل أو صوت MP3.",
        "err_live": "📡 البث المباشر مش مدعوم. استنى لما يخلص وجرّب تاني.",
        "err_long": "⏱ الفيديو أطول من الحد المسموح ({limit}).",
        "err_quota": "🚫 وصلت للحد اليومي ({limit} تحميل). جرّب بكرة، أو اكسب أيام مميزة بـ /invite أو /buy 💎",
        "busy": "⏳ عندك تحميلات شغالة بالفعل، استنى لما تخلص.",
        "maintenance": "🛠 البوت في صيانة دلوقتي، جرّب بعد شوية.",
        "invalid_url": "🚫 الرابط غير صالح أو غير مسموح.",
        "no_url": "🔗 ابعت رابط أو اسم للبحث.",
        "dl_usage": "الاستخدام: <code>/dl الرابط</code>",
        "search_usage": "الاستخدام: <code>/search اسم الأغنية أو الفيديو</code>",
        "join": "📢 لازم تشترك في القناة الأول عشان تستخدم البوت، وبعدها اضغط «تحقق».",
        "btn_join": "📢 اشترك في القناة",
        "btn_check": "✅ تحقق",
        "not_joined": "لسه مشتركتش في القناة!",
        "expired": "انتهت صلاحية الطلب، ابعت الرابط من جديد.",
        "not_yours": "الزرار ده مش بتاعك 🙂",
        "btn_auto": "⚡ تلقائي (أفضل جودة مناسبة)",
        "btn_thumb": "🖼 الصورة المصغرة",
        "btn_subs": "📝 الترجمة",
        "btn_clip": "✂️ قص مقطع",
        "btn_voice": "🎤 فويس",
        "btn_note": "⭕ دايرة فيديو",
        "btn_gif": "🎞 GIF",
        "btn_back": "‹ رجوع",
        "btn_cancel": "❌ إلغاء",
        "settings": (
            "⚙️ <b>الإعدادات</b>\n\n🌐 اللغة\n🎯 التحميل الافتراضي عند إرسال رابط\n"
            "📦 لو الملف أكبر من الحد: تقسيم لأجزاء أو ضغط\n📎 إرسال الفيديو كملف (جودة أصلية)"
        ),
        "pref_ask": "❓ اسألني كل مرة",
        "pref_best": "⚡ تلقائي (أفضل جودة)",
        "pref_720": "🎬 فيديو حتى 720p",
        "pref_480": "🎬 فيديو حتى 480p",
        "pref_audio": "🎵 صوت MP3 فقط",
        "big_split": "✂️ تقسيم",
        "big_compress": "🗜 ضغط",
        "doc_on": "📎 الإرسال كملف: ✅ شغال",
        "doc_off": "📎 الإرسال كملف: ❌ مقفول",
        "saved": "✅ تم الحفظ",
        "unknown_kind": "طلب غير معروف.",
        "no_thumb": "مفيش صورة مصغرة متاحة.",
        "cancelled": "تم الإلغاء ✅",
        "searching": "🔎 جاري البحث...",
        "search_title": "🔎 نتائج البحث عن: <b>{q}</b>\nاختار واحد 👇",
        "no_results": "😕 مفيش نتايج. جرّب كلمات تانية.",
        "subs_title": "📝 اختار لغة الترجمة (ملف SRT):",
        "subs_sending": "📝 جاري تجهيز الترجمة...",
        "clip_prompt": (
            "✂️ ابعت وقت البداية والنهاية بالشكل ده:\n<code>00:30-01:15</code>\n"
            "أو للصوت فقط:\n<code>00:30-01:15 mp3</code>\n\n"
            "أقصى مدة للمقطع: {max}\nللإلغاء: /cancel"
        ),
        "clip_invalid": "❌ صيغة غير صحيحة. مثال: <code>1:30-2:15</code>",
        "clip_toolong": "⚠️ المقطع أطول من الحد المسموح ({max}).",
        "converting": "🎧 جاري التحويل إلى MP3...",
        "err_file20": "⚠️ الملف أكبر من الحد اللي تليجرام بيسمح للبوت يحمّله (20MB).",
        "pl_card": "📚 <b>{title}</b>\n🎞 {n} عنصر\n\nاختار طريقة تحميل الكل 👇\n(للإيقاف في أي وقت: /stop)",
        "btn_pl_video": "🎬 كل الفيديوهات (تلقائي)",
        "btn_pl_audio": "🎵 كل الأغاني MP3",
        "pl_progress": "📚 {i}/{n}\n<b>{title}</b>",
        "pl_done": "✅ خلصت قائمة التشغيل: {ok}/{n}",
        "pl_stopped": "⛔ تم الإيقاف: {ok}/{n}",
        "pl_busy": "⏳ عندك قائمة تشغيل شغالة بالفعل (/stop للإيقاف).",
        "history_title": "🕘 آخر تحميلاتك (اضغط لإعادة التحميل):",
        "history_empty": "مفيش سجل لسه.",
        "sub_usage": "الاستخدام: <code>/subscribe رابط_قناة_يوتيوب</code>\nهتوصلك إشعارات بالفيديوهات الجديدة 🔔",
        "sub_added": "🔔 تم الاشتراك في <b>{title}</b>.\nهتوصلك إشعارات بالفيديوهات الجديدة.",
        "sub_exists": "أنت مشترك فيها بالفعل.",
        "sub_limit": "وصلت للحد الأقصى للاشتراكات ({limit}). المشتركين المميزين ليهم حد أكبر 💎",
        "sub_invalid": "مقدرتش ألاقي فيديوهات في الرابط ده.",
        "sub_list_title": "🔔 اشتراكاتك (اضغط للحذف):",
        "sub_none": "مفيش اشتراكات.\nاستخدم: <code>/subscribe رابط_القناة</code>",
        "sub_new": "🔔 <b>{feed}</b>\n🎬 {title}\n{url}",
        "btn_sub_dl": "⬇️ تحميل",
        "sub_removed": "🗑 تم حذف الاشتراك.",
        "ref_bonus": "🎁 {name} دخل البوت عن طريق رابطك!\nحصلت على +{days} يوم اشتراك مميز 💎",
        "invite": (
            "🎁 <b>ادعُ أصحابك</b>\nكل صديق يدخل من رابطك = +{days} يوم اشتراك مميز 💎\n\n"
            "🔗 {link}\n👥 عدد المدعوين: {n}"
        ),
        "invite_off": "نظام الدعوات مش مفعّل حالياً.",
        "buy_off": "الدفع غير مفعّل حالياً. تواصل مع الأدمن للاشتراك المميز.",
        "buy_title": "💎 اشتراك مميز",
        "buy_desc": "بدون حد يومي للتحميل لمدة {days} يوم.",
        "buy_ok": "✅ تم تفعيل الاشتراك المميز لمدة {days} يوم 💎 شكراً!",
        "me": (
            "👤 <b>حسابي</b>\n"
            "⬇️ إجمالي التحميلات: {total}\n"
            "📅 النهاردة: {today}/{limit}\n"
            "💎 الاشتراك المميز: {premium}"
        ),
        "no": "لا",
    },
    "en": {
        "start": (
            "👋 Hi <b>{name}</b>!\n\n"
            "Send me a <b>link</b> to a video, image or file, or type a <b>name</b> of a song/video and I'll search YouTube 🔎\n\n"
            "✅ YouTube • TikTok • Instagram • Facebook • Twitter/X • Reddit • Pinterest • "
            "SoundCloud • Twitch • Vimeo • and 1000+ more sites.\n\n"
            "✨ Many qualities • MP3/M4A/FLAC/WAV • Voice • Video note • GIF • Subtitles • Clips • "
            "Playlists • Channel alerts • Convert your files to MP3\n\n"
            "⚙️ /settings  📜 /history  🔔 /subscriptions  🎁 /invite  👤 /me  ❓ /help"
        ),
        "help": (
            "📖 <b>How to use</b>\n\n"
            "🔗 Send a link (up to {links} links) → pick quality or audio.\n"
            "🔎 Type a song/video name → pick from the results.\n"
            "🎵 Audio: MP3 (128/192/320) • M4A • OPUS • FLAC • WAV • 🎤 Voice.\n"
            "⭕ “Video note” (60s) and 🎞 “GIF” (30s) from any video.\n"
            "📚 Playlist link → download all as video or MP3 (/stop to cancel).\n"
            "📝 “Subtitles” → SRT file in any available language.\n"
            "✂️ “Clip” → choose start and end time.\n"
            "🖼 Image/album links (Instagram, Pinterest...) and direct file links (PDF, ZIP, APK...) are supported.\n"
            "🎧 Send me any video/audio/voice → I convert it to MP3.\n\n"
            "🔔 <code>/subscribe channel_link</code> → alerts for new videos • /subscriptions to manage.\n"
            "🎁 /invite invite friends and earn premium days • 💎 /buy premium.\n"
            "📜 /history your last downloads • 👤 /me your account • ⚙️ /settings.\n"
            "👥 In groups: <code>/dl link</code> or <code>/search name</code>\n"
            "🌐 Inline: type @bot_username then a song name in any chat.\n\n"
            "• <b>Auto</b> = best quality that fits the upload limit.\n"
            "• Files above the limit are split or compressed (see settings).\n\n"
            "⚠️ Max part size: <b>{limit}</b>"
        ),
        "analyzing": "🔎 Analyzing link...",
        "card": "🎞 <b>{title}</b>\n{meta}\n\nChoose a format 👇",
        "queue": "⏳ Queued... starting shortly.",
        "starting": "⏳ Preparing...",
        "downloading": "⬇️ <b>Downloading</b>\n{bar} {pct}%\n🚀 {speed}  •  ⏱ {eta}",
        "processing": "⚙️ Processing / merging...",
        "compressing": "🗜 File is large, compressing to fit the limit... (may take a while)",
        "splitting": "✂️ File is large, splitting into parts...",
        "part": "Part",
        "join_parts": "ℹ️ To join the parts: put them in one folder, then use 7-Zip or <code>cat filename.* &gt; filename</code>",
        "uploading": "📤 Uploading to Telegram...",
        "gallery_try": "🖼 Fetching images/media...",
        "err_generic": "❌ Something went wrong:\n<code>{reason}</code>\n\nTry another link or try again later.",
        "err_toobig": "⚠️ File exceeds the allowed limit ({limit}) even after splitting.\nChoose a lower quality or MP3.",
        "err_live": "📡 Live streams are not supported. Try again after it ends.",
        "err_long": "⏱ Video is longer than the allowed limit ({limit}).",
        "err_quota": "🚫 You reached the daily limit ({limit} downloads). Try tomorrow, or earn premium days with /invite or /buy 💎",
        "busy": "⏳ You already have downloads running, please wait.",
        "maintenance": "🛠 The bot is under maintenance, please try again later.",
        "invalid_url": "🚫 This link is invalid or not allowed.",
        "no_url": "🔗 Send a link or a name to search.",
        "dl_usage": "Usage: <code>/dl link</code>",
        "search_usage": "Usage: <code>/search song or video name</code>",
        "join": "📢 Please join the channel first, then press “Check”.",
        "btn_join": "📢 Join channel",
        "btn_check": "✅ Check",
        "not_joined": "You haven't joined yet!",
        "expired": "This request expired, send the link again.",
        "not_yours": "This button isn't yours 🙂",
        "btn_auto": "⚡ Auto (best fitting quality)",
        "btn_thumb": "🖼 Thumbnail",
        "btn_subs": "📝 Subtitles",
        "btn_clip": "✂️ Clip",
        "btn_voice": "🎤 Voice",
        "btn_note": "⭕ Video note",
        "btn_gif": "🎞 GIF",
        "btn_back": "‹ Back",
        "btn_cancel": "❌ Cancel",
        "settings": (
            "⚙️ <b>Settings</b>\n\n🌐 Language\n🎯 Default action when you send a link\n"
            "📦 If a file is over the limit: split into parts or compress\n📎 Send video as a file (original quality)"
        ),
        "pref_ask": "❓ Ask me every time",
        "pref_best": "⚡ Auto (best quality)",
        "pref_720": "🎬 Video up to 720p",
        "pref_480": "🎬 Video up to 480p",
        "pref_audio": "🎵 MP3 audio only",
        "big_split": "✂️ Split",
        "big_compress": "🗜 Compress",
        "doc_on": "📎 Send as file: ✅ on",
        "doc_off": "📎 Send as file: ❌ off",
        "saved": "✅ Saved",
        "unknown_kind": "Unknown request.",
        "no_thumb": "No thumbnail available.",
        "cancelled": "Cancelled ✅",
        "searching": "🔎 Searching...",
        "search_title": "🔎 Results for: <b>{q}</b>\nPick one 👇",
        "no_results": "😕 No results. Try different words.",
        "subs_title": "📝 Choose subtitle language (SRT file):",
        "subs_sending": "📝 Preparing subtitles...",
        "clip_prompt": (
            "✂️ Send start and end time like this:\n<code>00:30-01:15</code>\n"
            "or for audio only:\n<code>00:30-01:15 mp3</code>\n\n"
            "Max clip length: {max}\nTo cancel: /cancel"
        ),
        "clip_invalid": "❌ Invalid format. Example: <code>1:30-2:15</code>",
        "clip_toolong": "⚠️ Clip is longer than the allowed limit ({max}).",
        "converting": "🎧 Converting to MP3...",
        "err_file20": "⚠️ File is larger than Telegram lets bots download (20MB).",
        "pl_card": "📚 <b>{title}</b>\n🎞 {n} items\n\nChoose how to download all 👇\n(to stop anytime: /stop)",
        "btn_pl_video": "🎬 All videos (auto)",
        "btn_pl_audio": "🎵 All as MP3",
        "pl_progress": "📚 {i}/{n}\n<b>{title}</b>",
        "pl_done": "✅ Playlist finished: {ok}/{n}",
        "pl_stopped": "⛔ Stopped: {ok}/{n}",
        "pl_busy": "⏳ You already have a playlist running (/stop to cancel).",
        "history_title": "🕘 Your last downloads (tap to download again):",
        "history_empty": "No history yet.",
        "sub_usage": "Usage: <code>/subscribe youtube_channel_link</code>\nYou'll get alerts for new videos 🔔",
        "sub_added": "🔔 Subscribed to <b>{title}</b>.\nYou'll get alerts for new videos.",
        "sub_exists": "You're already subscribed.",
        "sub_limit": "You reached the subscription limit ({limit}). Premium users get more 💎",
        "sub_invalid": "I couldn't find videos at this link.",
        "sub_list_title": "🔔 Your subscriptions (tap to remove):",
        "sub_none": "No subscriptions.\nUse: <code>/subscribe channel_link</code>",
        "sub_new": "🔔 <b>{feed}</b>\n🎬 {title}\n{url}",
        "btn_sub_dl": "⬇️ Download",
        "sub_removed": "🗑 Subscription removed.",
        "ref_bonus": "🎁 {name} joined through your link!\nYou earned +{days} premium day(s) 💎",
        "invite": (
            "🎁 <b>Invite friends</b>\nEach friend who joins via your link = +{days} premium day(s) 💎\n\n"
            "🔗 {link}\n👥 Invited: {n}"
        ),
        "invite_off": "Invites are not enabled right now.",
        "buy_off": "Payments are not enabled. Contact the admin for Premium.",
        "buy_title": "💎 Premium",
        "buy_desc": "No daily download limit for {days} days.",
        "buy_ok": "✅ Premium activated for {days} days 💎 Thank you!",
        "me": (
            "👤 <b>My account</b>\n"
            "⬇️ Total downloads: {total}\n"
            "📅 Today: {today}/{limit}\n"
            "💎 Premium: {premium}"
        ),
        "no": "No",
    },
}


def t(lang: str, key: str, **kw) -> str:
    table = T.get(lang) or T["ar"]
    s = table.get(key) or T["en"].get(key) or key
    return s.format(**kw) if kw else s