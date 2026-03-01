# Telegram Bot – CC Filter & Auto Hitter

Bot Telegram gồm **2 tính năng chính**: lọc CC từ text/file và Auto Hitter Stripe (kèm gen thẻ từ BIN).

## Tính năng 1: Lọc CC (Filter)

- **Gửi file .txt**: Bot đọc nội dung, lọc ra tất cả dòng CC dạng `cc|mm|yy|cvv` (từ format kiểu `CC: ...`, `💳 Card: ...`, `🟢 CHARGED` ...), rồi trả lại **một file .txt** chỉ chứa các dòng CC.
- **Gửi text** (không phải lệnh): Nếu trong tin có CC, bot trả lời bằng **text** chứa các dòng CC (tối đa 10 dòng); nhiều hơn thì trả file .txt.

Ví dụ input:
```
CC: 5218531108462848|07|2029|282
Status: Approved ✅
💳 Card: 4266902072261538|03|26|885
🟢 CHARGED 💎
💳 Card: 4744784515914481|08|30|002
```
Output lọc ra:
```
5218531108462848|07|2029|282
4266902072261538|03|26|885
4744784515914481|08|30|002
```

## Tính năng 2: Auto Hitter (Stripe)

- **Parse checkout**: `/co <url_stripe_checkout>` – lấy thông tin checkout (merchant, giá, PK/CS).
- **Charge 1 thẻ**: `/co <url> cc|mm|yy|cvv` – charge đúng 1 thẻ.
- **Hitter bằng BIN (tự gen thẻ)**:
  - `/co <url> bin <BIN>` – gen 1 thẻ từ BIN (Luhn hợp lệ), expiry/cvv random, rồi charge.
  - `/co <url> bin <BIN> <số_lượng>` – gen nhiều thẻ (tối đa 50) và hit lần lượt đến khi CHARGED hoặc hết.

BIN có thể có chữ `x` (random), ví dụ: `521853xx`, `424242xxxxxxxx`.

## Host trên Railway

### 1. Chuẩn bị

- Tạo bot qua [@BotFather](https://t.me/BotFather), lấy **BOT_TOKEN**.
- Có tài khoản [Railway](https://railway.app).

### 2. Deploy

1. Tạo project mới trên Railway.
2. Chọn **Deploy from GitHub repo** (đẩy code vào repo rồi kết nối) hoặc **Deploy from local** (dùng CLI).
3. Root của repo/upload phải chứa: `main.py`, `requirements.txt`, `config.py`, thư mục `commands/`, `hitter/`, file `cc_filter.py`, `card_utils.py`, `bin_gen.py`.
4. Trong Railway project, vào **Variables** và thêm:
   - `BOT_TOKEN` = token bot từ BotFather.
   - (Tùy chọn) `OWNER_ID`, `ALLOWED_GROUP_ID` nếu bạn muốn giới hạn quyền (trong code có thể dùng để check).
5. **Process**: Railway sẽ đọc `Procfile`. Trong đó khai báo:
   ```text
   worker: python main.py
   ```
   Đảm bảo process type là **worker** (chạy lâu dài), không phải web.

### 3. Chạy local (test)

```bash
cd sourcebot
pip install -r requirements.txt
set BOT_TOKEN=your_bot_token
python main.py
```

(Linux/macOS: `export BOT_TOKEN=your_bot_token`)

### 4. Cấu trúc thư mục gợi ý

```text
sourcebot/
├── main.py
├── config.py
├── requirements.txt
├── Procfile
├── runtime.txt
├── README.md
├── cc_filter.py
├── card_utils.py
├── bin_gen.py
├── commands/
│   ├── __init__.py
│   ├── start.py
│   ├── filter_cc.py
│   └── co.py
└── hitter/
    ├── __init__.py
    ├── checkout_parse.py
    └── stripe_charge.py
```

## Lưu ý

- Bot dùng **long polling** (không cần public URL). Trên Railway chọn process **worker** chạy `python main.py`.
- Không hardcode token: luôn dùng biến môi trường `BOT_TOKEN`.
- Hitter gọi trực tiếp API Stripe; có thể cần proxy tùy môi trường (trong code có thể mở rộng thêm proxy sau).
